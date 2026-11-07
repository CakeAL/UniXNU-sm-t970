// SPDX-License-Identifier: MIT
// SM8250 GPU power-rail inventory through the always-on ARC cmd-db block.
// The parser is adapted from lmi-gpu-resources.c (Fsasdddd/lmi-uefi-touch-gpu,
// MIT); it performs no RPMh request and writes no register.
#pragma once
#include <stdint.h>
#include "../T970Touch/BusSnapshot.h"

namespace t970_gpu {

struct ArcResource {
    bool valid = false;
    uint32_t address = 0;
    unsigned levels = 0;
    unsigned minSvs = 0;
    uint16_t first = 0;
    uint16_t last = 0;
};

static inline uint32_t arcLe16(const volatile uint8_t *p) {
    return p[0] | (uint32_t(p[1]) << 8);
}
static inline uint32_t arcLe32(const volatile uint8_t *p) {
    return arcLe16(p) | (arcLe16(p + 2) << 16);
}

// The cmd-db header is 8 bytes plus eight 16-byte section headers. Resource
// entries are 24 bytes; the aux table holds little-endian voltage-corner
// codes, strictly increasing with a zero first entry.
static bool parseArc(const volatile uint8_t *db, uint32_t bytes, const char *id,
                     ArcResource &out) {
    if (!db || bytes < 144 || arcLe32(db + 4) != 0x0c0330db) return false;
    unsigned found = 0;
    for (unsigned section = 0; section < 8; ++section) {
        const volatile uint8_t *h = db + 8 + 16 * section;
        if (arcLe16(h) != 3) continue;
        uint32_t at = 144 + arcLe16(h + 2);
        uint32_t count = arcLe16(h + 6);
        uint32_t data = 144 + arcLe16(h + 4);
        if (count > 512 || at > bytes || count > (bytes - at) / 24) return false;
        for (unsigned i = 0; i < count; ++i) {
            const volatile uint8_t *e = db + at + 24 * i;
            bool equal = true;
            for (unsigned k = 0; k < 8; ++k) equal &= e[k] == static_cast<uint8_t>(id[k]);
            if (!equal) continue;
            if (found++) return false;
            uint32_t length = arcLe16(e + 20);
            uint32_t aux = data + arcLe16(e + 22);
            out.address = arcLe32(e + 16);
            if (!out.address || (out.address & 3u) || ((out.address >> 16) & 7u) != 3u ||
                !length || length > 32 || (length & 1u) ||
                aux > bytes || length > bytes - aux) return false;
            unsigned padding = 0;
            out.levels = 0;
            for (unsigned n = 0; n < length / 2; ++n) {
                uint32_t level = arcLe16(db + aux + 2 * n);
                if (!n && level) return false;
                if (n && !level) padding = 1;
                if (padding) { if (level) return false; continue; }
                if (n && level <= out.last) return false;
                if (!out.levels) out.first = static_cast<uint16_t>(level);
                out.last = static_cast<uint16_t>(level);
                ++out.levels;
                if (level >= 48 && !out.minSvs) out.minSvs = n;
            }
            if (out.levels < 2 || !out.minSvs) return false;
            out.valid = true;
        }
    }
    return found == 1 && out.valid;
}

// Read-only: the ARC block is already mapped by the touch/RSC path on this board.
static void reportArc(char *out, unsigned length) {
    using namespace t970_touch;
    auto db = mapMmio(0x80860000, 0x20000);
    if (!db || !db->getVirtualAddress()) {
        snprintf(out, length, "\nGPU arc: mapping failed");
        return;
    }
    const volatile uint8_t *bytes = reinterpret_cast<const volatile uint8_t *>(db->getVirtualAddress());
    ArcResource cx, mx;
    bool ok = parseArc(bytes, 0x20000, "cx.lvl\0", cx) &&
              parseArc(bytes, 0x20000, "mx.lvl\0", mx) && cx.address != mx.address;
    if (!ok) {
        snprintf(out, length, "\nGPU arc: refused cx=%d/%x mx=%d/%x",
                 cx.valid ? 1 : 0, cx.address, mx.valid ? 1 : 0, mx.address);
        return;
    }
    snprintf(out, length,
             "\nGPU arc db=%x cx=%x lv=%u min=%u mx=%x lv=%u min=%u",
             arcLe32(bytes), cx.address, cx.levels, cx.minSvs, mx.address, mx.levels, mx.minSvs);
}

} // namespace t970_gpu
