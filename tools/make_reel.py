#!/usr/bin/env python3
"""Turn a square post image into a 9:16 Reel (MP4) with animated text. Free: Pillow + ffmpeg.

Usage:
  python3 make_reel.py --image post.jpg --out reel.mp4 --hook "Short hook text" \
      --cta "fashionshrude.com" --sub "Follow for daily style tips" \
      --accent "#C9A14A" --style serif --seconds 12
"""
import argparse, os, subprocess, textwrap
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance

W, H, FPS = 1080, 1920, 30

FD = os.environ.get("FONT_DIR", "")
FONTS = {
    "sans": [os.path.join(FD, "ArchivoBlack-Regular.ttf"),"/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "sans_reg": [os.path.join(FD, "Lato-Bold.ttf"),"/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "serif": [os.path.join(FD, "DMSerifDisplay-Regular.ttf"),"/usr/share/fonts/opentype/noto/NotoSerifCJK-SemiBold.ttc",
              "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
}


def font(kind, size):
    for p in FONTS[kind]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def wrap(draw, text, fnt, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= maxw:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def text_layer(lines, fnt, color, line_gap, width, shadow=True):
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    asc, desc = fnt.getmetrics()
    lh = asc + desc + line_gap
    h = lh * len(lines) + 20
    layer = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, ln in enumerate(lines):
        tw = d0.textlength(ln, font=fnt)
        x = (width - tw) / 2
        y = i * lh
        if shadow:
            d.text((x + 3, y + 4), ln, font=fnt, fill=(0, 0, 0, 160))
        d.text((x, y), ln, font=fnt, fill=color)
    return layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hook", required=True)
    ap.add_argument("--cta", required=True)
    ap.add_argument("--sub", default="Follow for more")
    ap.add_argument("--accent", default="#F28C28")
    ap.add_argument("--style", default="sans", choices=["sans", "serif"])
    ap.add_argument("--seconds", type=float, default=12)
    a = ap.parse_args()

    accent = hex2rgb(a.accent)
    src = Image.open(a.image).convert("RGB")

    # Background: cover-fit, blurred, darkened
    s = max(W / src.width, H / src.height)
    bg = src.resize((int(src.width * s) + 1, int(src.height * s) + 1), Image.LANCZOS)
    l, t = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((l, t, l + W, t + H)).filter(ImageFilter.GaussianBlur(45))
    bg = ImageEnhance.Brightness(bg).enhance(0.45).convert("RGBA")

    # Foreground square
    FG = 960
    fg_src = src.resize((int(FG * 1.08), int(FG * 1.08)), Image.LANCZOS)
    fg_y = 520
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(((W - FG) // 2 + 6, fg_y + 14, (W + FG) // 2 + 6, fg_y + FG + 14), 28, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    mask = Image.new("L", (FG, FG), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, FG, FG), 28, fill=255)

    # Text layers
    dd = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    hook_f = font(a.style if a.style == "serif" else "sans", 76)
    lines = wrap(dd, a.hook, hook_f, W - 140)
    if len(lines) > 3:
        hook_f = font(a.style if a.style == "serif" else "sans", 62)
        lines = wrap(dd, a.hook, hook_f, W - 120)[:4]
    hook = text_layer(lines, hook_f, (255, 255, 255, 255), 14, W)

    cta_f = font("sans", 50)
    cta_w = int(dd.textlength(a.cta, font=cta_f)) + 110
    cta = Image.new("RGBA", (cta_w, 110), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cta)
    cd.rounded_rectangle((0, 0, cta_w - 1, 109), 55, fill=accent + (255,))
    lum = 0.299 * accent[0] + 0.587 * accent[1] + 0.114 * accent[2]
    cta_text = (20, 20, 20, 255) if lum > 150 else (255, 255, 255, 255)
    asc, desc = cta_f.getmetrics()
    cd.text(((cta_w - dd.textlength(a.cta, font=cta_f)) / 2, (110 - asc - desc) / 2 - 2), a.cta, font=cta_f, fill=cta_text)

    sub_f = font("sans_reg", 40)
    sub = text_layer([a.sub], sub_f, (235, 235, 235, 255), 0, W)

    n = int(a.seconds * FPS)
    proc = subprocess.Popen([
        os.environ.get("FFMPEG", "ffmpeg"), "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-shortest", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", a.out], stdin=subprocess.PIPE)

    for i in range(n):
        t = i / FPS
        frame = bg.copy()
        frame.alpha_composite(shadow)
        # slow zoom out 1.08 -> 1.0
        z = 1.08 - 0.08 * (i / max(1, n - 1))
        side = int(fg_src.width / z * (FG / fg_src.width) * z)  # keep FG size
        crop = int(fg_src.width / z)
        off = (fg_src.width - crop) // 2
        fg = fg_src.crop((off, off, off + crop, off + crop)).resize((FG, FG), Image.BILINEAR)
        frame.paste(fg, ((W - FG) // 2, fg_y), mask)

        # hook: slide down + fade in (0-0.7s)
        p = ease(t / 0.7)
        hk = hook.copy()
        hk.putalpha(hk.getchannel("A").point(lambda v: int(v * p)))
        frame.alpha_composite(hk, (0, int(150 + (1 - p) * -40) + max(0, (360 - hook.height) // 2)))

        # CTA pill: pop in at 1.2s
        p2 = ease((t - 1.2) / 0.5)
        if p2 > 0:
            c = cta.copy()
            c.putalpha(c.getchannel("A").point(lambda v: int(v * p2)))
            frame.alpha_composite(c, ((W - cta_w) // 2, int(1560 + (1 - p2) * 40)))
        # sub line at 2.2s
        p3 = ease((t - 2.2) / 0.6)
        if p3 > 0:
            sb = sub.copy()
            sb.putalpha(sb.getchannel("A").point(lambda v: int(v * p3)))
            frame.alpha_composite(sb, (0, 1700))
        # progress bar
        d = ImageDraw.Draw(frame)
        d.rectangle((0, H - 12, int(W * (i + 1) / n), H), fill=accent + (255,))
        proc.stdin.write(frame.convert("RGB").tobytes())

    proc.stdin.close()
    proc.wait()
    print("OK", a.out, os.path.getsize(a.out))


if __name__ == "__main__":
    main()
