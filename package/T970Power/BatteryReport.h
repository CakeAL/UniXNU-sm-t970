// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

// Implemented in the board battery archive (BatteryService.cpp). The display
// report only formats the last committed sample; it does not touch the bus.
extern "C" bool t970_battery_report(char *out, unsigned length);
extern "C" void t970_battery_start(void);
