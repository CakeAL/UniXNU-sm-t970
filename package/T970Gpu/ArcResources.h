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
    uint16_t level[16] = {};
};

static inline uint32_t arcLe16(const volatile uint8_t *p) {
    return p[0] | (uint32_t(p[1]) << 8);
}
static inline uint32_t arcLe32(const volatile uint8_t *p) {
    return arcLe16(p) | (arcLe16(p + 2) << 16);
}

struct CmdDbResource {
    const volatile uint8_t *entry = nullptr;
    uint32_t auxBase = 0;
};

// The command DB has eight 16-byte section headers and 24-byte resources.
static CmdDbResource findCmdDbResource(const volatile uint8_t *db, uint32_t bytes,
                                       unsigned slave, const char *id) {
    if (!db || bytes < 144 || arcLe32(db + 4) != 0x0c0330db) return {};
    CmdDbResource found;
    for (unsigned section = 0; section < 8; ++section) {
        const volatile uint8_t *h = db + 8 + 16 * section;
        if (arcLe16(h) != slave) continue;
        const uint32_t at = 144 + arcLe16(h + 2);
        const uint32_t count = arcLe16(h + 6);
        if (count > 512 || at > bytes || count > (bytes - at) / 24) return {};
        for (unsigned i = 0; i < count; ++i) {
            const volatile uint8_t *e = db + at + 24 * i;
            bool equal = true;
            for (unsigned k = 0; k < 8; ++k) equal &= e[k] == static_cast<uint8_t>(id[k]);
            if (!equal) continue;
            if (found.entry) return {};
            found = {e, 144 + arcLe16(h + 4)};
        }
    }
    return found;
}

// ARC aux data holds little-endian corner codes starting with a zero entry.
static bool parseArc(const volatile uint8_t *db, uint32_t bytes, const char *id,
                     ArcResource &out) {
    const auto resource = findCmdDbResource(db, bytes, 3, id);
    const auto *e = resource.entry;
    if (!e) return false;
    const uint32_t length = arcLe16(e + 20);
    const uint32_t aux = resource.auxBase + arcLe16(e + 22);
    out.address = arcLe32(e + 16);
    if (!out.address || (out.address & 3u) || ((out.address >> 16) & 7u) != 3u ||
        !length || length > 32 || (length & 1u) ||
        aux > bytes || length > bytes - aux) return false;
    bool padding = false;
    out.levels = 0;
    for (unsigned n = 0; n < length / 2; ++n) {
        const uint32_t level = arcLe16(db + aux + 2 * n);
        if (!n && level) return false;
        if (n && !level) padding = true;
        if (padding) { if (level) return false; continue; }
        if (n && level <= out.last) return false;
        if (!out.levels) out.first = static_cast<uint16_t>(level);
        out.last = static_cast<uint16_t>(level);
        out.level[out.levels] = static_cast<uint16_t>(level);
        ++out.levels;
        if (level >= 48 && !out.minSvs) out.minSvs = n;
    }
    if (out.levels < 2 || !out.minSvs) return false;
    out.valid = true;
    return true;
}

static void formatArcLevels(const ArcResource &resource, char *out, unsigned length) {
    size_t used = 0;
    for (unsigned i = 0; i < resource.levels && used + 8 < length; ++i) {
        int written = snprintf(out + used, length - used, i ? ",%u" : "%u", resource.level[i]);
        if (written <= 0) break;
        used += static_cast<size_t>(written);
    }
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
    char cxList[64] = {}, mxList[64] = {};
    formatArcLevels(cx, cxList, sizeof(cxList));
    formatArcLevels(mx, mxList, sizeof(mxList));
    snprintf(out, length,
             "\nGPU arc db=%x cx=%x lv=%u [%s] min=%u mx=%x lv=%u [%s] min=%u",
             arcLe32(bytes), cx.address, cx.levels, cxList, cx.minSvs,
             mx.address, mx.levels, mxList, mx.minSvs);
}

} // namespace t970_gpu
