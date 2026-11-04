// T970 board integration adapted from RigoLigoRLC/unixnu-sm-t733
// 3bb0d6f7840f088db6a0ec88ecb841e12042422f, package/T733Display/DisplayRegistration.cpp.
// SPDX-License-Identifier: BSD-2-Clause-Patent
#include <IOKit/IOPlatformExpert.h>
#include <IOKit/IODeviceMemory.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <IOKit/IOLib.h>
#include <IOKit/IOUserClient.h>
#include <libkern/c++/OSData.h>
#include <mach/kmod.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <machine/machine_routines.h>
#include <pexpert/pexpert.h>
#include "T970GopGeometry.h"



extern "C" kmod_info_t g_kernel_kmod_info;
extern "C" void displayStaticInit(void) __asm__("__GLOBAL__sub_I_NativeLegacyDisplay.cpp");
extern "C" IOService *native_legacy_display_allocate(void);
extern "C" kern_return_t OSKextLoadKextWithIdentifier(const char *);
extern "C" void t970_keystore_start(void);
extern "C" void native_t970_keystore_state(char *, unsigned);

static IOService *pendingDisplay;
static IOService *activeDisplay;
static IOPlatformDevice *activeProvider;
static bool initialized;
static volatile unsigned displayStage, displayMapped, displayPublished;
static volatile int displayMeta=-1, displaySurface=-1;
// Relaxed counters are diagnostic only; they never decide driver behavior.
static uint32_t clientsEntered, clientsOpened, clientsFailed, lastClientType, lastClientStatus;
static uint32_t swapsAccepted, swapsRejected, lastSwapReason, transfers, lastTransferStatus;
static uint32_t copies, retired;
// GopFramebuffer cf3b429 reports arm, notify, idle, late, start, refresh.
static uint32_t vsyncEvents[6];
static inline void note(uint32_t &value) { __atomic_fetch_add(&value,1,__ATOMIC_RELAXED); }
static inline uint32_t sample(uint32_t &value) { return __atomic_load_n(&value,__ATOMIC_RELAXED); }
extern "C" void native_t970_display_state(char *out, unsigned length) {
    if (!out || !length) return;
    snprintf(out,length,"display stage=%u meta=%d surface=%d mapped=%u published=%u vsync start/arm/idle/late/refresh=%u/%u/%u/%u/%u\nclient enter/open/fail=%u/%u/%u type=%x status=%x swap ok/bad=%u/%u why=%u xfer=%u status=%x copies=%u retire=%u vsync=%u",
             displayStage,displayMeta,displaySurface,displayMapped,displayPublished,
             sample(vsyncEvents[4]),sample(vsyncEvents[0]),sample(vsyncEvents[2]),
             sample(vsyncEvents[3]),sample(vsyncEvents[5]),
             sample(clientsEntered),sample(clientsOpened),sample(clientsFailed),sample(lastClientType),
             sample(lastClientStatus),sample(swapsAccepted),sample(swapsRejected),sample(lastSwapReason),
             sample(transfers),sample(lastTransferStatus),sample(copies),sample(retired),sample(vsyncEvents[1]));
    size_t used = strlen(out);
    native_t970_keystore_state(out + used, length - used);
}
static bool consoleReleased;
static bool reportTracksScanout;
static bool reportOwnsScanout;
static uint64_t scanoutWriter;
static uint64_t publishedAt, firstCopyAt;
static uint32_t firstLitExtent;
static uint32_t completedFrames;
static uint32_t rejectedFrames;

static bool videoAvailable(PE_Video &video) {
    return !PE_current_console(&video) &&
        t970GopGeometry(video.v_baseAddr, video.v_width, video.v_height,
                        video.v_rowBytes, video.v_depth, video.v_rotate);
}

static bool publishWord(IORegistryEntry *entry, const char *name, uint32_t value) {
    OSData *data = OSData::withBytes(&value, sizeof(value));
    bool result = data && entry->setProperty(name, data);
    OSSafeReleaseNULL(data);
    return result;
}

