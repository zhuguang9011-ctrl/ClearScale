"""Experimental masked ControlNet inpainting, isolated from SeedVR2 dependencies."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent

def prepare(source, mask, guide, resolution=512, padding=64):
    source = source.convert('RGBA')
    mask = mask.convert('L')
    if mask.size != source.size or guide.size != source.size:
        raise ValueError('原图、蒙版、结构图尺寸必须一致')
    a = np.asarray(mask)>25
    ys,xs = np.where(a)
    if len(xs)<64: raise ValueError('请先涂抹线材区域')
    box=(max(0,int(xs.min())-padding),max(0,int(ys.min())-padding),
         min(source.width,int(xs.max())+1+padding),min(source.height,int(ys.max())+1+padding))
    # Square padding avoids distorting the local curve geometry.
    size=(box[2]-box[0],box[3]-box[1]); side=max(size)
    offset=((side-size[0])//2,(side-size[1])//2)
    def square(image, fill, method):
        tile=Image.new(image.mode,(side,side),fill)
        tile.paste(image.crop(box),offset)
        return tile.resize((resolution,resolution),method)
    return (square(source.convert('RGB'),(127,127,127),Image.Resampling.LANCZOS),
            square(mask,0,Image.Resampling.NEAREST),
            square(guide.convert('RGB'),(127,127,127),Image.Resampling.LANCZOS),
            {'box':box,'side':side,'offset':offset,'crop_size':size})

def regular_control(mask, meta, spacing=10, angle=0, curvature=.35, resolution=512):
    """Analytic ridge contours in source coordinates; never trace old grooves."""
    hard = np.asarray(mask.convert('L')) > 25
    ys, xs = np.where(hard)
    if len(xs) < 64:
        raise ValueError('请先涂抹线材区域')
    cx, cy = (xs.min()+xs.max())/2, (ys.min()+ys.max())/2
    radius = max(1, xs.max()-xs.min(), ys.max()-ys.min())
    scale = meta['side']/resolution
    if spacing/scale < 4:
        raise ValueError(f'当前线距在模型中仅 {spacing/scale:.1f} 像素，请缩小选区或增大线距，至少达到 4 像素')
    yy, xx = np.mgrid[:resolution,:resolution].astype(float)
    xx = (xx+.5)*scale + meta['box'][0]-meta['offset'][0]-.5-cx
    yy = (yy+.5)*scale + meta['box'][1]-meta['offset'][1]-.5-cy
    theta = np.deg2rad(angle)
    normal = xx*np.cos(theta)+yy*np.sin(theta)
    along = -xx*np.sin(theta)+yy*np.cos(theta)
    phase = (normal-curvature*along**2/radius)/spacing
    # Approximate one-pixel contour width, independent of color/contrast.
    gradient = np.sqrt(1+(2*curvature*along/radius)**2)*scale/spacing
    distance = np.abs(phase-np.rint(phase))
    edges = (distance <= .55*gradient).astype('uint8')*255
    box=meta['box']; side=meta['side']; offset=meta['offset']
    tile=Image.new('L',(side,side)); tile.paste(mask.crop(box),offset)
    selected=np.asarray(tile.resize((resolution,resolution),Image.Resampling.NEAREST))>25
    edges[~selected]=0
    return Image.fromarray(edges).convert('RGB')

def stitch(source, mask, generated, meta, feather=4, preserve_color=True):
    base=np.asarray(source.convert('RGBA')).copy()
    box=meta['box']; x,y=meta['offset']; w,h=meta['crop_size']
    patch=generated.convert('RGB').resize((meta['side'],meta['side']),Image.Resampling.LANCZOS).crop((x,y,x+w,y+h))
    original=source.crop(box).convert('RGB')
    if preserve_color:
        old=np.asarray(original.convert('YCbCr')).copy()
        selected=(np.asarray(mask.crop(box).convert('L'))>25).astype('uint8')
        def blur(a):
            return np.asarray(Image.fromarray(a.astype('uint8')).filter(ImageFilter.GaussianBlur(12)),dtype=float)
        weights=blur(selected*255)/255
        for channel in (1,2):
            old[...,channel]=np.clip(blur(old[...,channel]*selected)/np.maximum(weights,1/255),0,255).astype('uint8')
        old[...,0]=np.asarray(patch.convert('YCbCr'))[...,0]
        patch=Image.fromarray(old,'YCbCr').convert('RGB')
    hard=np.asarray(mask.convert('L'))>25
    soft=np.asarray(Image.fromarray(hard.astype('uint8')*255).filter(ImageFilter.GaussianBlur(feather)),dtype=float)/255
    alpha=np.clip((soft-.5)*2,0,1)*hard
    x0,y0,x1,y1=box
    blend=alpha[y0:y1,x0:x1,None]
    before=base[y0:y1,x0:x1,:3].astype(float)
    base[y0:y1,x0:x1,:3]=np.uint8(np.clip(np.rint(before*(1-blend)+np.asarray(patch)*blend),0,255))
    return Image.fromarray(base)

def ensure_environment():
    if '--worker' in sys.argv: return
    uv=ROOT/'runtime/uv.exe'
    env=ROOT/'runtime/inpaint-venv'
    python=env/'Scripts/python.exe'
    if not python.exists():
        subprocess.run([str(uv),'venv','--python',sys.executable,str(env)],check=True)
    marker=env/'inpaint-v1.txt'
    if not marker.exists():
        subprocess.run([str(uv),'pip','install','--python',str(python),'torch==2.9.1','torchvision==0.24.1','--index-url','https://download.pytorch.org/whl/cu128'],check=True)
        subprocess.run([str(uv),'pip','install','--python',str(python),'diffusers==0.35.1','accelerate==1.10.1','transformers==4.49.0','numpy','pillow','opencv-python-headless'],check=True)
        marker.write_text('1')
    result=subprocess.run([str(python),str(Path(__file__).resolve()),*sys.argv[1:],'--worker'])
    raise SystemExit(result.returncode)

def main():
    p=argparse.ArgumentParser()
    for name in ('source','mask','guide','output'): p.add_argument(name,type=Path)
    p.add_argument('--reference',type=Path)
    p.add_argument('--prompt',default='macro product photograph of neatly wound plastic filament, consistent strand thickness, smooth continuous parallel curved strands, realistic surface reflections')
    p.add_argument('--strength',type=float,default=.65)
    p.add_argument('--control',type=float,default=.8)
    p.add_argument('--reference-strength',type=float,default=.35)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--spacing',type=float,default=10)
    p.add_argument('--angle',type=float,default=0)
    p.add_argument('--curvature',type=float,default=.35)
    p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    ensure_environment()
    import torch
    from diffusers import StableDiffusionControlNetInpaintPipeline, ControlNetModel, UniPCMultistepScheduler
    if not torch.cuda.is_available(): raise RuntimeError('CUDA GPU unavailable')
    source=ImageOps.exif_transpose(Image.open(args.source)).convert('RGBA')
    mask=Image.open(args.mask).convert('L'); guide=Image.open(args.guide).convert('RGB')
    image,local_mask,local_guide,meta=prepare(source,mask,guide)
    control=regular_control(mask,meta,args.spacing,args.angle,args.curvature)
    # Initialize selected pixels from rebuilt ridges, not the irregular source.
    original_crop=image
    image=Image.composite(local_guide,image,local_mask)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    control.save(args.output.parent/'control_preview.png')
    original_crop.save(args.output.parent/'crop_original.png')
    image.save(args.output.parent/'crop_input.png'); local_mask.save(args.output.parent/'crop_mask.png')
    print('Loading inpaint models; first run downloads weights',flush=True)
    net=ControlNetModel.from_pretrained('lllyasviel/control_v11p_sd15_canny',torch_dtype=torch.float16)
    pipe=StableDiffusionControlNetInpaintPipeline.from_pretrained('stable-diffusion-v1-5/stable-diffusion-v1-5',controlnet=net,torch_dtype=torch.float16)
    pipe.scheduler=UniPCMultistepScheduler.from_config(pipe.scheduler.config)
    extra={}
    if args.reference:
        pipe.load_ip_adapter('h94/IP-Adapter',subfolder='models',weight_name='ip-adapter-plus_sd15.bin',image_encoder_folder='models/image_encoder')
        pipe.set_ip_adapter_scale(args.reference_strength)
        extra['ip_adapter_image']=Image.open(args.reference).convert('RGB')
    pipe.enable_model_cpu_offload(); pipe.enable_vae_tiling()
    def progress(pipe,step,timestep,kwargs):
        print(f'Inpaint step {step+1}',flush=True); return kwargs
    result=pipe(prompt=args.prompt,negative_prompt='broken strands, tangled wires, crossed strands, text, lettering, objects, uneven thickness',image=image,mask_image=local_mask,control_image=control,width=512,height=512,strength=args.strength,controlnet_conditioning_scale=args.control,num_inference_steps=30,guidance_scale=5,generator=torch.Generator('cpu').manual_seed(args.seed),callback_on_step_end=progress,**extra)
    if result.nsfw_content_detected and any(result.nsfw_content_detected):
        raise RuntimeError('生成结果被模型过滤，请调整输入后重试')
    patch=result.images[0]; patch.save(args.output.parent/'generated_crop.png')
    stitch(source,mask,patch,meta).save(args.output)
    args.output.with_suffix('.json').write_text(json.dumps({'crop':meta,'strength':args.strength,'control':args.control,'seed':args.seed,'reference_used':bool(args.reference),'preserve_chroma':'low-pass original chroma', 'version':'regular-guide-v2', 'spacing':args.spacing,'angle':args.angle,'curvature':args.curvature,'prompt':args.prompt,'reference_strength':args.reference_strength,'masked_fraction':float((np.asarray(mask)>25).mean())},ensure_ascii=False,indent=2),encoding='utf-8')
    print('INPAINT SUCCESS',flush=True)

if __name__=='__main__': main()
