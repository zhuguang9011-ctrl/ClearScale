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

def stitch(source, mask, generated, meta, feather=4, preserve_color=True):
    base=np.asarray(source.convert('RGBA')).copy()
    box=meta['box']; x,y=meta['offset']; w,h=meta['crop_size']
    patch=generated.convert('RGB').resize((meta['side'],meta['side']),Image.Resampling.LANCZOS).crop((x,y,x+w,y+h))
    original=source.crop(box).convert('RGB')
    if preserve_color:
        old=np.asarray(original.convert('YCbCr')).copy()
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
    p.add_argument('--worker',action='store_true')
    args=p.parse_args()
    ensure_environment()
    import torch
    import cv2
    from diffusers import StableDiffusionControlNetInpaintPipeline, ControlNetModel, UniPCMultistepScheduler
    if not torch.cuda.is_available(): raise RuntimeError('CUDA GPU unavailable')
    source=ImageOps.exif_transpose(Image.open(args.source)).convert('RGBA')
    mask=Image.open(args.mask).convert('L'); guide=Image.open(args.guide).convert('RGB')
    image,local_mask,local_guide,meta=prepare(source,mask,guide)
    # Use the cleaned guide instead of the original irregular strand edges.
    edges=cv2.Canny(np.asarray(local_guide),60,140)
    control=Image.fromarray(edges).convert('RGB')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    control.save(args.output.parent/'control_preview.png')
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
    args.output.with_suffix('.json').write_text(json.dumps({'crop':meta,'strength':args.strength,'control':args.control,'seed':args.seed,'reference_used':bool(args.reference),'preserve_chroma':True},ensure_ascii=False,indent=2),encoding='utf-8')
    print('INPAINT SUCCESS',flush=True)

if __name__=='__main__': main()
