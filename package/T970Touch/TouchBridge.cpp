// SPDX-License-Identifier: BSD-2-Clause-Patent
//
// Feeds the STM FTS digitizer into our own HID publisher.
//
// The reference project wires the digitizer to ShengHidInput: its touch core publishes the
// finger set through the native_touch_* seqlock and calls the sink it was handed, while the
// publisher turns that into IOHIDDevice reports. ShengHidInput is a separate component whose
// build needs an ABI header generated from a pinned reference kernel we do not have, so the
// board uses package/T970Touch/TouchHid.cpp instead: it is already the owned HID publisher
// (same report layout, same class) and exposes t970_touch_hid_start/t970_touch_hid_frame.
// This file is the missing link between those two: set a sink on the digitizer, convert the
// published frame back into sensor space and hand it to the publisher.
#include "TouchHid.h"
#include <IOKit/IOLib.h>
#include <pexpert/pexpert.h>
#include <kern/thread.h>

bool touchProbeStart();

extern "C" {
void native_touch_set_sink(void (*sink)(void *), void *context);
extern volatile uint32_t native_touch_seq, native_touch_count;
extern volatile int native_touch_xs[12], native_touch_ys[12], native_touch_ids[12];
extern volatile uint32_t native_touch_fail_step;
extern volatile int native_touch_stage_result;
extern volatile unsigned native_touch_stage_value, native_touch_stage_total;
extern char native_touch_stage_name[32];
}

namespace {

// The seqlock carries frame buffer coordinates scaled along the panel's long side (x 0..30480,
// y 0..20320); the publisher's coordinates() expects the sensor's own 1751 x 2799 space and
// applies t970-touch-xform itself. Undo the swap and the scaling, nothing else.
void forward(void *)
{
    const uint32_t first = native_touch_seq;
    if (first & 1) {
        return;
    }
    unsigned count = native_touch_count;
    if (count > t970TouchSlots) {
        count = t970TouchSlots;
    }
    T970TouchFrame frame;
    for (unsigned i = 0; i < count; ++i) {
        const int id = native_touch_ids[i];
        if (id < 0 || id >= static_cast<int>(t970TouchSlots)) {
            continue;
        }
        const unsigned longX = static_cast<unsigned>(native_touch_xs[i]);
        const unsigned longY = static_cast<unsigned>(native_touch_ys[i]);
        frame.x[id] = static_cast<uint16_t>(longY * 1752u / 20320u);
        frame.y[id] = static_cast<uint16_t>(longX * 2800u / 30480u);
        frame.active |= static_cast<uint16_t>(1u << id);
    }
    if (native_touch_seq != first) {
        return;
    }
    frame.down = frame.active;
    t970_touch_hid_frame(frame);
}

}  // namespace

namespace {
volatile unsigned diagHidRefused;

void diagWatchdog(void *, wait_result_t)
{
    IOSleep(12000);
    panic("T970 touch: step=%u last=%s value=%x rc=%d hid=%u frames=%u",
          (unsigned)native_touch_fail_step, native_touch_stage_name,
          (unsigned)native_touch_stage_value, (int)native_touch_stage_result,
          (unsigned)diagHidRefused, (unsigned)native_touch_count);
}
}  // namespace

extern "C" void t970_touch_bridge_start(void)
{
    thread_t diag = nullptr;
    if (kernel_thread_start(diagWatchdog, nullptr, &diag) == KERN_SUCCESS) {
        thread_deallocate(diag);
    }
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-touch-hid", &enabled, sizeof(enabled)) || enabled != 1) {
        return;
    }
    // Keep the booting order: the HID publisher is loaded first, exactly as in the image that
    // reaches the home screen, but a refusal no longer stops the digitizer from starting.
    const bool hid = t970_touch_hid_start();
    if (!hid) {
        diagHidRefused = 1;
        IOLog("T970 touch: HID publisher start refused\n");
    }
    native_touch_set_sink(forward, nullptr);
    if (!touchProbeStart()) {
        IOLog("T970 touch: FTS core refused to start\n");
    }
}
