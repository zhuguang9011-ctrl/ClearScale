import numpy as np

from app import editor_parts, image_pixels


image = np.full((24, 32, 3), 127, dtype=np.uint8)
paint = np.zeros((24, 32, 4), dtype=np.uint8)
paint[4:12, 6:18, 3] = 255

# Normal Gradio payload.
background, mask = editor_parts({"background": image, "layers": [paint], "composite": image})
assert background.shape == image.shape
assert mask.shape == image.shape[:2]

# Payload observed on some Chromium/Gradio combinations: the visible upload is
# present as composite but background is null.
background, mask = editor_parts({"background": None, "layers": [paint], "composite": image})
assert np.array_equal(background, image)
assert int(mask.max()) == 255

# Image references use the same compatibility conversion.
assert np.array_equal(image_pixels({"background": None, "layers": [], "composite": image}), image)

print("image editor compatibility test passed")