extern "C" void native_legacy_display_probe(void) {
    unsigned enabled=0;
    if (!PE_parse_boot_argn("t970-display-start", &enabled, sizeof(enabled)) || enabled != 1) return;
    if (initialized) {
        return;
    }
    initialized = true;
    t970_keystore_start();
    displayStage=1;

    PE_Video video = {};
    if (!videoAvailable(video)) {
        IOLog("T970 display: firmware framebuffer geometry unavailable\n");
        return;
    }
    displayStage=2;
    void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
    if (!handle) {
        return;
    }
    displayStaticInit();
    OSReturn status = OSMetaClass::postModLoad(handle);
    displayMeta=status; displayStage=3;
    if (status) {
        IOLog("T970 display: class registration failed %x\n", status);
        return;
    }

    IOService *display = native_legacy_display_allocate();
    if (!display || !display->init()) {
        OSSafeReleaseNULL(display);
        IOLog("T970 display: instance initialization failed\n");
        return;
    }
    pendingDisplay = display;
    displayStage=4;
    IOLog("T970 display: initialized original Legacy, waiting for IOBSD\n");
}

extern "C" void native_legacy_display_late_probe(void) {
    IOService *display = pendingDisplay;
    if (!display) {
        return;
    }
    pendingDisplay = nullptr;
    displayStage=5;

    kern_return_t load = OSKextLoadKextWithIdentifier("com.apple.iokit.IOSurface");
    OSDictionary *matching = IOService::nameMatching("IOCoreSurfaceRoot");
    IOService *surface = matching ? IOService::waitForMatchingService(matching, 5000000000ULL) : nullptr;
    bool surfaceReady = load == KERN_SUCCESS && surface;
    displaySurface=load;
    if(surfaceReady) displayStage=6;
    OSSafeReleaseNULL(surface);
    OSSafeReleaseNULL(matching);
    PE_Video video = {};
    if (!surfaceReady || !videoAvailable(video)) {
        IOLog("T970 display: IOSurface unavailable status=%x\n", load);
        display->release();
        return;
    }

    IOService *parent = IOService::getResourceService();
    IORegistryEntry *treeParent = IORegistryEntry::fromPath("/arm-io", gIODTPlane);
    IOPlatformDevice *provider = new IOPlatformDevice;
    IODeviceMemory *memory = IODeviceMemory::withRange(video.v_baseAddr, video.v_rowBytes * video.v_height);
    OSArray *ranges = OSArray::withCapacity(1);
    const char type[] = "display-subsystem";
    OSData *typeData = OSData::withBytes(type, sizeof(type));
    bool providerAttached = false, providerStarted = false, treeAttached = false;
    bool displayAttached = false, displayStarted = false;
    if (parent && treeParent && provider && memory && ranges && typeData && provider->init()) {
        if (!ranges->setObject(memory)) {
            OSSafeReleaseNULL(typeData); OSSafeReleaseNULL(ranges); OSSafeReleaseNULL(memory);
            OSSafeReleaseNULL(provider); OSSafeReleaseNULL(treeParent); display->release(); return;
        }
        provider->setDeviceMemory(ranges);
        provider->setName("T970FirmwareFramebuffer");
        providerAttached = provider->attach(parent);
        if (providerAttached) {
            providerStarted = provider->start(parent);
        }
        if (providerStarted && provider->setProperty("device_type", typeData)) {
            provider->setName("gop-display", gIODTPlane);
            treeAttached = provider->attachToParent(treeParent, gIODTPlane);
        }
        displayStage=7;
        SInt32 score = 0;
        if (treeAttached && display->probe(provider, &score) == display) {
            displayAttached = display->attach(provider);
        }
        if (displayAttached) {
            unsigned hold = 0;
            PE_parse_boot_argn("t970-display-hold", &hold, sizeof(hold));
            __atomic_store_n(&reportTracksScanout, hold == 1, __ATOMIC_RELEASE);
            displayStarted = display->start(provider);
        }
    }

    OSSafeReleaseNULL(typeData);
    OSSafeReleaseNULL(ranges);
    OSSafeReleaseNULL(memory);
    if (displayStarted) {
        displayStage=8;
        activeDisplay = display;
        activeProvider = provider;
        OSSafeReleaseNULL(treeParent);
        IOLog("T970 display: CPU framebuffer service ready 2800x1752 stride=%lu\n", video.v_rowBytes);
        return;
    }

    IOLog("T970 display: start failed provider=%u tree=%u attached=%u\n",
          providerStarted, treeAttached, displayAttached);
    if (displayAttached) {
        display->detach(provider);
    }
    if (treeAttached) {
        provider->detachFromParent(treeParent, gIODTPlane);
    }
    if (providerStarted) {
        provider->stop(parent);
    }
    if (providerAttached) {
        provider->detach(parent);
    }
    OSSafeReleaseNULL(provider);
    OSSafeReleaseNULL(treeParent);
    display->release();
}

