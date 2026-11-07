// SPDX-License-Identifier: BSD-2-Clause-Patent
// Read-only MAX77705 battery service. A boot-lifetime worker refreshes the
// gauge through the board's bounded GPIO I2C read and publishes the sample as
// an IOPMPowerSource. No PMIC, gauge or charger configuration is written.
// IOService brings in OSSharedPtr before the board bus header uses it.
#include <IOKit/IOLib.h>
#include <IOKit/IOService.h>
#include <IOKit/pwr_mgt/IOPMPowerSource.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSSymbol.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>

#include "BatteryReport.h"
#include "GaugeProbe.h"
#include "Max77705Charger.h"

extern "C" {
extern kmod_info_t g_kernel_kmod_info;
void t970_battery_static_init(void) __asm__("__GLOBAL__sub_I_BatteryService.cpp");
// The exported thread.h omits this declaration, as T970Touch also records.
void thread_terminate_self(void);
}

namespace {

using t970_power::GaugeAction;
using t970_power::GaugeSample;
using t970_power::t970_charger_config;
using t970_power::t970_charger_config_decode;
using t970_power::t970_charger_decode;
using t970_power::t970_charger_state;

constexpr unsigned kPollMilliseconds = 5000;
bool chargeArmed;

// Double-buffered diagnostic snapshot for the terminal report. The worker only
// overwrites the slot that the published index does not select, so a panic
// reader can format a committed sample without taking a lock.
struct BatteryState {
    GaugeSample slot[2];
    uint32_t index;
    uint32_t available;
    uint32_t samples;
    uint32_t errors;
    uint32_t published;
    const char *chargeResult;
    uint64_t sampledAt;
};
BatteryState state;

void publishState(const GaugeSample &sample, bool complete) {
    uint32_t next = state.index ^ 1u;
    state.slot[next] = sample;
    state.sampledAt = mach_absolute_time();
    state.samples++;
    if (!complete) state.errors++;
    state.chargeResult = sample.chargeResult;
    __atomic_store_n(&state.index, next, __ATOMIC_RELEASE);
    __atomic_store_n(&state.available, 1u, __ATOMIC_RELEASE);
}

IOService *waitForBSD(void) {
    for (;;) {
        OSDictionary *matching = IOService::resourceMatching("IOBSD");
        IOService *provider = matching ?
            IOService::waitForMatchingService(matching, 60ull * NSEC_PER_SEC) : nullptr;
        OSSafeReleaseNULL(matching);
        if (provider) return provider;
        printf("T970 battery: IOBSD not ready; retrying\n");
        IOSleep(5000);
    }
}

void batteryWorker(void *, wait_result_t);

} // namespace

// Publishes only fields that were actually decoded. An incomplete read keeps the
// previous values and sets an error condition instead of presenting zeroes as
// measurements; a complete later sample clears it through updateStatus().
class T970Battery : public IOPMPowerSource {
    OSDeclareDefaultStructors(T970Battery)

    bool published = false;

    void setValue(const char *name, OSObject *value) {
        const OSSymbol *key = OSSymbol::withCString(name);
        if (!key) return;
        setPSProperty(key, value);
        key->release();
    }

    void setNumber(const char *name, uint32_t value) {
        OSNumber *number = OSNumber::withNumber(value, 32);
        if (!number) return;
        setValue(name, number);
        number->release();
    }

    void setBoolean(const char *name, bool value) {
        setValue(name, value ? kOSBooleanTrue : kOSBooleanFalse);
    }

public:
    bool init(void) override {
        if (!IOPMPowerSource::init()) return false;
        setName("T970Battery");
        setProperty("Built-In", kOSBooleanTrue);
        setProperty("DeviceName", "MAX77705 Battery");
        setTimeRemaining(-1);
        return true;
    }

