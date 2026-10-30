#include "phase_roi.h"
#include <string.h>

static void put16(uint8_t *p, uint16_t v) { p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); }
static void put32(uint8_t *p, uint32_t v) { put16(p,(uint16_t)v); put16(p+2,(uint16_t)(v>>16)); }

size_t sv_roi_packet(uint8_t *out, size_t capacity, const sv_complex16 *input,
    uint16_t range_bins, uint16_t antennas, uint16_t first_bin, uint16_t bin_count,
    uint32_t frame_number, uint32_t cpu_cycles, uint32_t frame_period_us)
{
    static const uint8_t magic[8]={2,1,4,3,6,5,8,7};
    size_t payload, total, r, a, cursor;
    if(!out || !input || !range_bins || range_bins>1024 || !antennas || antennas>12 ||
       !bin_count || first_bin>=range_bins || bin_count>range_bins-first_bin || !frame_period_us) return 0;
    payload=16+(size_t)bin_count*antennas*4;
    total=(40+8+payload+31)&~(size_t)31;
    if(capacity<total) return 0;
    memset(out,0,total);
    memcpy(out,magic,8);
    put32(out+8,0x03060200); put32(out+12,(uint32_t)total); put32(out+16,0x000a6843);
    put32(out+20,frame_number); put32(out+24,cpu_cycles); put32(out+32,1);
    put32(out+40,0x53565031); put32(out+44,(uint32_t)payload);
    put16(out+48,1); put16(out+50,range_bins); put16(out+52,first_bin);
    put16(out+54,bin_count); put16(out+56,antennas); put32(out+60,frame_period_us);
    cursor=64;
    for(r=first_bin;r<(size_t)first_bin+bin_count;r++) for(a=0;a<antennas;a++) {
        const sv_complex16 *z=input+r*antennas+a;
        put16(out+cursor,(uint16_t)z->imag); put16(out+cursor+2,(uint16_t)z->real); cursor+=4;
    }
    return total;
}