extern "C" bool native_legacy_gop_mapping_observed(IOService *, IOMemoryMap *mapping,
                                                   uint32_t width, uint32_t height) {
    PE_Video video = {};
    if (!mapping || !mapping->getVirtualAddress() || !videoAvailable(video) ||
        mapping->getLength() != video.v_rowBytes * video.v_height || width != 2800 || height != 1752 ||
        mapping->getPhysicalAddress() != video.v_baseAddr) {
        return false;
    }

    IORegistryEntry *chosen = IORegistryEntry::fromPath("/chosen", gIODTPlane);
    if (!chosen) {
        return false;
    }
    bool result = publishWord(chosen, "display-scale", 2) && publishWord(chosen, "display-rotation", 0);
    chosen->release();
    IOLog("T970 display: scanout cache option=%llx physical=%llx bytes=%llu\n",
          (uint64_t)(mapping->getMapOptions() & kIOMapCacheMask),
          (uint64_t)mapping->getPhysicalAddress(), (uint64_t)mapping->getLength());
    if(result) displayMapped=1;
    return result;
}

// The CPU surface path checks prepare twice on the same thread. Its terminal
// transfer callback runs after the store barrier or on each rejection.
static bool reserveScanout(uint64_t self) {
    if (__atomic_load_n(&reportOwnsScanout, __ATOMIC_SEQ_CST)) return false;
    uint64_t previous = 0;
    if (!__atomic_compare_exchange_n(&scanoutWriter, &previous, self, false,
                                     __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST) && previous != self) return false;
    return !__atomic_load_n(&reportOwnsScanout, __ATOMIC_SEQ_CST);
}

static void releaseScanout(uint64_t self) {
    __atomic_compare_exchange_n(&scanoutWriter, &self, 0, false,
                                __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST);
}

extern "C" int native_t970_display_hold(void) {
    if (!__atomic_load_n(&reportTracksScanout, __ATOMIC_ACQUIRE)) return -1;
    // Close admission before checking for an in-flight writer. A writer
    // claiming the slot concurrently must recheck admission before copying.
    __atomic_store_n(&reportOwnsScanout, true, __ATOMIC_SEQ_CST);
    return __atomic_load_n(&scanoutWriter, __ATOMIC_SEQ_CST) != 0;
}

extern "C" bool native_legacy_prepare_scanout(void) {
    if (__atomic_load_n(&reportTracksScanout, __ATOMIC_ACQUIRE) && !reserveScanout(thread_tid(current_thread()))) return false;
    if (!consoleReleased) {
        unsigned int noVideoConsole = 0;
        // Match arm_init: presence of t970-novc skips text console setup.
        if (!PE_parse_boot_argn("t970-novc", &noVideoConsole, sizeof(noVideoConsole))) {
            IOLog("T970 display: first CPU frame, releasing text console\n");
            PE_initialize_console(nullptr, kPEDisableScreen);
        }
        consoleReleased = true;
    }
    return true;
}

extern "C" void native_t970_display_timing(char *out, unsigned length, int hold) {
    uint64_t publishNs = 0, copyNs = 0;
    absolutetime_to_nanoseconds(__atomic_load_n(&publishedAt, __ATOMIC_RELAXED), &publishNs);
    absolutetime_to_nanoseconds(__atomic_load_n(&firstCopyAt, __ATOMIC_RELAXED), &copyNs);
    uint32_t extent = __atomic_load_n(&firstLitExtent, __ATOMIC_RELAXED);
    snprintf(out, length, "\nFB hold=%d publish/first-copy ms=%llu/%llu src-lit=%ux%u writer=%llx",
             hold, (unsigned long long)(publishNs / 1000000), (unsigned long long)(copyNs / 1000000),
             extent >> 16, extent & 0xffff,
             (unsigned long long)__atomic_load_n(&scanoutWriter, __ATOMIC_SEQ_CST));
}

extern "C" __attribute__((noreturn)) void native_legacy_backend_guard(unsigned slot, void *object, void *caller) {
    panic("T970 display: unsupported original backend slot=%u object=%p caller=%p frames=%u",
          slot, object, caller, completedFrames);
}

extern "C" void native_legacy_registration_observed(IOService *display) {
    __atomic_store_n(&publishedAt, mach_absolute_time(), __ATOMIC_RELAXED);
    displayPublished=1;
    IOLog("T970 display: registered %s\n", display->getMetaClass()->getClassName());
}