    void acceptSample(const GaugeSample &sample, const t970_charger_state &charger) {
        const uint32_t values = sample.values.valid;
        const bool gaugeComplete = sample.identified && values == 0x7f;

        if (values & T970_BAT_PRESENT) setBatteryInstalled(sample.values.present != 0);
        if (values & T970_BAT_SOC) {
            unsigned percent = sample.values.percent_x100 / 100;
            if (percent > 100) percent = 100;
            setCurrentCapacity(percent);
            setMaxCapacity(100);
            setNumber("T970StateOfChargePercentX100", sample.values.percent_x100);
            setAtWarnLevel(sample.values.percent_x100 <= 1500);
            setAtCriticalLevel(sample.values.percent_x100 <= 500);
        }
        if (values & T970_BAT_VOLTAGE) setVoltage(sample.values.voltage_uv / 1000);
        if (values & T970_BAT_CURRENT) {
            const int milliamps = sample.values.current_ua / 1000;
            setAmperage(milliamps);
            setNumber("InstantAmperage", static_cast<uint32_t>(static_cast<int32_t>(milliamps)));
        }
        if (values & T970_BAT_TEMPERATURE) {
            setNumber("T970GaugeTemperatureMilliC", static_cast<uint32_t>(sample.values.temperature_mc));
        }
        if (values & T970_BAT_REMAINING) setNumber("T970RemainingMilliampHours", sample.values.remaining_mah);
        if (values & T970_BAT_FULL) setNumber("T970FullMilliampHours", sample.values.full_mah);

        if (charger.valid) {
            setExternalConnected(charger.external);
            setBoolean("AppleRawExternalConnected", charger.external);
            setIsCharging(charger.charging);
            setBoolean("FullyCharged", charger.full);
            setNumber("T970ChargerDetail", charger.chgDtls);
        }
        t970_charger_config config = t970_charger_config_decode(sample.config, sample.configValid);
        if (config.valid) {
            // Read-only snapshot for the next charger decision; nothing here writes it back.
            setNumber("T970ChargerConfig00", config.cnfg00);
            setNumber("T970ChargerConfig02", config.cnfg02);
            setNumber("T970ChargerConfig04", config.cnfg04);
            setNumber("T970ChargerConfig06", config.cnfg06);
            setNumber("T970ChargerConfig09", config.cnfg09);
            setNumber("T970ChargeCurrentMilliamp", config.chargeCurrentMa);
            setNumber("T970InputCurrentLimitMilliamp", config.inputCurrentMa);
            setBoolean("T970ChargerWatchdogEnabled", config.watchdogEnabled);
            setBoolean("T970ChargeEnabled", config.chargeEnabled);
        }

        if (!gaugeComplete || !charger.valid) {
            const OSSymbol *error = OSSymbol::withCString("MAX77705ReadIncomplete");
            if (error) {
                setErrorCondition(const_cast<OSSymbol *>(error));
                error->release();
            }
        } else if (properties->getObject(errorConditionKey)) {
            properties->removeObject(errorConditionKey);
            removeProperty(errorConditionKey);
            settingsChangedSinceUpdate = true;
        }

        setNumber("T970SampleValidFields", values);
        setBoolean("T970SampleCurrent", gaugeComplete && charger.valid);
        updateStatus();

        if (!published && gaugeComplete) {
            registerService();
            published = true;
            __atomic_store_n(&state.published, 1u, __ATOMIC_RELEASE);
            printf("T970 battery: IOPMPowerSource registered percent=%u external=%u charging=%u\n",
                   currentCapacity(), unsigned(charger.external), unsigned(charger.charging));
        }
    }
};
OSDefineMetaClassAndStructors(T970Battery, IOPMPowerSource)

