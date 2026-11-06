"""Actual SPMI key protocol against a software model of the version-5 arbiter."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

HARNESS = r'''
#include "package/T970Input/KeyProbeCore.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint32_t core[0x2000/4], cnfg[0x2000/4], obs[0x2000/4];

static void clear(void) { memset(core, 0, sizeof core); memset(cnfg, 0, sizeof cnfg); memset(obs, 0, sizeof obs); }
static uint32_t *map(uint32_t apid) { return &core[(T970_ARB_V5_APID_MAP + 4*apid)/4]; }
static uint32_t *owner(uint32_t apid) { return &cnfg[(T970_ARB_V5_OWNER + 4*apid)/4]; }
static uint32_t *channel(uint32_t apid) { return &obs[(T970_ARB_OBS_STRIDE*apid)/4]; }

int main(void) {
    struct t970_arbiter a = {core, cnfg, obs, 0};
    uint32_t version = 0, count = 0, apid = 0, value = 0;

    clear();
    core[0] = T970_ARB_V5_MIN;
    assert(t970_arb_version(&a, &version) == 0 && version == T970_ARB_V5_MIN);
    core[0] = T970_ARB_V7_MIN;
    assert(t970_arb_version(&a, &version) == 1);

    clear();
    core[0] = T970_ARB_V5_MIN;
    core[T970_ARB_FEATURES/4] = 0x10;
    assert(t970_arb_apids(&a, &count) == 0 && count == 0x10 && a.apids == 0x10);
    core[T970_ARB_FEATURES/4] = 0;
    assert(t970_arb_apids(&a, &count) == 1);

    clear();
    core[0] = T970_ARB_V5_MIN;
    a.apids = 16;
    *map(5) = (T970_PON_PPID << 8) | (1u << 24);
    *owner(5) = 1;
    *map(9) = (T970_GPIO_PPID << 8) | (1u << 24);
    *owner(9) = 0;
    assert(t970_arb_find(&a, T970_PON_PPID, &apid) == 0 && apid == 5);
    assert(t970_arb_find(&a, T970_GPIO_PPID, &apid) == 0 && apid == 9);
    assert(t970_arb_find(&a, 0x123, &apid) == 2);

    clear();
    a.apids = 16;
    *map(9) = (T970_GPIO_PPID << 8) | (1u << 24);
    *owner(9) = 0;
    channel(9)[T970_ARB_STATUS/4] = T970_ARB_DONE;
    channel(9)[T970_ARB_RDATA/4] = 0;
    assert(t970_arb_read32(&a, 9, T970_GPIO_RT_STS, &value) == 0 && value == 0);
    assert(channel(9)[T970_ARB_CMD/4] == ((1u << 27) | (T970_GPIO_RT_STS << 4) | 3u));

    channel(9)[T970_ARB_STATUS/4] = T970_ARB_DONE | 2u;
    assert(t970_arb_read32(&a, 9, T970_GPIO_RT_STS, &value) == 2);
    channel(9)[T970_ARB_STATUS/4] = 0;
    assert(t970_arb_read32(&a, 9, T970_GPIO_RT_STS, &value) == 1);

    assert(t970_keys_mask(0, T970_GPIO_ACTIVE_LOW) == 0);
    assert(t970_keys_mask(T970_PON_POWER, T970_GPIO_ACTIVE_LOW) == 1);
    assert(t970_keys_mask(0, 0) == 2);
    assert(t970_keys_mask(T970_PON_RESIN, T970_GPIO_ACTIVE_LOW) == 4);
    assert(t970_keys_mask(T970_PON_POWER | T970_PON_RESIN, 0) == 7);

    /* Edge state: two agreeing samples are needed, so bounce is rejected. */
    struct t970_key_state k = {0};
    assert(t970_key_update(&k, 0, 1) == 0);      /* first release sample arms it */
    assert(t970_key_update(&k, 1, 1) == 0);      /* first high sample */
    assert(t970_key_update(&k, 1, 1) == 1);      /* steady: press */
    assert(k.presses == 1 && k.down == 1);
    assert(t970_key_update(&k, 1, 1) == 0);      /* held: no repeat */
    assert(t970_key_update(&k, 0, 1) == 0);      /* first low sample */
    assert(t970_key_update(&k, 0, 1) == 2);      /* steady: release */
    assert(k.releases == 1 && k.down == 0);
    /* Bounce: a single opposite sample drops the edge. */
    assert(t970_key_update(&k, 1, 1) == 0);
    assert(t970_key_update(&k, 0, 1) == 0);
    assert(t970_key_update(&k, 1, 1) == 0);
    assert(t970_key_update(&k, 1, 1) == 1);
    /* Unusable keys never change state. */
    struct t970_key_state u = {0};
    assert(t970_key_update(&u, 1, 0) == 0 && t970_key_update(&u, 1, 0) == 0);
    assert(u.presses == 0 && u.down == 0);
    /* A key already down at start is not reported as a press. */
    struct t970_key_state h = {.last = 1, .live = 0, .down = 0};
    assert(t970_key_update(&h, 1, 1) == 0);      /* steady but live=0 */
    assert(t970_key_update(&h, 0, 1) == 0);      /* first low sample */
    assert(t970_key_update(&h, 0, 1) == 0);      /* steady low arms live */
    assert(h.live == 1 && h.presses == 0);
    /* Report line. */
    struct t970_key_state line[3] = {{.presses = 1, .releases = 1}, {.releases = 1}, {0}};
    char text[256];
    t970_keys_text(text, sizeof text, 0x50000000, 8, 0x4c3, 5, line);
    assert(strcmp(text, "Keys: v=50000000 pon=8 gpio=4c3 mask=5 power=1/1 up=0/1 down=0/0") == 0);
    puts("ok");
    return 0;
}
'''


class KeyProbe(unittest.TestCase):
    def test_protocol(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'keys.c'
            binary = Path(tmp) / 'keys'
            source.write_text(HARNESS)
            subprocess.run(['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(ROOT),
                            str(source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'ok')


if __name__ == '__main__':
    unittest.main()
