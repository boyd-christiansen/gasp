"""Generate Gasp's short start cue; no external sound assets."""
import math
from pathlib import Path
import struct
import sys
import wave

rate, seconds = 48000, .08
samples = [int(5500 * math.sin(math.pi*i/(rate*seconds-1))**2
               * math.sin(2*math.pi*(880*i/rate + 110*(i/rate)**2/seconds)))
           for i in range(round(rate*seconds))]
target = Path(sys.argv[1])
with wave.open(str(target), 'wb') as out:
    out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate)
    out.writeframes(struct.pack('<'+'h'*len(samples), *samples))
