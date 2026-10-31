#!/usr/bin/env python3
"""Collect the SM-T970 UFS hardware inputs from the captured device evidence.

Sources: the live device tree captured over ADB (controller, PHY, clocks,
resets, supplies), the GPT snapshot for the four LUNs, and the Qualcomm kona
clock/reset ID headers. Writes a JSON inventory; it enables nothing and talks
to no device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE / 'scripts'))
sys.path.insert(0, str(DEVICE.parent / 'UniXNU/scripts'))
from unixnu import devicetree as dt  # noqa: E402

# UFS-related IDs from include/dt-bindings/clock/qcom,gcc-kona.h and
# include/dt-bindings/clock/qcom,rpmh.h of the LineageOS sm8250 kernel.
GCC_UFS_CLOCKS = {
    4: 'GCC_AGGRE_UFS_CARD_AXI_CLK', 5: 'GCC_AGGRE_UFS_CARD_AXI_HW_CTL_CLK',
    6: 'GCC_AGGRE_UFS_PHY_AXI_CLK', 7: 'GCC_AGGRE_UFS_PHY_AXI_HW_CTL_CLK',
    149: 'GCC_UFS_1X_CLKREF_EN', 150: 'GCC_UFS_CARD_AHB_CLK',
    151: 'GCC_UFS_CARD_AXI_CLK', 152: 'GCC_UFS_CARD_AXI_CLK_SRC',
    153: 'GCC_UFS_CARD_AXI_HW_CTL_CLK', 154: 'GCC_UFS_CARD_ICE_CORE_CLK',
    155: 'GCC_UFS_CARD_ICE_CORE_CLK_SRC', 156: 'GCC_UFS_CARD_ICE_CORE_HW_CTL_CLK',
    157: 'GCC_UFS_CARD_PHY_AUX_CLK', 158: 'GCC_UFS_CARD_PHY_AUX_CLK_SRC',
    159: 'GCC_UFS_CARD_PHY_AUX_HW_CTL_CLK', 160: 'GCC_UFS_CARD_RX_SYMBOL_0_CLK',
    161: 'GCC_UFS_CARD_RX_SYMBOL_1_CLK', 162: 'GCC_UFS_CARD_TX_SYMBOL_0_CLK',
    163: 'GCC_UFS_CARD_UNIPRO_CORE_CLK', 164: 'GCC_UFS_CARD_UNIPRO_CORE_CLK_SRC',
    165: 'GCC_UFS_CARD_UNIPRO_CORE_HW_CTL_CLK', 166: 'GCC_UFS_PHY_AHB_CLK',
    167: 'GCC_UFS_PHY_AXI_CLK', 168: 'GCC_UFS_PHY_AXI_CLK_SRC',
    169: 'GCC_UFS_PHY_AXI_HW_CTL_CLK', 170: 'GCC_UFS_PHY_ICE_CORE_CLK',
    171: 'GCC_UFS_PHY_ICE_CORE_CLK_SRC', 172: 'GCC_UFS_PHY_ICE_CORE_HW_CTL_CLK',
    173: 'GCC_UFS_PHY_PHY_AUX_CLK', 174: 'GCC_UFS_PHY_PHY_AUX_CLK_SRC',
    175: 'GCC_UFS_PHY_PHY_AUX_HW_CTL_CLK', 176: 'GCC_UFS_PHY_RX_SYMBOL_0_CLK',
    177: 'GCC_UFS_PHY_RX_SYMBOL_1_CLK', 178: 'GCC_UFS_PHY_TX_SYMBOL_0_CLK',
    179: 'GCC_UFS_PHY_UNIPRO_CORE_CLK', 180: 'GCC_UFS_PHY_UNIPRO_CORE_CLK_SRC',
    181: 'GCC_UFS_PHY_UNIPRO_CORE_HW_CTL_CLK',
}
GCC_UFS_RESETS = {32: 'GCC_UFS_CARD_BCR', 33: 'GCC_UFS_PHY_BCR'}
RPMH_CLOCKS = {0: 'RPMH_CXO_CLK', 1: 'RPMH_CXO_CLK_A'}

# ShengUfs e2b32cc4 is scoped to SM8550; these are its hard-coded facts.
SHENG = {'controller_base': 0x1d84000, 'controller_size': 0x3000,
         'phy_base': 0x1d80000, 'phy_size': 0x2000, 'stream_id': 0x60,
         'gcc_base': 0x100000}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-dts', type=Path,
                        default=DEVICE / 'evidence/adb-2026-11-01/live-device-tree.dts')
    parser.add_argument('--gpt', type=Path, default=DEVICE / 'evidence/adb-2026-11-01/gpt.json')
    parser.add_argument('--gcc-header', type=Path, help='qcom,gcc-kona.h for ID cross-check')
    parser.add_argument('--rpmh-header', type=Path, help='qcom,rpmh.h for ID cross-check')
    parser.add_argument('--output', type=Path, default=DEVICE / 'evidence/storage/board-inputs.json')
    args = parser.parse_args()

    blob = subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', str(args.live_dts)],
                          capture_output=True, check=True).stdout
    tree = dt.read_fdt(blob)
    nodes = {node.name: node for node in tree.walk()}
    phandles = {dt.number(node.cells('phandle')): node.name
                for node in tree.walk() if 'phandle' in node.properties}

    def ranges(node):
        return [f'0x{base:x}+0x{size:x}' for base, size in dt.registers(node)]

    controller = nodes['ufshc@1d84000']
    phy = nodes['ufsphy_mem@1d87000']
    interrupts = controller.cells('interrupts')
    clock_names = controller.strings('clock-names')
    clock_cells = controller.cells('clocks')
    clocks = []
    for index, name in enumerate(clock_names):
        provider, clock_id = clock_cells[index * 2:index * 2 + 2]
        provider_name = phandles[provider]
        table = GCC_UFS_CLOCKS if provider_name == 'qcom,gcc@100000' else RPMH_CLOCKS
        clocks.append({'name': name, 'provider': provider_name, 'id': clock_id,
                       'mapping': table.get(clock_id, 'UNKNOWN')})
    reset_cells = controller.cells('resets')
    resets = []
    for index, name in enumerate(controller.strings('reset-names')):
        provider, reset_id = reset_cells[index * 2:index * 2 + 2]
        resets.append({'name': name, 'provider': phandles[provider], 'id': reset_id,
                       'mapping': GCC_UFS_RESETS.get(reset_id, 'UNKNOWN')})
    supplies = {}
    for prop in ('vdd-hba-supply', 'vcc-supply', 'vccq-supply', 'vccq2-supply',
                 'qcom,vddp-ref-clk-supply', 'qcom,vccq-parent-supply'):
        if prop in controller.properties:
            supplies[prop] = phandles[dt.number(controller.cells(prop))]
    phy_supplies = {}
    for prop in ('vdda-phy-supply', 'vdda-pll-supply'):
        if prop in phy.properties:
            phy_supplies[prop] = phandles[dt.number(phy.cells(prop))]

    gpt = json.loads(args.gpt.read_text())
    luns = {}
    for disk, info in gpt.items():
        partitions = {p['name']: p for p in info['partitions']}
        luns[disk] = {
            'logical_block_size': info['logical_block_size'],
            'partitions': len(info['partitions']),
            'gpt_crc_valid': info['primary_header_crc_valid'] and info['entry_array_crc_valid'],
            'scsi_path': info['scsi_path'],
            'userdata': (partitions.get('userdata') or {}).get('first_lba'),
            'last_lba': max(p['last_lba'] for p in info['partitions']),
            'key_partitions': {name: {'first_lba': partitions[name]['first_lba'],
                                      'size_bytes': partitions[name]['size_bytes']}
                               for name in ('boot', 'dtbo', 'recovery', 'super', 'userdata')
                               if name in partitions},
        }
    userdata = luns['sda']['key_partitions']['userdata']
    ufs_iface = gpt['sda']['scsi_path']
    assert '1d84000.ufshc' in ufs_iface

    headers = {}
    if args.gcc_header:
        derived_clocks, derived_resets = {}, {}
        for line in args.gcc_header.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == '#define':
                target = derived_resets if parts[1].endswith('_BCR') else derived_clocks
                target[int(parts[2])] = parts[1]
        for table, derived, label in ((GCC_UFS_CLOCKS, derived_clocks, 'clock'),
                                      (GCC_UFS_RESETS, derived_resets, 'reset')):
            for key, value in table.items():
                assert derived.get(key) == value, ('gcc', label, key, derived.get(key), value)
        headers['gcc'] = {'sha256': sha256(args.gcc_header),
                          'clocks_verified': len(GCC_UFS_CLOCKS),
                          'resets_verified': len(GCC_UFS_RESETS)}
    if args.rpmh_header:
        derived = {}
        for line in args.rpmh_header.read_text().splitlines():
            parts = line.split()
            if len(parts) == 3 and parts[0] == '#define':
                derived[int(parts[2])] = parts[1]
        for key, value in RPMH_CLOCKS.items():
            assert derived.get(key) == value, ('rpmh', key, derived.get(key), value)
        headers['rpmh'] = {'sha256': sha256(args.rpmh_header),
                           'clocks_verified': len(RPMH_CLOCKS)}

    # Compatibility with the only catalog storage driver (SM8550-scoped).
    compat = {
        'driver': {'id': 'ShengUfs', 'revision': 'e2b32cc429e8cf1501161c1d8c517f8994ceb9b2',
                   'scope': 'SM8550 UFS controller'},
        'controller_base_matches': SHENG['controller_base'] == dt.registers(controller)[0][0],
        'controller_size_matches': SHENG['controller_size'] == dt.registers(controller)[0][1],
        'phy_base_matches': SHENG['phy_base'] == dt.registers(phy)[0][0],
        'phy_size_matches': SHENG['phy_size'] == dt.registers(phy)[0][1],
        'stock_iommus_present': 'iommus' in controller.properties,
        'sheng_stream_id': SHENG['stream_id'],
        'gcc_controller_present': 'qcom,gcc@100000' in phandles.values(),
        'lanes_per_direction': dt.number(controller.cells('lanes-per-direction')),
        'selected': False,
        'reason': 'ShengUfs hard-codes the SM8550 PHY window, SM8550 clock/reset policy and a '
                  'fixed apps-SMMU stream; this board has a different PHY window, an ICE block, '
                  'no iommus property and its own userdata geometry.',
    }
    required = [
        'Port the controller bring-up to qcom,ufshc + QMP PHY v4 at 0x1d87000/0xe000 with the '
        'UFS_PHY clock/reset ids above, or document a firmware-state takeover.',
        'Decide SMMU ownership: the stock DT has no iommus property, so stream/context ownership '
        'must be read from firmware or the kernel driver, not copied from sheng stream 0x60.',
        'Implement ICE handling for the 0x1d90000/0x8000 block or prove it can stay disabled.',
        'Recompute the userdata/root window from this GPT instead of sheng LBA 3094592..64007162.',
        'Provide the storage ABI inputs, archive recipe and root-volume policy, then build a kernel.',
    ]
    report = {
        'scope': 'SM-T970 UFS hardware inventory from captured evidence; no device access',
        'sources': {'live_dts': str(args.live_dts.relative_to(DEVICE)),
                    'gpt': str(args.gpt.relative_to(DEVICE)), 'headers': headers},
        'controller': {'node': controller.name, 'compatible': controller.strings('compatible'),
                       'reg': ranges(controller), 'reg_names': controller.strings('reg-names'),
                       'interrupts': [interrupts[i:i + 3] for i in range(0, len(interrupts), 3)],
                       'lanes_per_direction': dt.number(controller.cells('lanes-per-direction')),
                       'dev_ref_clk_freq': dt.number(controller.cells('dev-ref-clk-freq')),
                       'pinctrl': controller.strings('pinctrl-names')},
        'phy': {'node': phy.name, 'compatible': phy.strings('compatible'), 'reg': ranges(phy),
                'reg_names': phy.strings('reg-names'),
                'lanes_per_direction': dt.number(phy.cells('lanes-per-direction')),
                'clocks': phy.strings('clock-names')},
        'clocks': clocks, 'resets': resets,
        'supplies': supplies, 'phy_supplies': phy_supplies,
        'gpt': {'luns': luns, 'userdata_first_lba': userdata['first_lba'],
                'userdata_size_bytes': userdata['size_bytes'], 'ufs_interface': ufs_iface},
        'compatibility': compat, 'required_work': required,
        'result': 'inventory-only; storage driver not selected and UFS stays disabled',
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print('wrote', args.output)
    print('controller', ranges(controller), 'phy', ranges(phy))
    print('clocks', [(c['name'], c['mapping']) for c in clocks])
    print('compat: phy_base_matches', compat['phy_base_matches'],
          'iommus', compat['stock_iommus_present'])


if __name__ == '__main__':
    main()
