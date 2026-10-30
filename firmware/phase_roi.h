#ifndef SUBVOCAL_PHASE_ROI_H
#define SUBVOCAL_PHASE_ROI_H
#include <stdint.h>
#include <stddef.h>

/* SDK cmplx16ImRe_t-compatible layout. No TI source is redistributed. */
typedef struct { int16_t imag; int16_t real; } sv_complex16;

/* Encode one frame into caller-owned memory. Returns 0 on invalid bounds.
 * Call ONLY after the complex range/antenna buffer is ready, before reuse.
 * input is [range][antenna]; result is one padded SDK-framed SVP1 packet.
 * UART serialization and cache coherency remain the SDK integration's job.
 */
size_t sv_roi_packet(uint8_t *out, size_t capacity, const sv_complex16 *input,
    uint16_t range_bins, uint16_t antennas, uint16_t first_bin, uint16_t bin_count,
    uint32_t frame_number, uint32_t cpu_cycles, uint32_t frame_period_us);
#endif
