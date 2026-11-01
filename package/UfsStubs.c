// SPDX-License-Identifier: BSD-2-Clause-Patent
// ShengUfs imports boot_progress_poll as a weak reference; a static kernel link
// still has to resolve it. Weak so a real BootProgress archive later wins.
#include <stdint.h>

__attribute__((weak)) void boot_progress_poll(void);
__attribute__((weak)) void boot_progress_poll(void)
{
}
