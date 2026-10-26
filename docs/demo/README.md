# Demo video

`lapidary-demo.mp4` (1280x720, 64 seconds, with sound) and `lapidary-demo.gif` (the 15-second side by side moment, which plays at the top of the README and links to the video).

Every picture in it is a real screenshot from [`../screenshots/`](../screenshots/README.md), taken from a Lapidary answering on qwen3:4b; the camera moves, highlights and captions are drawn on top. The music is synthesized by `tools/music.py`.

## Rebuild it

Needs Google Chrome (or `CHROME` pointing at another Chromium), Node 22 or newer, and Python with numpy and Pillow.

```sh
python3 -m http.server 8766 --directory docs          # from the repository root, in its own terminal
cd docs/demo/tools
npm install mp4-muxer@5
python music.py music.wav
node render.mjs ../lapidary-demo-1080.mp4             # draws frames/ and encodes 1920x1080 with sound
cp frames/f00720.jpg frames/f00000.jpg                # the side by side frame at 24 s becomes the thumbnail
node encode-only.mjs ../lapidary-demo.mp4 frames 1920 30 1280 720 1600000 music.wav
python gif.py frames ../lapidary-demo.gif                # needs Pillow
```

`scene.html` draws any moment of the video from a time value (`scene.html?t=24` shows that frame), so a scene can be checked as a still before rendering. If an encode finishes but the file is not written, `fetch-out.mjs` reads it from the still-open encoder page.