extern "C" void native_legacy_pm_observed(unsigned stage, IOReturn status, unsigned long ordinal) {
    IOLog("T970 display: PM stage=%u status=%x ordinal=%lu\n", stage, status, ordinal);
}

extern "C" void native_legacy_client_enter(task_t, uint32_t type) {
    note(clientsEntered); __atomic_store_n(&lastClientType,type,__ATOMIC_RELAXED);
    IOLog("T970 display: opening user client type=%u\n", type);
}

extern "C" void native_legacy_client_observed(IOReturn status, IOUserClient *) {
    note(status == kIOReturnSuccess ? clientsOpened : clientsFailed);
    __atomic_store_n(&lastClientStatus,(uint32_t)status,__ATOMIC_RELAXED);
    IOLog("T970 display: user client status=%x\n", status);
}

extern "C" void native_legacy_swap_validation_observed(bool accepted, unsigned reason, const void *, const void *) {
    note(accepted ? swapsAccepted : swapsRejected);
    __atomic_store_n(&lastSwapReason,reason,__ATOMIC_RELAXED);
    if (!accepted && rejectedFrames++ < 16) {
        IOLog("T970 display: rejected swap reason=%u\n", reason);
    }
}

extern "C" void native_legacy_surface_rejected(uint64_t width, uint64_t height, uint32_t format,
                                               uint32_t planes, uint64_t stride, uint64_t allocation, uint64_t bytes) {
    if (rejectedFrames < 16) {
        IOLog("T970 display: surface %llux%llu format=%x planes=%u stride=%llu allocation=%llu bytes=%llu\n",
              width, height, format, planes, stride, allocation, bytes);
    }
}

extern "C" void native_legacy_transfer_observed(IOReturn status, const void *, uint64_t bytes) {
    if (__atomic_load_n(&reportTracksScanout, __ATOMIC_ACQUIRE)) releaseScanout(thread_tid(current_thread()));
    note(transfers); __atomic_store_n(&lastTransferStatus,(uint32_t)status,__ATOMIC_RELAXED);
    if (status || completedFrames < 4) {
        IOLog("T970 display: CPU transfer status=%x bytes=%llu\n", status, bytes);
    }
}

extern "C" void native_legacy_retirement_observed(IOService *) {
    note(retired);
    ++completedFrames;
    if (completedFrames <= 4) {
        IOLog("T970 display: completed frame=%u\n", completedFrames);
    }
}

extern "C" void native_legacy_copy_timing_observed(uint64_t ticks, uint64_t bytes) {
    if (!__atomic_load_n(&firstCopyAt, __ATOMIC_RELAXED)) {
        uint64_t unset = 0;
        __atomic_compare_exchange_n(&firstCopyAt, &unset, mach_absolute_time(),
                                    false, __ATOMIC_RELAXED, __ATOMIC_RELAXED);
    }
    note(copies);
    if (completedFrames < 4) {
        IOLog("T970 display: CPU copy ticks=%llu bytes=%llu\n", ticks, bytes);
    }
}

extern "C" void native_legacy_vsync_observed(unsigned event, unsigned hz) {
    if (event < sizeof(vsyncEvents) / sizeof(vsyncEvents[0])) note(vsyncEvents[event]);
    if (event == 4 || event == 5) {
        IOLog("T970 display: refresh event=%u hz=%u\n", event, hz);
    }
}

extern "C" bool native_legacy_gpu_offer(void *, IOMemoryDescriptor *, uint64_t, uint32_t, uint32_t) {
    return false;
}

extern "C" void native_legacy_gpu_fallback_observed(int status) {
    IOLog("T970 display: CPU transfer selected status=%x\n", status);
}

extern "C" void native_legacy_swap_stage(unsigned) {
}

extern "C" void native_legacy_frame_observed(unsigned stage, uint64_t count,
                                             uint64_t minX, uint64_t minY, uint64_t maxX, uint64_t maxY) {
    if (stage || !count || maxX < minX || maxY < minY || maxX >= 2800 || maxY >= 1752) return;
    uint32_t extent = ((maxX - minX + 1) << 16) | (maxY - minY + 1);
    uint32_t unset = 0;
    __atomic_compare_exchange_n(&firstLitExtent, &unset, extent, false, __ATOMIC_RELAXED, __ATOMIC_RELAXED);
}

extern "C" void native_legacy_frame_colors_observed(const uint32_t *, const uint64_t *, uint64_t) {
}
