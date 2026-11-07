// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <IOKit/IOLib.h>
#include <pexpert/pexpert.h>
#include <pexpert/arm64/boot.h>

static void t970MemoryHandoff(char *out, unsigned length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-memory-report", &enabled, sizeof(enabled)) || enabled != 1) return;
    if (!out || !length) return;
    const auto *args = static_cast<const boot_args *>(PE_state.bootArgs);
    if (!args || args->Version != kBootArgsVersion2) {
        snprintf(out, length, "\nMemory owned: unavailable boot_args");
        return;
    }
    snprintf(out, length, "\nMemory owned base=%llx size=%llx actual=%llx top=%llx",
        static_cast<unsigned long long>(args->physBase),
        static_cast<unsigned long long>(args->memSize),
        static_cast<unsigned long long>(args->memSizeActual),
        static_cast<unsigned long long>(args->topOfKernelData));
}
