import os
import select
import threading
import time
import numpy as np
import pytest
from gasp.profile import bundled_profile, parse_profile
from gasp.transport import SerialSource
from gasp.protocol import encode_frame


def test_real_serial_io_with_emulated_ti_device():
    """Exercise pyserial over OS PTYs, not a mock Serial object. No physical radar."""
    cm,cs=os.openpty();dm,ds=os.openpty();stop=threading.Event();started=threading.Event();commands=[]
    def device():
        buf=b'';number=0;deadline=time.monotonic()
        while not stop.is_set():
            ready,_,_=select.select([cm],[],[],.01)
            if ready:
                buf+=os.read(cm,4096)
                while b'\n' in buf:
                    line,buf=buf.split(b'\n',1);line=line.strip().decode();commands.append(line)
                    os.write(cm,b'\r\nDone\r\nmmwDemo:/>')
                    if line=='sensorStart':started.set()
                    if line=='sensorStop':started.clear()
            if started.is_set() and time.monotonic()>=deadline:
                z=np.ones((64,12),dtype=np.complex64)*(123+456j)
                wire=encode_frame(number,z);os.write(dm,wire[:23]);os.write(dm,wire[23:]);number+=1;deadline=time.monotonic()+.005
    worker=threading.Thread(target=device,daemon=True);worker.start()
    frames=[];errors=[];source=None
    try:
        # macOS PTYs do not support the hardware-only IOSSIOSPEED ioctl.
        # Use a standard PTY baud and a profile whose wire budget fits it.
        p=parse_profile(bundled_profile().text.replace('frameCfg 0 2 16 0 50','frameCfg 0 2 16 0 500'))
        source=SerialSource(os.ttyname(cs),os.ttyname(ds),p,lambda f,t:frames.append(f),errors.append,data_baud=115200)
        source.start()
        deadline=time.monotonic()+2
        while len(frames)<3 and time.monotonic()<deadline:time.sleep(.02)
        assert len(frames)>=3 and not errors
        np.testing.assert_array_equal(frames[0].complex_heatmap(64),123+456j)
        assert commands[-1]=='sensorStart' and 'guiMonitor -1 0 1 0 1 0 1' in commands
    finally:
        before_close=time.monotonic()
        if source:source.close()
        close_seconds=time.monotonic()-before_close
        stop.set();worker.join(1)
        for fd in (cm,cs,dm,ds):os.close(fd)
    assert close_seconds<3, 'Serial shutdown stalled under output backpressure'
    assert commands[-1]=='sensorStop', 'The emulator must handle stop while its data output is drained'
