# social-reels

Temporary public storage for short Reel videos made by the social media bot
(China Cargo Hub, China Sell Hub, Fashionshrude).

- `tools/make_reel.py` turns a square post image into a 9:16 MP4 Reel (Pillow + ffmpeg).
- `reels/` holds the videos for the current run only. The website copies each video into
  its own media library, so files here are replaced every run.
