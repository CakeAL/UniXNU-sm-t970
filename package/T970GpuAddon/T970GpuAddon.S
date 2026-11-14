/* SPDX-License-Identifier: BSD-2-Clause-Patent
   The DarwinBoot on SM-T970 hands no GpuAddon over, so the kernel image carries
   the addon bytes itself; t970-gpu-addon-embedded.patch uses them when the loader
   supplied none. */
.section __DATA,__const
.p2align 3
.globl _t970_gpu_addon_size
_t970_gpu_addon_size:
.quad _t970_gpu_addon_end - _t970_gpu_addon_data
.p2align 4
.globl _t970_gpu_addon_data
_t970_gpu_addon_data:
.incbin "/Users/cakeal/vsc/UniXNU-sm-t970/package/T970GpuAddon/gpu.addon"
_t970_gpu_addon_end:
