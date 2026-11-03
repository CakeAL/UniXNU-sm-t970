// SPDX-License-Identifier: BSD-2-Clause-Patent
// Lifecycle adapted from unixnu-sm-t733@3bb0d6f, T733Display/KeyStoreRegistration.cpp.
// State callbacks follow UniXNU-umi@3eb7257, legacy-display/KeyStoreProbe.cpp.
// This board uses only the catalog's unchanged RAM-fixture state service.
#include <IOKit/IOService.h>
#include <IOKit/IODeviceTreeSupport.h>
#include <IOKit/IOLib.h>
#include <libkern/c++/OSData.h>
#include <libkern/c++/OSSymbol.h>
#include <mach/kmod.h>
#include <pexpert/pexpert.h>

extern "C" kmod_info_t g_kernel_kmod_info;
extern "C" void keyStoreStaticInit(void) __asm__("__GLOBAL__sub_I_NativeKeyStoreEvents.cpp");
extern "C" IOService *native_keyevents_allocate(void);
static IOService *keyService;
static bool attempted;
static unsigned stage, opens, refused, calls, lastSelector, lastResult;
static int metaStatus = -1;

static bool argument(const char *name) {
    unsigned value = 0;
    return PE_parse_boot_argn(name, &value, sizeof(value)) && value == 1;
}

extern "C" bool native_aks_state_enabled(void) {
    // Reject state answers until this board has qualified the RAM-only environment.
    return keyService && argument("sheng-aks") && argument("offline-key-events");
}
extern "C" uint32_t native_aks_lock_state(void) { return 3; }
extern "C" void native_keyevents_open_refused(void) {
    __atomic_fetch_add(&refused, 1, __ATOMIC_RELAXED);
}
extern "C" void native_aks_opened(void) {
    __atomic_fetch_add(&opens, 1, __ATOMIC_RELAXED);
}
extern "C" void native_aks_call(uint32_t selector, int32_t result) {
    __atomic_store_n(&lastSelector, selector, __ATOMIC_RELAXED);
    __atomic_store_n(&lastResult, (unsigned)result, __ATOMIC_RELAXED);
    __atomic_fetch_add(&calls, 1, __ATOMIC_RELAXED);
}
extern "C" void native_t970_keystore_state(char *out, unsigned length) {
    if (!out || !length) return;
    snprintf(out, length, "\nkey-state stage=%u meta=%d ready=%u open/refused/calls=%u/%u/%u sel=%u rc=%x",
             stage, metaStatus, keyService ? 1U : 0U,
             __atomic_load_n(&opens, __ATOMIC_RELAXED), __atomic_load_n(&refused, __ATOMIC_RELAXED),
             __atomic_load_n(&calls, __ATOMIC_RELAXED), __atomic_load_n(&lastSelector, __ATOMIC_RELAXED),
             __atomic_load_n(&lastResult, __ATOMIC_RELAXED));
}

extern "C" void t970_keystore_start(void) {
    if (attempted || !argument("offline-key-events") || !argument("sheng-aks")) return;
    attempted = true;
    stage = 1;
    IORegistryEntry *chosen = IORegistryEntry::fromPath("/chosen", gIODTPlane);
    uint32_t ephemeral = 0;
    OSData *data = chosen ? OSDynamicCast(OSData, chosen->getProperty("ephemeral-storage")) : nullptr;
    if (data && data->getLength() == sizeof(ephemeral))
        memcpy(&ephemeral, data->getBytesNoCopy(), sizeof(ephemeral));
    OSSafeReleaseNULL(chosen);
    if (ephemeral != 1) return;

    stage = 2;
    const OSSymbol *name = OSSymbol::withCString("AppleKeyStore");
    if (!name) return;
    bool exists = OSMetaClass::getMetaClassWithName(name);
    OSSafeReleaseNULL(name);
    if (exists) return;
    IOService *provider = IOService::getResourceService();
    void *handle = provider ? OSMetaClass::preModLoad(g_kernel_kmod_info.name) : nullptr;
    if (!handle) return;
    keyStoreStaticInit();
    metaStatus = OSMetaClass::postModLoad(handle);
    if (metaStatus) return;

    stage = 3;
    IOService *service = native_keyevents_allocate();
    bool attached = service && service->init() && service->attach(provider);
    // Set the qualified service before start publishes it to matching clients.
    keyService = attached ? service : nullptr;
    bool started = attached && service->start(provider);
    if (!started) {
        keyService = nullptr;
        if (attached) service->detach(provider);
        OSSafeReleaseNULL(service);
        return;
    }
    stage = 4;
    IOLog("T970 RAM key state: service ready (state queries only)\n");
}
