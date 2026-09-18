"""Manual masked filament reconstruction; not an automatic 3-D estimator."""
import numpy as np
from PIL import Image, ImageFilter


def rebuild(image, mask, spacing=10, angle=0, curvature=0.35, contrast=0.12):
    rgba = np.asarray(image.convert('RGBA')).copy()
    h, w = rgba.shape[:2]
    if mask is None:
        raise ValueError('请先涂抹一个连续的线材区域')
    m = np.asarray(mask)
    if m.shape != (h, w):
        raise ValueError('蒙版尺寸与原图不一致，请重新上传原图并涂抹')
    binary = m > 25
    if binary.sum() < 64:
        raise ValueError('请涂抹更大的线材区域')
    spacing = float(spacing)
    if not 3 <= spacing <= 80:
        raise ValueError('线距需在 3–80 原图像素之间')
    ys, xs = np.where(binary)
    cx, cy = (xs.min()+xs.max())/2, (ys.min()+ys.max())/2
    radius = max(1, ys.max()-ys.min(), xs.max()-xs.min())
    # Normalized masked low-pass removes old grooves without bleeding black
    # spool/background pixels into the selected surface.
    radius_blur = max(3, spacing * 1.5)
    weights = np.asarray(Image.fromarray(binary.astype('float32'), mode='F'))
    def blur(values):
        # Pillow GaussianBlur does not support mode F: use 8-bit weighted RGB
        return np.asarray(Image.fromarray(np.uint8(np.clip(values,0,255))).filter(
            ImageFilter.GaussianBlur(radius_blur)), dtype=np.float32)
    denominator = blur(weights * 255) / 255
    rgb = rgba[...,:3].astype(np.float32)
    smooth = np.stack([blur(rgb[...,i]*weights)/np.maximum(denominator,1/255)
                       for i in range(3)], axis=-1)
    yy, xx = np.mgrid[:h,:w].astype(np.float32)
    theta = np.deg2rad(float(angle))
    normal = (xx-cx)*np.cos(theta) + (yy-cy)*np.sin(theta)
    along = -(xx-cx)*np.sin(theta) + (yy-cy)*np.cos(theta)
    phase = (normal - float(curvature)*along**2/radius)/spacing
    # Consistent ridge profile, with a small asymmetric specular shoulder.
    profile = np.cos(2*np.pi*phase) + .22*np.sin(4*np.pi*phase)
    rebuilt = smooth * (1 + float(contrast)*profile[...,None])
    # Feather only inward: absolutely no modifications outside the mask.
    feather = np.asarray(Image.fromarray(binary.astype('uint8')*255).filter(
        ImageFilter.GaussianBlur(1.5)),dtype=np.float32)/255
    alpha = np.clip((feather-.5)*2,0,1)*binary
    result = rgb*(1-alpha[...,None])+rebuilt*alpha[...,None]
    rgba[...,:3] = np.uint8(np.clip(np.rint(result),0,255))
    return Image.fromarray(rgba), {'mode':'manual curved filament reconstruction',
        'spacing_source_px':spacing,'angle_degrees':float(angle),
        'curvature':float(curvature),'contrast':float(contrast),
        'masked_fraction':float(binary.mean()),'automatic_perspective':False}
