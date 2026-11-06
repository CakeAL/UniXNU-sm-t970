// SPDX-License-Identifier: BSD-2-Clause-Patent
// Adapted from SM-T733 T733TouchHidABI.h at 3bb0d6f7840f088db6a0ec88ecb841e12042422f.
#pragma once
#include <IOKit/IOService.h>
#include <IOKit/IOMemoryDescriptor.h>

/* IOHIDDevice describes the 208-byte, 207-slot original IOHIDFamily device used by NativeHidInput. */
class IOHIDDevice : public IOService {
    OSDeclareAbstractStructors(IOHIDDevice)
    unsigned char originalPrivate[0xd0 - sizeof(IOService)];

public:
    using IOService::setProperty;
    IOReturn Dispatch(IORPC) override;
    void free() override;
    bool init(OSDictionary *properties = nullptr) override;
    bool setProperty(const OSSymbol *, OSObject *) override;
    bool willTerminate(IOService *, IOOptionBits) override;
    IOReturn configureReport(IOReportChannelList *, IOReportConfigureAction, void *, void *) override;
    IOReturn updateReport(IOReportChannelList *, IOReportUpdateAction, void *, void *) override;
    bool start(IOService *) override;
    void stop(IOService *) override;
    bool handleOpen(IOService *, IOOptionBits, void *) override;
    void handleClose(IOService *, IOOptionBits) override;
    bool handleIsOpen(const IOService *) const override;
    bool matchPropertyTable(OSDictionary *, SInt32 *) override;
    IOReturn message(UInt32, IOService *, void *) override;
    IOReturn newUserClient(task_t, void *, UInt32, OSDictionary *, IOUserClient **) override;

#define T970_HID_SLOT(number) virtual void opaque##number();
    T970_HID_SLOT(168)
    T970_HID_SLOT(169)
    T970_HID_SLOT(170)
    virtual OSString *newTransportString() const;
    T970_HID_SLOT(172)
    virtual OSString *newProductString() const;
    T970_HID_SLOT(174)
    T970_HID_SLOT(175)
    T970_HID_SLOT(176)
    T970_HID_SLOT(177)
    T970_HID_SLOT(178)
    T970_HID_SLOT(179)
    virtual IOReturn newReportDescriptor(IOMemoryDescriptor **) const = 0;
    virtual IOReturn handleReport(IOMemoryDescriptor *, unsigned, IOOptionBits);
    T970_HID_SLOT(182)
    T970_HID_SLOT(183)
    T970_HID_SLOT(184)
    T970_HID_SLOT(185)
    T970_HID_SLOT(186)
    T970_HID_SLOT(187)
    T970_HID_SLOT(188)
    T970_HID_SLOT(189)
    T970_HID_SLOT(190)
    T970_HID_SLOT(191)
    T970_HID_SLOT(192)
    T970_HID_SLOT(193)
    T970_HID_SLOT(194)
    T970_HID_SLOT(195)
    T970_HID_SLOT(196)
    T970_HID_SLOT(197)
    T970_HID_SLOT(198)
    T970_HID_SLOT(199)
    T970_HID_SLOT(200)
    T970_HID_SLOT(201)
    T970_HID_SLOT(202)
    T970_HID_SLOT(203)
    T970_HID_SLOT(204)
    T970_HID_SLOT(205)
    T970_HID_SLOT(206)
#undef T970_HID_SLOT
};

static_assert(sizeof(IOHIDDevice) == 0xd0, "Original IOHIDDevice instance size");
