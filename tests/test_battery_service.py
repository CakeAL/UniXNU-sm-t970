"""MAX77705 charger decode and read-only battery power-source wiring."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChargerDecode(unittest.TestCase):
    def test_measured_and_synthetic_states(self):
        model = r'''
#include <cassert>
#include <cstdint>
#include "package/T970Power/Max77705Charger.h"
int main() {
    using namespace t970_power;
    /* v94 BOOT6d5c4c60: VBUS valid but CHG_DTLS 0xB (watchdog expired). */
    uint8_t measured[3] = {0xcf, 0xe0, 0x3b};
    auto s = t970_charger_decode(measured, true);
    assert(s.valid && s.external && !s.charging && !s.full && s.watchdogExpired);
    assert(s.intOk == 0xcf && s.chginDtls == 3 && s.wcinDtls == 0 && s.chgDtls == 0x0b);
    /* Charging: CHGIN valid, CHG_DTLS 0x2. */
    uint8_t charging[3] = {0x40, 0x60, 0x02};
    auto c = t970_charger_decode(charging, true);
    assert(c.external && c.charging && !c.full && !c.watchdogExpired);
    /* Full: CHG_DTLS 0x3. */
    uint8_t full[3] = {0x40, 0x60, 0x03};
    auto f = t970_charger_decode(full, true);
    assert(f.external && !f.charging && f.full);
    /* Cable removed: CHGIN_DTLS 0, CHG_DTLS 0xB. */
    uint8_t absent[3] = {0x00, 0x00, 0x0b};
    auto a = t970_charger_decode(absent, true);
    assert(!a.external && !a.charging && a.watchdogExpired);
    /* Wireless input also counts as external power. */
    uint8_t wireless[3] = {0x20, 0x18, 0x01};
    auto w = t970_charger_decode(wireless, true);
    assert(w.external && w.charging);
    /* A failed read has no usable charger state. */
    uint8_t none[3] = {0xff, 0xff, 0xff};
    auto n = t970_charger_decode(none, false);
    assert(!n.valid && !n.external && !n.charging && !n.full && !n.watchdogExpired);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / 'charger.cpp', Path(tmp) / 'charger'
            cpp.write_text(model)
            subprocess.run(['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(ROOT), str(cpp), '-o', str(exe)],
                           check=True)
            subprocess.run([str(exe)], check=True)


class ServiceWiring(unittest.TestCase):
    def test_power_source_publication(self):
        source = (ROOT / 'package/T970Power/BatteryService.cpp').read_text()
        for needle in (
                'PE_parse_boot_argn("t970-battery"',
                'class T970Battery : public IOPMPowerSource',
                'setCurrentCapacity(', 'setMaxCapacity(',
                'setVoltage(', 'setAmperage(', 'setBatteryInstalled(',
                'setExternalConnected(', 'setIsCharging(', 'setBoolean("FullyCharged"',
                'setErrorCondition(',
                'updateStatus()',
                'registerService()',
                'readGaugeSample(sample)',
                't970_charger_decode(sample.charger, sample.chargerValid)',
                'IOSleep(kPollMilliseconds)',
                'Battery svc=1 samples=%u errors=%u published=%u age_ms=%llu',
                'OSMetaClass::preModLoad(g_kernel_kmod_info.name)',
                'OSMetaClass::postModLoad(handle)'):
            self.assertIn(needle, source)
        # The refresh is a bounded poll; the service never configures the charger.
        self.assertIn('kPollMilliseconds = 5000', source)

    def test_boot_hook_and_archive_members(self):
        patch = (ROOT / 'patches/xnu/t970-battery-power.patch').read_text()
        self.assertIn('extern void t970_battery_start(void);', patch)
        self.assertIn('t970_battery_start();', patch)
        series = (ROOT / 'patches/xnu/series').read_text().splitlines()
        self.assertEqual(series.count('t970-battery-power.patch'), 1)
        builder = (ROOT / 'scripts/build-platform-power.py').read_text()
        self.assertIn('T970Power/BatteryService.cpp', builder)
        self.assertIn('BatteryService.late.o', builder)
        self.assertIn('BatteryService.late.o', (ROOT / 'scripts/check-data-payload.py').read_text())

    def test_cached_report_does_not_touch_the_bus(self):
        bus = (ROOT / 'package/T970Power/BusSnapshot.h').read_text()
        body = bus[bus.index('static void reportBus('):bus.index('static void reportBus(') + 700]
        self.assertIn('if (enabled == 3 && t970_battery_report(out, length)) return;', body)
        self.assertLess(body.index('t970_battery_report'), body.index('mapMmio'))


if __name__ == '__main__':
    unittest.main()
