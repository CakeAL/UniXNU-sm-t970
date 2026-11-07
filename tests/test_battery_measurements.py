"""Gauge wire encodings and missing-data handling, using explicit numeric vectors."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Measurements(unittest.TestCase):
    def test_measurement_vectors(self):
        code = r'''
#include "package/T970Power/Max77705Measurements.h"
#include <assert.h>
#include <string.h>
int main(void) {
    struct t970_battery_measurements m = {0};
    const uint8_t vcell[] = {0x80,0xd4}; /* 4250 mV */
    const uint8_t soc[] = {0x80,0x4b};   /* 75.5 percent */
    const uint8_t charge[] = {0,1};     /* +200 mA for this board's scale */
    const uint8_t discharge[] = {0,0xfe}; /* -400 mA */
    const uint8_t warm[] = {0x80,0x19}; /* 25.5 C */
    const uint8_t cold[] = {0x80,0xfa}; /* -5.5 C, two's complement */
    const uint8_t capacity[] = {0xc4,0x0f}; /* 4036 units -> 10090 mAh */
    const uint8_t absent[] = {8,0}, present[] = {0,0};
    assert(m.valid == 0); /* Missing readings are not zero-valued measurements. */
    assert(t970_battery_word(&m, 9, vcell, 2) && m.voltage_uv == 4250000);
    assert(t970_battery_word(&m, 6, soc, 2) && m.percent_x100 == 7550);
    assert(t970_battery_word(&m, 10, charge, 2) && m.current_ua == 200000);
    assert(t970_battery_word(&m, 10, discharge, 2) && m.current_ua == -400000);
    assert(t970_battery_word(&m, 8, warm, 2) && m.temperature_mc == 25500);
    assert(t970_battery_word(&m, 8, cold, 2) && m.temperature_mc == -5500);
    assert(t970_battery_word(&m, 16, capacity, 2) && m.full_mah == 10090);
    assert(t970_battery_word(&m, 5, capacity, 2) && m.remaining_mah == 10090);
    assert(t970_battery_word(&m, 0, absent, 2) && !m.present);
    assert(t970_battery_word(&m, 0, present, 2) && m.present);
    assert(m.valid == 127);
    struct t970_battery_measurements before = m;
    assert(!t970_battery_word(&m, 9, vcell, 1));
    assert(!t970_battery_word(&m, 9, 0, 2));
    assert(!t970_battery_word(&m, 0x1d, capacity, 2)); /* Config not a measurement. */
    assert(!memcmp(&before, &m, sizeof m));
    const uint8_t max_soc[] = {0xff,0xff};
    assert(t970_battery_word(&m, 6, max_soc, 2) && m.percent_x100 == 10000);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'gauge.c'
            binary = Path(tmp) / 'gauge'
            source.write_text(code)
            subprocess.run(['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-I', str(ROOT),
                            str(source), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    unittest.main()
