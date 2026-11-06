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
