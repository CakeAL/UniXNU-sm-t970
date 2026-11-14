// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board adapter for the gts7xlwifi DRV2 transaction implementation.
#include <IOKit/IODeviceMemory.h>
#include <IOKit/IOLib.h>
#include <kern/clock.h>
#include <machine/machine_routines.h>

namespace {
struct Region {
    uintptr_t base;
    unsigned length;
    IOOptionBits options;
    IOMemoryMap *map;
};
Region regions[] = {
    {0x0c3f0000, 0x1000, kIOMapReadOnly, nullptr},
    {0x80860000, 0x20000, kIOMapReadOnly, nullptr},
    {0x18220000, 0x2000, 0, nullptr},
};
unsigned busy;

uintptr_t address(uintptr_t physical)
{
    for (const auto &region : regions) {
        if (physical >= region.base && physical - region.base <= region.length - 4) {
            return region.map->getVirtualAddress() + physical - region.base;
        }
    }
    panic("T970 RPMh: unmapped address %lx", (unsigned long)physical);
}

bool mapRegions()
{
    for (auto &region : regions) {
        if (region.map) continue;
        auto *memory = IODeviceMemory::withRange(region.base, region.length);
        if (!memory) return false;
        region.map = memory->map(kIOMapAnywhere | kIOMapInhibitCache | region.options);
        memory->release();
        if (!region.map) return false;
        if (!region.map->getVirtualAddress()) {
            OSSafeReleaseNULL(region.map);
            return false;
        }
    }
    return true;
}
}

extern "C" void t970_rpmh_lock()
{
    while (__atomic_exchange_n(&busy, 1u, __ATOMIC_ACQUIRE)) IOSleep(1);
}

extern "C" void t970_rpmh_unlock()
{
    __atomic_store_n(&busy, 0u, __ATOMIC_RELEASE);
}

namespace rpmh {
#define STATIC static
#define CONST const
#define VOID void
#define BIT0 (1u << 0)
#define BIT1 (1u << 1)
#define BIT2 (1u << 2)
#define BIT3 (1u << 3)
#define BIT8 (1u << 8)
#define BIT16 (1u << 16)
#define BIT24 (1u << 24)
#define MAX_UINT32 UINT32_MAX
#define EFI_ERROR(x) ((x) != EFI_SUCCESS)
#define DEBUG(x) ((void)0)
using UINT8 = uint8_t;
using UINT16 = uint16_t;
using UINT32 = uint32_t;
using UINT64 = uint64_t;
using UINTN = uintptr_t;
using BOOLEAN = bool;
using EFI_STATUS = int;
enum {
    EFI_SUCCESS, EFI_TIMEOUT, EFI_DEVICE_ERROR, EFI_INVALID_PARAMETER, EFI_UNSUPPORTED,
    EFI_NOT_FOUND, EFI_ACCESS_DENIED, EFI_COMPROMISED_DATA, EFI_NOT_READY, EFI_ALREADY_STARTED,
};

static uint32_t MmioRead32(uintptr_t physical)
{
    return *reinterpret_cast<const volatile uint32_t *>(address(physical));
}

static uint16_t MmioRead16(uintptr_t physical)
{
    return uint16_t(MmioRead32(physical & ~uintptr_t(3)) >> ((physical & 2) * 8));
}

static void MemoryFence()
{
    __asm__ volatile("dsb sy" ::: "memory");
}

static void MmioWrite32(uintptr_t physical, uint32_t value)
{
    MemoryFence();
    *reinterpret_cast<volatile uint32_t *>(address(physical)) = value;
    MemoryFence();
}

static uint64_t GetPerformanceCounter() { return mach_absolute_time(); }
static uint64_t GetTimeInNanoSecond(uint64_t ticks)
{
    uint64_t ns;
    absolutetime_to_nanoseconds(ticks, &ns);
    return ns;
}
static void MicroSecondDelay(unsigned us) { IODelay(us); }
static bool SaveAndDisableInterrupts() { return ml_set_interrupts_enabled(false); }
static void SetInterruptState(bool state) { ml_set_interrupts_enabled(state); }

#include "T970Rpmh.inc"
}

extern "C" int t970_rpmh_write(const char *name, uint32_t word, uint32_t value)
{
    if (!name || !*name || strnlen(name, 9) > 8 || (word != 0 && word != 4 && word != 8)) {
        return rpmh::EFI_INVALID_PARAMETER;
    }
    t970_rpmh_lock();
    int result = mapRegions() ? rpmh::T970RpmhWrite(name, word, value) : -200;
    t970_rpmh_unlock();
    return result;
}
