// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board wiring: stock SM-T970 DT; v5 protocol: see docs/buttons.md.
#include <IOKit/IODeviceMemory.h>
#include <IOKit/IOLib.h>
#include <libkern/c++/OSSharedPtr.h>
#include <kern/thread.h>
#include <pexpert/pexpert.h>
#include "KeyProbeCore.h"

extern "C" void thread_terminate_self(void);
extern "C" int native_t970_key_hid_publish(uint32_t) __attribute__((weak_import));

namespace {
uint32_t started, stage, version, ponApid, gpioApid, mask, errors, samples;
uint32_t hidEnabled, hidReports, hidStatus;
t970_key_state keys[3];

OSSharedPtr<IOMemoryMap> map(uint64_t address, uint64_t size, bool write = false) {
    OSSharedPtr<IODeviceMemory> memory(IODeviceMemory::withRange(address, size), OSNoRetain);
    if (!memory) return {};
    return OSSharedPtr<IOMemoryMap>(memory->map(kIOMapAnywhere | kIOMapInhibitCache |
                                              (write ? 0 : kIOMapReadOnly)), OSNoRetain);
}
uint32_t load(const uint32_t &v) { return __atomic_load_n(&v, __ATOMIC_RELAXED); }
void store(uint32_t &v, uint32_t n) { __atomic_store_n(&v, n, __ATOMIC_RELAXED); }

void worker(void *, wait_result_t) {
    // Only the observer command window is writable. Never map the RW channels.
    auto core = map(0x0c440000, 0x2000);
    auto cnfg = map(0x0c40a000, 0x1000);
    auto obs = map(0x0e600000, 0x10000, true);
    store(stage, 2);
    if (core && cnfg && obs) {
        t970_arbiter arb = {reinterpret_cast<volatile uint32_t *>(core->getVirtualAddress()),
                           reinterpret_cast<volatile uint32_t *>(cnfg->getVirtualAddress()),
                           reinterpret_cast<volatile uint32_t *>(obs->getVirtualAddress()), 0};
        uint32_t v = 0, n = 0, pon = 0, gpio = 0;
        store(stage, 3);
        int rc = t970_arb_version(&arb, &v);
        store(version, v);
        if (!rc) {
            rc = t970_arb_apids(&arb, &n);
            if (!rc) rc = t970_arb_find(&arb, T970_PON_PPID, &pon);
            if (!rc) rc = t970_arb_find(&arb, T970_GPIO_PPID, &gpio);
            store(ponApid, pon);
            store(gpioApid, gpio);
            store(stage, rc ? 4 : 5);
            t970_key_state state[3] = {};
            unsigned failures = 0;
            uint32_t delivered = ~0u;
            while (!rc) {
                uint32_t p = 0, g = 0;
                int error = t970_arb_read32(&arb, pon, T970_PON_RT_STS, &p);
                if (!error) error = t970_arb_read32(&arb, gpio, T970_GPIO_RT_STS, &g);
                if (error) {
                    store(errors, load(errors) + 1);
                    // An interrupted sample breaks the two-sample debounce chain.
                    for (auto &key : state) key.live = key.last = 0;
                    // Release an accepted press on transport loss rather than leaving it held.
                    if (load(hidEnabled) && native_t970_key_hid_publish) {
                        store(hidStatus, static_cast<uint32_t>(native_t970_key_hid_publish(0)));
                        delivered = ~0u;
                    }
                    for (auto &key : state) key.down = 0;
                    if (++failures >= 3) { store(stage, 6); break; }
                } else {
                    failures = 0;
                    uint32_t levels = t970_keys_mask(p, g);
                    store(mask, levels);
                    for (unsigned i = 0; i < 3; ++i) {
                        t970_key_update(&state[i], (levels & (1u << i)) != 0, 1);
                        store(keys[i].presses, state[i].presses);
                        store(keys[i].releases, state[i].releases);
                    }
                    uint32_t accepted = state[0].down | (uint32_t(state[1].down) << 1) |
                                        (uint32_t(state[2].down) << 2);
                    if (load(hidEnabled) && native_t970_key_hid_publish && accepted != delivered) {
                        int result = native_t970_key_hid_publish(accepted);
                        store(hidStatus, static_cast<uint32_t>(result));
                        if (!result) { delivered = accepted; store(hidReports, load(hidReports) + 1); }
                    }
                    store(samples, load(samples) + 1);
                }
                IOSleep(16);
            }
        }
    }
    // Release mappings before terminating the kernel thread (which does not unwind).
    core.reset(); cnfg.reset(); obs.reset();
    thread_terminate_self();
}
}

extern "C" void native_t970_key_start(void) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-keys", &enabled, sizeof(enabled)) || enabled != 1) return;
    if (__atomic_exchange_n(&started, 1, __ATOMIC_ACQ_REL)) return;
    unsigned hid = 0;
    if (PE_parse_boot_argn("t970-keys-hid", &hid, sizeof(hid)) && hid == 1) store(hidEnabled, 1);
    store(stage, 1);
    thread_t thread = THREAD_NULL;
    if (kernel_thread_start(worker, nullptr, &thread) == KERN_SUCCESS) thread_deallocate(thread);
    else store(stage, 7);
}

extern "C" void native_t970_key_state(char *out, unsigned size) {
    if (!out || !size || !load(started)) return;
    t970_key_state snapshot[3] = {};
    for (unsigned i = 0; i < 3; ++i) {
        snapshot[i].presses = load(keys[i].presses);
        snapshot[i].releases = load(keys[i].releases);
    }
    char line[192];
    t970_keys_text(line, sizeof(line), load(version), load(ponApid), load(gpioApid), load(mask), snapshot);
    snprintf(out, size, "\n%s stage=%u samples=%u errors=%u hid=%u/%u/%x", line, load(stage), load(samples), load(errors),
             load(hidEnabled), load(hidReports), load(hidStatus));
}
