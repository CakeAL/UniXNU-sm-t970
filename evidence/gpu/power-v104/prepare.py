#!/usr/bin/env python3
"""Pack a GPU power probe from its exact baseline BOOT."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[3]
OUT = DEVICE / 'out/data-bringup'
TREE = OUT / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
PREFIX = '::/EFI/UniXNU/'
CONFIG = 'unixnu.toml'
KERNEL = 'Payloads/kernel.macho'
PRESERVED = ('Payloads/kernel.macho.adt', 'Payloads/scratch-data.img', 'Payloads/kernel.macho.trustcache')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument('--cx-pulse', action='store_true', help='Pack v105 from the tested v104 BOOT')
    variants.add_argument('--xo-clocks', action='store_true', help='Pack v106 from the tested v105 BOOT')
    variants.add_argument('--gmu-read', action='store_true', help='Pack v107 from the tested v106 BOOT')
    variants.add_argument('--rsc-read', action='store_true', help='Pack v108 from the tested v107 BOOT')
    variants.add_argument('--rsc-init', action='store_true', help='Pack v109 from the tested v108 BOOT')
    variants.add_argument('--arc-vote', action='store_true', help='Pack v110 from the tested v109 BOOT')
    variants.add_argument('--gmu-rate', action='store_true', help='Pack v111 from the tested v110 BOOT')
    variants.add_argument('--smmu-read', action='store_true', help='Pack v112 from the tested v111 BOOT')
    variants.add_argument('--cb-format', action='store_true', help='Pack v113 from the tested v112 BOOT')
    variants.add_argument('--cb-guard', action='store_true', help='Pack v114 from the tested v113 BOOT')
    variants.add_argument('--cb-restore', action='store_true', help='Pack v115 from the tested v114 BOOT')
    variants.add_argument('--gmu-tables', action='store_true', help='Pack v116 from the tested v115 BOOT')
    variants.add_argument('--cb-bar', action='store_true', help='Pack v117 from the tested v116 BOOT')
    variants.add_argument('--cb-release', action='store_true', help='Pack v118 from the tested v117 BOOT')
    variants.add_argument('--ttbr-width', action='store_true', help='Pack v119 from the tested v118 BOOT')
    variants.add_argument('--cb-root', action='store_true', help='Pack v120 from the tested v119 BOOT')
    variants.add_argument('--cb-activate', action='store_true', help='Pack v121 from the tested v120 BOOT')
    variants.add_argument('--sid5', action='store_true', help='Pack v122 from the tested v121 BOOT')
    variants.add_argument('--gmu-firmware', action='store_true', help='Pack v123 from the tested v122 BOOT')
    variants.add_argument('--gmu-boot', action='store_true', help='Pack v124 from the tested v123 BOOT')
    variants.add_argument('--gmu-boot-axi', action='store_true', help='Pack v125 from the tested v124 BOOT')
    variants.add_argument('--gmu-boot-pf', action='store_true', help='Pack v126 from the tested v125 BOOT')
    variants.add_argument('--gmu-boot-pf-fix', action='store_true', help='Pack v127 from the tested v125 BOOT')
    variants.add_argument('--gmu-boot-scratch-exec', action='store_true', help='Pack v128 from the tested v127 BOOT')
    variants.add_argument('--gmu-boot-default-inst', action='store_true', help='Pack v129 from the tested v128 BOOT')
    variants.add_argument('--gmu-hfi-version', action='store_true', help='Pack v130 from the tested v129 BOOT')
    variants.add_argument('--gmu-hfi-perf', action='store_true', help='Pack v131 from the tested v130 BOOT')
    variants.add_argument('--gmu-hfi-core', action='store_true', help='Pack v132 from the tested v131 BOOT')
    variants.add_argument('--gmu-hfi-gx', action='store_true', help='Pack v133 from the tested v132 BOOT')
    variants.add_argument('--gpu-cp-read', action='store_true', help='Pack v134 from the tested v133 BOOT')
    variants.add_argument('--gpu-cb1-format', action='store_true', help='Pack v135 from the tested v134 BOOT')
    options = parser.parse_args()
    if options.gpu_cb1_format:
        baseline = 'gpu-cp-read-v134'
        base_sha = '54cc16fa928448adb68a0bda3ffc3731d5b5b9dd92adeace5a7cdb9067174167'
        output = OUT / 'gpu-cb1-format-v135'
        old, new = b't970-gpu-p=30', b't970-gpu-p=31'
        markers = (b'GPU cp %s rbbm=', b'GPU cb1fmt %s va=')
    elif options.gpu_cp_read:
        baseline = 'gpu-hfi-gx-v133'
        base_sha = 'f6537ceddde66d65b67fdc74d5efac5df468ac2a1459750da0cdc62180d5a793'
        output = OUT / 'gpu-cp-read-v134'
        old, new = b't970-gpu-p=29', b't970-gpu-p=30'
        markers = (b'GPU cp %s rbbm=', b'GPU cb1 va=')
    elif options.gmu_hfi_gx:
        baseline = 'gpu-hfi-core-v132'
        base_sha = '3fdb8e6dc324e9b2d724c73cc1010ca1821e7bffe8d88cba72f82371fd372015'
        output = OUT / 'gpu-hfi-gx-v133'
        old, new = b't970-gpu-p=28', b't970-gpu-p=29'
        markers = (b'GPU gx %s/%s/%s echo=', b'GPU core %s cmd=')
    elif options.gmu_hfi_core:
        baseline = 'gpu-hfi-perf-v131'
        base_sha = '08365a3ad111027ea7cadb0027200b7424f3769fd80d24537ed01c692344b20a'
        output = OUT / 'gpu-hfi-core-v132'
        old, new = b't970-gpu-p=27', b't970-gpu-p=28'
        markers = (b'GPU bw %s cmd=', b'GPU core %s cmd=')
    elif options.gmu_hfi_perf:
        baseline = 'gpu-hfi-version-v130'
        base_sha = 'da0349810f6e3f64181c273502a3c6b31db78b3d6e2740b1ff97f67c2a7180a7'
        output = OUT / 'gpu-hfi-perf-v131'
        old, new = b't970-gpu-p=26', b't970-gpu-p=27'
        markers = (b'GPU fwver %s cmd=', b'GPU perf %s cmd=')
    elif options.gmu_hfi_version:
        baseline = 'gpu-gmuboot-inst-v129'
        base_sha = '866a0644d8bbba90ce7dd2caa08d78e479b36713f59bb802b59fe0650b7cb2e3'
        output = OUT / 'gpu-hfi-version-v130'
        old, new = b't970-gpu-p=25', b't970-gpu-p=26'
        markers = (b'GPU boot %s/%s fw=', b'GPU fwver %s cmd=')
    elif options.gmu_boot_default_inst:
        baseline = 'gpu-gmuboot-exec-v128'
        base_sha = '8ee0c6edbbdf3a6a6c419cef22be74c82b846b7caaacf01e9a704dca076e9c88'
        output = OUT / 'gpu-gmuboot-inst-v129'
        old, new = b't970-gpu-p=24', b't970-gpu-p=25'
        markers = (b'GPU boot %s/%s fw=', b'pf=%u s2=%x')
    elif options.gmu_boot_scratch_exec:
        baseline = 'gpu-gmuboot-pf-v127'
        base_sha = '9b6513f4350264f534e3157afe62260fa8d27fabf5fa060b8a77a5460f7a94e3'
        output = OUT / 'gpu-gmuboot-exec-v128'
        old, new = b't970-gpu-p=23', b't970-gpu-p=24'
        markers = (b'GPU boot %s/%s fw=', b'pte=%llx/%llx fix=%c%c')
    elif options.gmu_boot_pf_fix:
        baseline = 'gpu-gmuboot-axi-v125'
        base_sha = '1cb79accad1624cd468373e8fe3421beb1ce08e8a5f076ed2b908bf40b4e38b6'
        output = OUT / 'gpu-gmuboot-pf-v127'
        old, new = b't970-gpu-p=22', b't970-gpu-p=23'
        markers = (b'GPU boot %s/%s fw=', b'GPU pf%u fsr=%x far=')
    elif options.gmu_boot_pf:
        baseline = 'gpu-gmuboot-axi-v125'
        base_sha = '1cb79accad1624cd468373e8fe3421beb1ce08e8a5f076ed2b908bf40b4e38b6'
        output = OUT / 'gpu-gmuboot-pf-v126'
        old, new = b't970-gpu-p=22', b't970-gpu-p=23'
        markers = (b'GPU boot %s/%s fw=', b'GPU pf%u fsr=%x far=')
    elif options.gmu_boot_axi:
        baseline = 'gpu-gmuboot-v124'
        base_sha = 'a5af785e63a87473fff855937a37222173e7fa9b8c82abcc8cf5f54d92d82224'
        output = OUT / 'gpu-gmuboot-axi-v125'
        old, new = b't970-gpu-p=21', b't970-gpu-p=22'
        markers = (b'GPU boot %s/%s fw=', b'held=%u axi=%x/%x/%x')
    elif options.gmu_boot:
        baseline = 'gpu-gmufw-v123'
        base_sha = '5bce7bb8a8160c67b5c5f40a4400ed3df1e225bb6d02ff2b615077d847ffba28'
        output = OUT / 'gpu-gmuboot-v124'
        old, new = b't970-gpu-p=20', b't970-gpu-p=21'
        markers = (b'GPU boot %s/%s fw=', b'held=%u axi=%x\0')
    elif options.gmu_firmware:
        baseline = 'gpu-sid5-v122'
        base_sha = '1c7ea2fe56a3f61945340c5e1879a8af781b5390106db882904a3812f497838d'
        output = OUT / 'gpu-gmufw-v123'
        old, new = b't970-gpu-p=19', b't970-gpu-p=20'
        markers = (b'GPU fw %s/%s/%s tcm/ram=', b'tcm-hold')
    elif options.sid5:
        baseline = 'gpu-cbactivate-v121'
        base_sha = 'e99b0cf69823f9320f2196ef9d71580c00a2fc023c9a273ad99526c8d3b8447d'
        output = OUT / 'gpu-sid5-v122'
        old, new = b't970-gpu-p=18', b't970-gpu-p=19'
        markers = (b'GPU sid5 %s/%s/%s smr=', b'GPU ctx %s/%s/%s tlb=')
    elif options.cb_activate:
        baseline = 'gpu-cbroot-v120'
        base_sha = 'e6d8b426b79facd7ebe47b5a6e6100f377542befbf3fc718e9a91c8a3c6d21b6'
        output = OUT / 'gpu-cbactivate-v121'
        old, new = b't970-gpu-p=17', b't970-gpu-p=18'
        markers = (b'GPU ctx %s/%s/%s tlb=', b'sync-off')
    elif options.cb_root:
        baseline = 'gpu-ttbrwidth-v119'
        base_sha = '9e07061db0cdff73c64b48ed88101726021451f515d5bcc22d184038cb655c6a'
        output = OUT / 'gpu-cbroot-v120'
        old, new = b't970-gpu-p=16', b't970-gpu-p=17'
        markers = (b'GPU root %s/%s/%s cfg/rb=', b'GPU ttbr %s/%s/%s rd/wr/rb=')
    elif options.ttbr_width:
        baseline = 'gpu-cbrelease-v118'
        base_sha = '240b2f38742b2b181f4e6a97cc269e7c24b6b74c68fa50306785653caa9eeb6f'
        output = OUT / 'gpu-ttbrwidth-v119'
        old, new = b't970-gpu-p=15', b't970-gpu-p=16'
        markers = (b'GPU ttbr %s/%s/%s rd/wr/rb=', b'inert')
    elif options.cb_release:
        baseline = 'gpu-cbbar-v117'
        base_sha = 'a9c4860d9fd50e264f00d75c65de75350aa487b9edfcc83249abf7f36974ee92'
        output = OUT / 'gpu-cbrelease-v118'
        old, new = b't970-gpu-p=14', b't970-gpu-p=15'
        markers = (b'GPU cbar %s/%s/%s bar=', b'inert')
    elif options.cb_bar:
        baseline = 'gpu-gmu-tables-v116'
        base_sha = '9ea0a92498f038c87798a410ecade65a3592bbdd82d2914f98324f960fd26633'
        output = OUT / 'gpu-cbbar-v117'
        old, new = b't970-gpu-p=13', b't970-gpu-p=14'
        markers = (b'GPU cbar %s/%s/%s bar=', b'latched')
    elif options.gmu_tables:
        baseline = 'gpu-cbrestore-v115'
        base_sha = '789e99a1b42f03b312586e5641e5d11da3b666a36f7a04d2e58245c1add98353'
        output = OUT / 'gpu-gmu-tables-v116'
        old, new = b't970-gpu-p=12', b't970-gpu-p=13'
        markers = (b'GPU tables %s rc=', b'GPU tables backing')
    elif options.cb_restore:
        baseline = 'gpu-cbguard-v114'
        base_sha = 'a3c7e5fc2c73b168e7b4baee587a371166f877fe28dd184e7b1940966754f72f'
        output = OUT / 'gpu-cbrestore-v115'
        old, new = b't970-gpu-p=11', b't970-gpu-p=12'
        markers = (b'GPU cbfmt %s/%s va64=', b'CB guard id=', b'rb=%u guard=')
    elif options.cb_guard:
        baseline = 'gpu-cbfmt-v113'
        base_sha = 'cc2fb731540a3e3fdbe13c1e8d3c93aaea8690283b64b37a5272ecde1d02c0ad'
        output = OUT / 'gpu-cbguard-v114'
        old, new = b't970-gpu-p=10', b't970-gpu-p=11'
        markers = (b'GPU cbfmt %s/%s va64=', b'CB guard id=', b'rb=%u guard=')
    elif options.cb_format:
        baseline = 'gpu-smmu-v112'
        base_sha = 'f9df94f349d8bb6859fd6ee7626941de38be3e7333a422e3e0d49b7a0b3bd550'
        output = OUT / 'gpu-cbfmt-v113'
        old, new = b't970-gpu-p=9', b't970-gpu-p=10'
        markers = (b'GPU cbfmt %s/%s va64=', b'smmu-hold')
    elif options.smmu_read:
        baseline = 'gpu-gmu-rate-v111'
        base_sha = '50deea9b872a75087923157b3696a96d80c7330e06fb037594c9d5a4e5c06888'
        output = OUT / 'gpu-smmu-v112'
        old, new = b't970-gpu-p=8', b't970-gpu-p=9'
        markers = (b'GPU smmu %s/%s id=', b'CB0 bar/attr=')
    elif options.gmu_rate:
        baseline = 'gpu-arc-vote-v110'
        base_sha = 'f8039496c056aa92d1bd9bf6cd2a24ddc19f8299713a5e019a272d485e33f039'
        output = OUT / 'gpu-gmu-rate-v111'
        old, new = b't970-gpu-p=7', b't970-gpu-p=8'
        markers = (b'GPU rate %s/%s', b'update-hold', b'xo-hold')
    elif options.arc_vote:
        baseline = 'gpu-rsc-init-v109'
        base_sha = '569ebe5fcf875c26aae7fd6b9d544ba9cec8204f0a2df527057184d387899eab'
        output = OUT / 'gpu-arc-vote-v110'
        old, new = b't970-gpu-p=6', b't970-gpu-p=7'
        markers = (b'GPU vote %s/%s', b'arc-hold', b'clear-hold')
    elif options.rsc_init:
        baseline = 'gpu-rsc-v108'
        base_sha = '25f846a61e86269dc42d97ba863de8bf13ef983dd488e66e56060c29301067ec'
        output = OUT / 'gpu-rsc-init-v109'
        old, new = b't970-gpu-p=5', b't970-gpu-p=6'
        markers = (b'GPU init %s cfg=', b'busy-hold', b'restore-hold')
    elif options.rsc_read:
        baseline = 'gpu-gmu-v107'
        base_sha = '5354324ff1c4b61f86be0a188fece6f8e980cd7d362ae31731071a0b365fba9b'
        output = OUT / 'gpu-rsc-v108'
        old, new = b't970-gpu-p=4', b't970-gpu-p=5'
        markers = (b'GPU rsc %s cfg/st/busy=', b'RSC hidden=')
    elif options.gmu_read:
        baseline = 'gpu-xo-v106'
        base_sha = 'd0a4c1919b589ba1db6c147300a426e8745345f18043664b78d0722a76de4955'
        output = OUT / 'gpu-gmu-v107'
        old, new = b't970-gpu-p=3', b't970-gpu-p=4'
        markers = (b'GPU gmu %s reset=', b'GPU xo hold rcg=')
    elif options.xo_clocks:
        baseline = 'gpu-cx-v105'
        base_sha = '4ae3bcd1cbf11903cb24ad69cb607368dab1a3edcdd5575769686a8071bf90cb'
        output = OUT / 'gpu-xo-v106'
        old, new = b't970-gpu-p=2', b't970-gpu-p=3'
        markers = (b'GPU xo rcg=', b'GPU xo hold rcg=')
    elif options.cx_pulse:
        baseline = 'gpu-power-v104'
        base_sha = '031095d5baf37dae5f3ae7b89e4f1eaffd22683bea218efdf56ffe6e5434f902'
        output = OUT / 'gpu-cx-v105'
        old, new = b't970-gpu-p=1', b't970-gpu-p=2'
        markers = (b'GPU cx pre=', b'ack=%u restore=%u')
    else:
        baseline = 'gpu-clk-write-v103'
        base_sha = '6b1240530b8b702f1ea1083d1f2adb94f2a9ec59203422932a75946399e6ec80'
        output = OUT / 'gpu-power-v104'
        old, new = b't970-gpu-w=1', b't970-gpu-p=1'
        markers = (b'GPU pwr cfg/mem/dvm/axi=', b'cx/hw/gx/ahb/gmu/smmu=')
    build = output.with_name(output.name + '-build')
    boot = (OUT / baseline / 'boot-partition.img').read_bytes()
    require(boot[:8] == b'ANDROID!' and sha(boot) == base_sha, f'Expected the exact {baseline} BOOT')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(boot), 'Invalid ramdisk bounds')
    output.mkdir()
    fat = output / 'payload.img'
    fat.write_bytes(boot[start:end])
    copy = ['mcopy', '-i', str(fat)]

    def read(name):
        return subprocess.check_output([*copy, PREFIX + name, '-'])

    original_config = read(CONFIG)
    old_flag, new_flag = b' ' + old + b' ', b' ' + new + b' '
    require(original_config.count(old_flag) == 1 and new_flag not in original_config, 'Unexpected baseline GPU flag')
    config = original_config.replace(old_flag, new_flag)
    entries = [entry for entry in tomllib.loads(config.decode())['entry'] if entry.get('type') == 'xnu']
    require(len(entries) == 1, 'Expected one XNU entry')
    args = entries[0]['args'].encode()
    require(len(args) <= 1000 and new in args.split() and old not in args.split(),
            'Invalid GPU flag or Loader argument length')
    config_path = output / CONFIG
    config_path.write_bytes(config)
    preserved = {name: sha(read(name)) for name in PRESERVED}

    built = build / 'kernel.macho'
    kernel = output / 'kernel.macho'
    shutil.copyfile(built, kernel)
    env = dict(os.environ, UNIXNU_UEFI=str(DEVICE / '.cache/uefi-source/Mu-Silicium'))
    subprocess.run(['python3.14', str(TREE / 'scripts/patch-xnu-entry-probe.py'),
                    str(kernel), '--panic-screen', '--no-reset'], env=env, check=True)
    payload_kernel = kernel.read_bytes()
    for marker in (*markers, b't970-gpu-p',
                   b'GPU arc db=', b'Battery svc=', b'Memory owned base=', b'blank/dark='):
        require(marker in payload_kernel, f'Missing linked marker {marker!r}')

    for local, name in ((config_path, CONFIG), (kernel, KERNEL)):
        subprocess.run([*copy, '-o', str(local), PREFIX + name], check=True)
    require(read(CONFIG) == config and read(KERNEL) == payload_kernel, 'FAT readback mismatch')
    require({name: sha(read(name)) for name in PRESERVED} == preserved, 'Inherited FAT input changed')
    payload = fat.read_bytes()
    require(len(payload) == payload_size, 'Payload size changed')
    result = boot[:start] + payload + boot[end:]
    (output / 'boot-partition.img').write_bytes(result)

    compile_report = json.loads((build / 'registration/report.json').read_text())
    report = dict(base_boot_sha256=base_sha, boot_sha256=sha(result), boot_bytes=len(result),
                  kernel_build_sha256=sha(built.read_bytes()), kernel_sha256=sha(payload_kernel),
                  config_sha256=sha(config), xnu_args_bytes=len(args), gpu_boot_arg=new.decode(),
                  unchanged_fat_inputs=preserved, unchanged_header_firmware_dtb_tail=True,
                  gpu_soc_revision=compile_report['gpu_soc_revision'],
                  gpu_soc_header_sha256=compile_report['gpu_soc_header_sha256'])
    (output / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