namespace {

void batteryWorker(void *, wait_result_t) {
    IOService *provider = waitForBSD();

    T970Battery *battery = new T970Battery;
    bool attached = battery && battery->init() && battery->attach(provider);
    if (!attached || !battery->start(provider)) {
        printf("T970 battery: power-source start failed attached=%u\n", unsigned(attached));
        if (attached) battery->detach(provider);
        OSSafeReleaseNULL(battery);
        provider->release();
        thread_terminate_self();
        return;
    }
    provider->release();

    bool lastComplete = false, lastExternal = false, lastCharging = false, lastFull = false;
    uint32_t lastPercent = 0xffffffffu;
    unsigned count = 0;
    for (;;) {
        GaugeSample sample;
        GaugeAction action;
        action.enableCharging = chargeArmed;
        bool complete = t970_power::readGaugeSample(sample, chargeArmed ? &action : nullptr);
        t970_charger_state charger = t970_charger_decode(sample.charger, sample.chargerValid);
        publishState(sample, complete);
        battery->acceptSample(sample, charger);
        ++count;
        if (count == 1 || complete != lastComplete || charger.external != lastExternal ||
            charger.charging != lastCharging || charger.full != lastFull ||
            sample.values.percent_x100 != lastPercent || !(count % 12)) {
            printf("T970 battery: sample=%u complete=%u valid=%x percent=%u voltage_mv=%u current_ma=%d temp_mc=%d external=%u charging=%u full=%u watchdog=%u published=%u restored=%u stage=%s/%s\n",
                   count, unsigned(complete), sample.values.valid, sample.values.percent_x100,
                   sample.values.voltage_uv / 1000, sample.values.current_ua / 1000,
                   sample.values.temperature_mc, unsigned(charger.external),
                   unsigned(charger.charging), unsigned(charger.full),
                   unsigned(charger.watchdogExpired),
                   __atomic_load_n(&state.published, __ATOMIC_ACQUIRE),
                   unsigned(sample.restored), sample.stage, sample.fault);
            if (sample.writeAttempted) {
                printf("T970 battery: charger action result=%s applied=%u cnfg06=%02x\n",
                       sample.chargeResult, unsigned(sample.writeApplied), sample.chargeReadback06);
            }
            if (sample.configValid) {
                t970_charger_config config = t970_charger_config_decode(sample.config, true);
                printf("T970 battery: charger cfg %02x/%02x/%02x/%02x/%02x wdtEn=%u chgEn=%u ichg=%umA iin=%umA cv=%02x\n",
                       config.cnfg00, config.cnfg02, config.cnfg04, config.cnfg06, config.cnfg09,
                       unsigned(config.watchdogEnabled), unsigned(config.chargeEnabled),
                       config.chargeCurrentMa, config.inputCurrentMa, config.floatVoltageCode);
            }
        }
        lastComplete = complete;
        lastExternal = charger.external;
        lastCharging = charger.charging;
        lastFull = charger.full;
        lastPercent = sample.values.percent_x100;
        IOSleep(kPollMilliseconds);
    }
}

} // namespace

extern "C" bool t970_battery_report(char *out, unsigned length) {
    if (!out || !length) return false;
    if (!__atomic_load_n(&state.available, __ATOMIC_ACQUIRE)) return false;
    uint32_t index = __atomic_load_n(&state.index, __ATOMIC_ACQUIRE);
    t970_power::formatGaugeSample(state.slot[index], out, length);
    size_t used = strlen(out);
    if (used >= length) return true;
    uint64_t age = 0;
    uint64_t now = mach_absolute_time();
    if (now > state.sampledAt) absolutetime_to_nanoseconds(now - state.sampledAt, &age);
    snprintf(out + used, length - used,
             "\nBattery svc=1 samples=%u errors=%u published=%u age_ms=%llu charge=%s",
             __atomic_load_n(&state.samples, __ATOMIC_ACQUIRE),
             __atomic_load_n(&state.errors, __ATOMIC_ACQUIRE),
             __atomic_load_n(&state.published, __ATOMIC_ACQUIRE),
             static_cast<unsigned long long>(age / 1000000),
             state.chargeResult ? state.chargeResult : "none");
    return true;
}

extern "C" void t970_battery_start(void) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-battery", &enabled, sizeof(enabled)) || enabled != 1) return;
    unsigned charge = 0;
    chargeArmed = PE_parse_boot_argn("t970-charge", &charge, sizeof(charge)) && charge == 1;
    static uint32_t started;
    if (__atomic_exchange_n(&started, 1u, __ATOMIC_ACQ_REL)) return;
    // Register the class during the single-threaded bsd_init window, before any
    // concurrent kext load can own OSMetaClass's stalled-class state.
    void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
    if (!handle) {
        printf("T970 battery: preModLoad failed\n");
        return;
    }
    t970_battery_static_init();
    if (OSMetaClass::postModLoad(handle) != kOSReturnSuccess) {
        printf("T970 battery: postModLoad failed\n");
        return;
    }
    thread_t thread = THREAD_NULL;
    kern_return_t result = kernel_thread_start(batteryWorker, nullptr, &thread);
    if (result == KERN_SUCCESS) {
        thread_deallocate(thread);
    } else {
        printf("T970 battery: worker start failed=%d\n", result);
    }
}
