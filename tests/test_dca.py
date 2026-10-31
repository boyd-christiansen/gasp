import struct
import numpy as np
import pytest
from gasp.dca import PacketWriter, command_packet, parse_reply, decode_adc
from gasp.profile import bundled_profile


def packet(seq,offset,data):return struct.pack('<I',seq)+offset.to_bytes(6,'little')+data


def test_commands_are_little_endian_and_checked():
    assert command_packet(5)==bytes.fromhex('5aa505000000aaee')
    assert parse_reply(bytes.fromhex('5aa509000000aaee'),9)==0
    with pytest.raises(RuntimeError):parse_reply(bytes.fromhex('5aa509000100aaee'),9)
    with pytest.raises(ValueError):parse_reply(b'bad',9)


def test_udp_reorder_duplicate_and_hole_are_preserved(tmp_path):
    w=PacketWriter(tmp_path/'adc.bin',max_bytes=1000)
    w.add(packet(3,8,b'ijkl'));w.add(packet(1,0,b'abcd'));w.add(packet(3,8,b'ijkl'))
    with pytest.raises(ValueError):w.add(packet(10,999,b'overflow'))
    report=w.finish()
    assert (tmp_path/'adc.bin').read_bytes()==b'abcd'+bytes(4)+b'ijkl'
    assert report['missing_intervals']==[[4,8]] and report['duplicates']==1
    assert report['out_of_order']==1


def test_adc_layout_and_timestamps_and_loss(tmp_path):
    p=bundled_profile('dca-raw');n=2*p.loops*p.tx_count*p.rx_count*p.adc_samples
    t=np.arange(p.adc_samples)
    signal=np.tile(1000*np.exp(2j*np.pi*8*t/p.adc_samples), n//p.adc_samples).astype(np.complex64)
    paired=signal.reshape(-1,2)
    wire=np.stack([paired[:,0].real,paired[:,1].real,paired[:,0].imag,paired[:,1].imag],axis=1).astype('<i2')
    path=tmp_path/'adc.bin';path.write_bytes(wire.tobytes())
    z,stamps,q=decode_adc(path,p)
    assert z.shape==(2*p.loops,64,12) and np.argmax(abs(z[0,:,0]))==8
    assert np.all(np.diff(stamps)>0)
    assert stamps[p.loops]==20_000_000 and stamps[1]==141000
    frame_bytes=len(wire.tobytes())//2
    z,stamps,q=decode_adc(path,p,[[10,20]])
    assert q['dropped_frames']==1 and z.shape[0]==p.loops and stamps[0]==20_000_000
