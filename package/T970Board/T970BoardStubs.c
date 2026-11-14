/* Weak definitions for the wireless diagnostic tables BootLog reads.
 * The real arrays live in the Wi-Fi probe/stack (port milestone M5); until then
 * the boot report prints zeros for those rows instead of failing to link. */
#include <stdint.h>

__attribute__((weak)) volatile uint32_t t970_wifi_stats[28];
__attribute__((weak)) char t970_wifi_cmddb[640];
__attribute__((weak)) volatile int32_t t970_wifi_rail_rc[12];
__attribute__((weak)) volatile uint32_t t970_wifi_smmu[10];
__attribute__((weak)) volatile uint32_t t970_wifi_mhi[13];
__attribute__((weak)) volatile uint32_t t970_wifi_dom[14];
__attribute__((weak)) volatile uint32_t t970_wifi_trace[27];
__attribute__((weak)) volatile uint32_t t970_wifi_rst[9];
__attribute__((weak)) volatile uint32_t t970_wifi_chk[18];
__attribute__((weak)) volatile uint32_t t970_wifi_pbl[26];
__attribute__((weak)) volatile uint32_t t970_wifi_msi[10];
__attribute__((weak)) volatile uint32_t t970_wifi_stack[16];

/* Remaining diagnostic tables referenced by BootLog until their owners are ported. */
__attribute__((weak)) volatile unsigned long armcpu_core_entries[8];
__attribute__((weak)) volatile unsigned long armcpu_core_last_id[8];
__attribute__((weak)) volatile unsigned long armcpu_core_phase[8];
__attribute__((weak)) volatile unsigned long armcpu_stall_row[8];
__attribute__((weak)) volatile unsigned long boot_ui_trace_mutex_owner_rows[8];
__attribute__((weak)) volatile unsigned long native_accel_hid[8];
__attribute__((weak)) volatile unsigned long native_adreno_close_step[8];
__attribute__((weak)) volatile unsigned long native_adreno_cp_aperture[8];
__attribute__((weak)) volatile unsigned long native_adreno_cp_image[8];
__attribute__((weak)) volatile unsigned long native_adreno_global_lock[8];
__attribute__((weak)) volatile unsigned long native_adreno_map_ring[8];
__attribute__((weak)) volatile unsigned long native_adreno_map_ring_count[8];
__attribute__((weak)) volatile unsigned long native_adreno_table_pages[8];
__attribute__((weak)) volatile unsigned long native_adreno_table_switches[8];
__attribute__((weak)) volatile unsigned long native_adreno_unmap_ring[8];
__attribute__((weak)) volatile unsigned long native_adreno_unmap_ring_count[8];
__attribute__((weak)) volatile unsigned long native_adreno_vm_fail[8];
__attribute__((weak)) volatile unsigned long native_gpu_addon4_stage[8];
__attribute__((weak)) volatile unsigned long native_gpu_addon4_status[8];
__attribute__((weak)) volatile unsigned long native_gpu_step[8];
__attribute__((weak)) volatile unsigned long native_gyro_hid[8];
__attribute__((weak)) volatile unsigned long native_hid_accel_status[8];
__attribute__((weak)) volatile unsigned long native_hid_gyro_status[8];
__attribute__((weak)) volatile unsigned long native_hid_orient_status[8];
__attribute__((weak)) volatile unsigned long native_hid_pen_status[8];
__attribute__((weak)) volatile unsigned long native_hid_props_driver[8];
__attribute__((weak)) volatile unsigned long native_legacy_direct[8];
__attribute__((weak)) volatile unsigned long native_legacy_surface_stride_raw[8];
__attribute__((weak)) volatile unsigned long native_legacy_swap_drops[8];
__attribute__((weak)) volatile unsigned long native_orient_hid[8];
__attribute__((weak)) volatile unsigned long native_pen_hid[8];
__attribute__((weak)) volatile unsigned long native_t970_mgcache[8];
__attribute__((weak)) volatile unsigned long native_t970_ttbr[8];
__attribute__((weak)) volatile unsigned long native_t970_wc_attr[8];
__attribute__((weak)) volatile unsigned long native_t970_wc_reassert[8];
__attribute__((weak)) volatile unsigned long native_ufs_dpu_check[8];
__attribute__((weak)) volatile unsigned long native_ufs_dpu_smmu[8];
__attribute__((weak)) volatile unsigned long native_ufs_poll_text[8];
__attribute__((weak)) volatile unsigned long qcom_usb_debug_peek_status[8];
__attribute__((weak)) volatile unsigned long qcom_usb_diag_failed[8];
__attribute__((weak)) volatile unsigned long qcom_usb_diag_phase[8];
__attribute__((weak)) volatile unsigned long t970_battery[8];
__attribute__((weak)) volatile unsigned long t970_bt[8];
__attribute__((weak)) volatile unsigned long t970_bt_cp[8];
__attribute__((weak)) volatile unsigned long t970_bt_hci[8];
__attribute__((weak)) volatile unsigned long t970_bt_sk[8];
__attribute__((weak)) volatile unsigned long t970_bt_text[8];
__attribute__((weak)) volatile unsigned long t970_camera[8];
__attribute__((weak)) volatile unsigned long t970_camera_ae[8];
__attribute__((weak)) volatile unsigned long t970_camera_c5[8];
__attribute__((weak)) volatile unsigned long t970_camera_thumb[8];
__attribute__((weak)) volatile unsigned long t970_dpu_timing_row[8];
__attribute__((weak)) volatile unsigned long t970_memtest_result[8];
__attribute__((weak)) volatile unsigned long t970_qud_faults[8];
__attribute__((weak)) volatile unsigned long t970_qud_inherited[8];
__attribute__((weak)) volatile unsigned long t970_qud_phy[8];
__attribute__((weak)) volatile unsigned long t970_qud_retry[8];
__attribute__((weak)) volatile unsigned long t970_qud_ss[8];

