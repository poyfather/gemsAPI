"""
Builds the README loop from frames drawn by render.mjs: the side by side moment, 12.6 to 27.6 s,
at 10 frames a second and 800 pixels wide, with one shared palette so colours do not flicker.

    python gif.py frames ../lapidary-demo.gif
"""
import sys

from PIL import Image

frames_dir, out = sys.argv[1], sys.argv[2]
FPS = 30
idx = list(range(int(12.6 * FPS), int(27.6 * FPS), 3))
frames = [Image.open(f"{frames_dir}/f{i:05d}.jpg").convert("RGB").resize((800, 450), Image.LANCZOS) for i in idx]
sample = Image.new("RGB", (800, 450 * 6))
for k, frame in enumerate(frames[:: max(1, len(frames) // 6)][:6]):
    sample.paste(frame, (0, 450 * k))
palette = sample.quantize(colors=128, method=Image.MEDIANCUT)
quantized = [f.quantize(palette=palette, dither=Image.FLOYDSTEINBERG) for f in frames]
quantized[0].save(out, save_all=True, append_images=quantized[1:], duration=100, loop=0, optimize=True, disposal=1)
print(f"wrote {out}: {len(quantized)} frames")
