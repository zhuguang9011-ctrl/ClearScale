import numpy as np
from PIL import Image
from run_local_inpaint import prepare, stitch
rng=np.random.default_rng(42)
a=rng.integers(0,256,(80,140,4),dtype=np.uint8)
source=Image.fromarray(a)
for region in [(0,0,30,40),(90,40,140,80),(30,20,75,60)]:
    mask=np.zeros((80,140),dtype=np.uint8)
    x0,y0,x1,y1=region; mask[y0:y1,x0:x1]=255
    m=Image.fromarray(mask)
    crop,cm,guide,meta=prepare(source,m,source,512,8)
    assert crop.size==cm.size==guide.size==(512,512)
    result=np.asarray(stitch(source,m,Image.new('RGB',(512,512),'white'),meta,preserve_color=False))
    assert np.array_equal(result[mask==0],a[mask==0])
    assert np.array_equal(result[...,3],a[...,3])
    assert not np.array_equal(result[mask>0,:3],a[mask>0,:3])
try: prepare(source,Image.new('L',source.size),source)
except ValueError: pass
else: raise AssertionError('empty mask accepted')
print('PASS: edge crops, square padding, exact outside-mask and alpha preservation, empty mask rejection')

from run_local_inpaint import regular_control
m=Image.new('L',(256,256),255)
_,_,_,meta=prepare(Image.new('RGB',m.size),m,Image.new('RGB',m.size),256,0)
c=np.asarray(regular_control(m,meta,spacing=16,angle=0,curvature=0,resolution=256))[:,:,0]
assert np.array_equal(c[20],c[220]), 'straight contours must not change between rows'
assert np.array_equal(c[:,32:224],c[:,16:208]), 'line period is not 16 px'
assert c.max()==255 and c.min()==0
try: regular_control(m,meta,spacing=1,resolution=256)
except ValueError: pass
else: raise AssertionError('undersampled lines accepted')
print('PASS: analytic control periodicity and undersampling rejection')
