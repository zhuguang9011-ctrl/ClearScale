import numpy as np
from PIL import Image
from filament_rebuild import rebuild

y,x=np.mgrid[:256,:256]
old=120+25*np.sin(2*np.pi*(x/7+.002*x*x))
source=np.stack([old, old*.25, old*.2, np.full_like(old,197)],axis=-1).astype('uint8')
mask=np.zeros((256,256),dtype='uint8');mask[16:240,16:240]=255
out,report=rebuild(Image.fromarray(source),mask,12,0,0,.2)
a=np.asarray(out)
assert np.array_equal(a[mask==0],source[mask==0]), 'outside mask changed'
assert np.array_equal(a[...,3],source[...,3]), 'alpha changed'
row=a[128,48:208,0].astype(float)
spectrum=np.abs(np.fft.rfft(row-row.mean()))
period=len(row)/(np.argmax(spectrum[1:])+1)
assert abs(period-12)<1, period
assert np.mean(np.abs(a[64:192,64:192,:3].astype(float)-source[64:192,64:192,:3]))>5
try: rebuild(Image.fromarray(source),np.zeros_like(mask))
except ValueError: pass
else: raise AssertionError('empty mask accepted')
print('PASS: rebuilt line period, changed old pattern, exact outside-mask and alpha preservation')