__attribute__((weak)) volatile unsigned long native_adreno_bad_physical[8];
__attribute__((weak)) volatile unsigned long native_gop_failures[8];
__attribute__((weak)) volatile unsigned long native_gop_ready[8];
__attribute__((weak)) volatile unsigned long native_gop_transfers[8];
__attribute__((weak)) volatile unsigned long native_gpu_rows[8];
__attribute__((weak)) volatile unsigned long native_hid_class_sizes[8];
__attribute__((weak)) volatile unsigned long native_hid_input_meta_status[8];
__attribute__((weak)) volatile unsigned long native_hid_load_status[8];
__attribute__((weak)) volatile unsigned long native_hid_matching_load_status[8];
__attribute__((weak)) volatile unsigned long native_hid_stage[8];
__attribute__((weak)) volatile unsigned long native_hid_touch_status[8];
__attribute__((weak)) volatile unsigned long native_legacy_gop_height[8];
__attribute__((weak)) volatile unsigned long native_legacy_gop_width[8];
__attribute__((weak)) volatile unsigned long native_legacy_presented_generation[8];
__attribute__((weak)) volatile unsigned long native_legacy_retired_frames[8];
__attribute__((weak)) volatile unsigned long native_legacy_surfaces[8];
__attribute__((weak)) volatile unsigned long native_touch_frame_raw[8];
__attribute__((weak)) volatile unsigned long native_touch_hid_reports[8];
__attribute__((weak)) volatile unsigned long native_ufs_log_read[8];
__attribute__((weak)) volatile unsigned long native_ufs_log_read_bytes[8];
__attribute__((weak)) volatile unsigned long qcom_usb_debug_write[8];
__attribute__((weak)) void boot_progress_exit_fault(int a, unsigned b, char *c, unsigned long d) { (void)a; (void)b; (void)c; (void)d; }
__attribute__((weak)) void boot_progress_exit_reason(int a, unsigned b, char *c, unsigned long d) { (void)a; (void)b; (void)c; (void)d; }
__attribute__((weak)) int boot_reset_probe(char *a, unsigned b) { (void)a; (void)b; return 0; }
__attribute__((weak)) int boot_reset_bootloader(char *a, unsigned b) { (void)a; (void)b; return 0; }
__attribute__((weak)) int boot_reset_mark_bootloader(char *a, unsigned b) { (void)a; (void)b; return 0; }
__attribute__((weak)) int boot_reset_watchdog(unsigned c, char *a, unsigned b) { (void)c; (void)a; (void)b; return 0; }
__attribute__((weak)) volatile unsigned long t970_motion_log_status[8];
