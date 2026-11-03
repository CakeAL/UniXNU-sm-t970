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
#include <machine/machine_routines.h>
#include <pexpert/pexpert.h>
#include "T970GopGeometry.h"

extern "C" { volatile uint64_t native_legacy_early_retires=0, native_legacy_early_failures=0; }

extern "C" kmod_info_t g_kernel_kmod_info;
extern "C" void displayStaticInit(void) __asm__("__GLOBAL__sub_I_NativeLegacyDisplay.cpp");
extern "C" IOService *native_legacy_display_allocate(void);
extern "C" kern_return_t OSKextLoadKextWithIdentifier(const char *);

static IOService *pendingDisplay;
static IOService *activeDisplay;
static IOPlatformDevice *activeProvider;
static bool initialized;
static bool consoleReleased;
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

    PE_Video video = {};
    if (!videoAvailable(video)) {
        IOLog("T970 display: firmware framebuffer geometry unavailable\n");
        return;
    }
    void *handle = OSMetaClass::preModLoad(g_kernel_kmod_info.name);
    if (!handle) {
        return;
    }
    displayStaticInit();
    OSReturn status = OSMetaClass::postModLoad(handle);
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
    IOLog("T970 display: initialized original Legacy, waiting for IOBSD\n");
}

extern "C" void native_legacy_display_late_probe(void) {
    IOService *display = pendingDisplay;
    if (!display) {
        return;
    }
    pendingDisplay = nullptr;

    kern_return_t load = OSKextLoadKextWithIdentifier("com.apple.iokit.IOSurface");
    OSDictionary *matching = IOService::nameMatching("IOCoreSurfaceRoot");
    IOService *surface = matching ? IOService::waitForMatchingService(matching, 5000000000ULL) : nullptr;
    bool surfaceReady = load == KERN_SUCCESS && surface;
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
        SInt32 score = 0;
        if (treeAttached && display->probe(provider, &score) == display) {
            displayAttached = display->attach(provider);
        }
        if (displayAttached) {
            displayStarted = display->start(provider);
        }
    }

    OSSafeReleaseNULL(typeData);
    OSSafeReleaseNULL(ranges);
    OSSafeReleaseNULL(memory);
    if (displayStarted) {
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
    return result;
}

extern "C" bool native_legacy_prepare_scanout(void) {
    if (!consoleReleased) {
        IOLog("T970 display: first CPU frame, releasing text console\n");
        PE_initialize_console(nullptr, kPEDisableScreen);
        consoleReleased = true;
    }
    return true;
}

extern "C" __attribute__((noreturn)) void native_legacy_backend_guard(unsigned slot, void *object, void *caller) {
    panic("T970 display: unsupported original backend slot=%u object=%p caller=%p frames=%u",
          slot, object, caller, completedFrames);
}

extern "C" void native_legacy_registration_observed(IOService *display) {
    IOLog("T970 display: registered %s\n", display->getMetaClass()->getClassName());
}

extern "C" void native_legacy_pm_observed(unsigned stage, IOReturn status, unsigned long ordinal) {
    IOLog("T970 display: PM stage=%u status=%x ordinal=%lu\n", stage, status, ordinal);
}

extern "C" void native_legacy_client_enter(task_t, uint32_t type) {
    IOLog("T970 display: opening user client type=%u\n", type);
}

extern "C" void native_legacy_client_observed(IOReturn status, IOUserClient *) {
    IOLog("T970 display: user client status=%x\n", status);
}

extern "C" void native_legacy_swap_validation_observed(bool accepted, unsigned reason, const void *, const void *) {
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
    if (status || completedFrames < 4) {
        IOLog("T970 display: CPU transfer status=%x bytes=%llu\n", status, bytes);
    }
}

extern "C" void native_legacy_retirement_observed(IOService *) {
    ++completedFrames;
    if (completedFrames <= 4) {
        IOLog("T970 display: completed frame=%u\n", completedFrames);
    }
}

extern "C" void native_legacy_copy_timing_observed(uint64_t ticks, uint64_t bytes) {
    if (completedFrames < 4) {
        IOLog("T970 display: CPU copy ticks=%llu bytes=%llu\n", ticks, bytes);
    }
}

extern "C" void native_legacy_vsync_observed(unsigned event, unsigned hz) {
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

extern "C" void native_legacy_frame_observed(unsigned, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t) {
}

extern "C" void native_legacy_frame_colors_observed(const uint32_t *, const uint64_t *, uint64_t) {
}
