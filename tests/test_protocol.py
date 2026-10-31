import ctypes
from pathlib import Path
import struct
import subprocess
import numpy as np
import pytest
from gasp.protocol import Parser, Frame, encode_frame, MAGIC, HEADER


def test_fragmented_resync_and_multiple_frames():
    z = (np.arange(64*12).reshape(64,12) + 1j*123).astype(np.complex64)
    wire = b'junk' + encode_frame(42,z) + encode_frame(43,z)
    p=Parser(); result=[]
    for i in range(0,len(wire),13): result.extend(p.feed(wire[i:i+13]))
    assert [x.number for x in result]==[42,43]
    np.testing.assert_array_equal(result[0].complex_heatmap(64),z)
    assert p.discarded_bytes==4 and p.bad_packets==0 and not p.buffer


def test_bad_length_and_bad_tlv_then_valid():
    z=np.ones((64,12),dtype=np.complex64)
    bad=bytearray(encode_frame(1,z));struct.pack_into('<I',bad,44,100000)
    invalid=HEADER.pack(MAGIC,0,0xffffffff,0,0,0,0,0,0)
    p=Parser(); frames=p.feed(invalid+bad+encode_frame(2,z))
    assert [f.number for f in frames]==[2] and p.bad_packets>=2


def test_magnitude_is_not_complex():
    f=Frame(0,0,0,0,0,b'',{2:struct.pack('<3H',1,2,3)})
    assert f.complex_heatmap(64) is None
    np.testing.assert_array_equal(f.range_profile(),[1,2,3])
    with pytest.raises(ValueError): Frame(0,0,0,0,0,b'',{8:bytes(7)}).complex_heatmap(64)


def test_portable_c_firmware_matches_python_decoder(tmp_path):
    root=Path(__file__).parents[1]
    library=tmp_path/'phase_roi.dylib'
    subprocess.run(['clang','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                    str(root/'firmware/phase_roi.c'),'-o',str(library)],check=True)
    lib=ctypes.CDLL(str(library))
    fn=lib.sv_roi_packet
    fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]+[ctypes.c_uint16]*4+[ctypes.c_uint32]*3
    fn.restype=ctypes.c_size_t
    # imag, real wire order; values are signed, including the negative edge.
    iq=np.zeros((64,12,2),dtype=np.int16);iq[:,:,0]=-32768;iq[:,:,1]=1234
    out=ctypes.create_string_buffer(4096)
    n=fn(out,len(out),iq.ctypes.data,64,12,4,12,19,7,50000)
    assert n>0 and n%32==0
    f=Parser().feed(out.raw[:n])[0];z=f.complex_heatmap(64)
    assert f.number==19 and z.shape==(64,12)
    np.testing.assert_array_equal(z[4:16],1234-32768j)
    assert not z[:4].any() and not z[16:].any()
    assert fn(out,32,iq.ctypes.data,64,12,4,12,19,7,50000)==0
