import hashlib
import math
import shutil
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path(__file__).with_name("fonts") / "NotoSansSC-Regular.otf"
FONT_SHA256 = "faa6c9df652116dde789d351359f3d7e5d2285a2b2a1f04a2d7244df706d5ea9"


@lru_cache(maxsize=1)
def font_for():
    if (
        not FONT_PATH.is_file()
        or hashlib.sha256(FONT_PATH.read_bytes()).hexdigest() != FONT_SHA256
    ):
        raise ValueError(
            "Bundled OFL typeface missing or changed. Reinstall AgentBeatVideo."
        )
    with TTFont(FONT_PATH, lazy=True) as face:
        family = face["name"].getDebugName(1)
        cmap = frozenset(face.getBestCmap())
    return str(FONT_PATH), 0, family, cmap


def check_glyphs(text, cmap):
    missing = list(
        dict.fromkeys(c for c in text if not c.isspace() and ord(c) not in cmap)
    )
    if missing:
        raise ValueError("Noto Sans SC lacks these glyphs: " + "".join(missing))


def fixed_caption(plan, folder):
    path, _, family, cmap = font_for()
    check_glyphs(plan.caption, cmap)
    w, h = plan.resolution, plan.resolution * 16 // 9
    max_width = round(0.83 * w)
    # Fit actual ink bounds, including the outline, before drawing the one reusable layer.
    for size in range(round(w * 0.076), max(12, round(w * 0.025)) - 1, -2):
        font = ImageFont.truetype(path, size)
        stroke = max(2, round(size * 0.045))
        lines = []
        for paragraph in plan.caption.splitlines():
            lines.extend(wrap(paragraph, font, max_width - 2 * stroke) or [""])
        text = "\n".join(lines)
        spacing = round(size * 0.34)
        draw = ImageDraw.Draw(Image.new("L", (1, 1)))
        left, top, right, bottom = draw.multiline_textbbox(
            (0, 0),
            text,
            font=font,
            spacing=spacing,
            align="center",
            stroke_width=stroke,
        )
        ink_w, ink_h = math.ceil(right - left), math.ceil(bottom - top)
        if ink_w <= max_width and ink_h <= h * 0.38:
            break
    else:
        raise ValueError("Caption does not fit the safe area.")
    pad = stroke + 2
    tile = Image.new("RGBA", (ink_w + 2 * pad, ink_h + 2 * pad))
    ImageDraw.Draw(tile).multiline_text(
        (pad - left, pad - top),
        text,
        font=font,
        spacing=spacing,
        align="center",
        fill=(255, 251, 243, 255),
        stroke_width=stroke,
        stroke_fill=(27, 35, 39, 255),
    )
    # YUV 4:2:0 overlay coordinates are rounded down to even pixels by FFmpeg.
    x = ((w - tile.width) // 2) & ~1
    y = (round(0.74 * h) - tile.height // 2) & ~1
    tile.save(folder / "caption.png")
    return dict(
        text=plan.caption,
        font=family,
        font_version="2.004",
        font_license="OFL-1.1",
        font_sha256=FONT_SHA256,
        start_frame=0,
        duration_frames=plan.total_frames,
        lines=len(lines),
        x=x,
        y=y,
        safe_box=[x, y, x + tile.width, y + tile.height],
        font_size=size,
        glyphs_present=True,
    )


def timestamp(frames, fps):
    centis = round(frames * 100 / fps)
    return f"{centis // 360000}:{centis // 6000 % 60:02}:{centis // 100 % 60:02}.{centis % 100:02}"


def wrap(text, font, width):
    lines = []
    line = ""
    for c in text:
        if line and font.getlength(line + c) > width:
            lines.append(line.rstrip())
            line = ""
        line += c
    if line.strip():
        lines.append(line.strip())
    return lines


def subtitles(plan, folder):
    w, h = plan.resolution, plan.resolution * 16 // 9
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
"""
    fontdir = folder / "fonts"
    fontdir.mkdir(exist_ok=True)
    styles = []
    events = []
    checked = []
    for i, event in enumerate(plan.text_events):
        path, index, family, cmap = font_for()
        check_glyphs(event.text, cmap)
        target = fontdir / Path(path).name
        if not target.exists():
            shutil.copyfile(path, target)
        title = event.role == "title"
        size = round(w * (0.099 if title else 0.063))
        margin = round(0.085 * w)
        font = ImageFont.truetype(path, size, index=index)
        lines = wrap(event.text, font, w - 2 * margin - round(0.02 * w))
        lineheight = round(size * 1.52)
        y = round(h * (0.71 if title else 0.74)) - lineheight * (len(lines) - 1)
        if y < round(0.13 * h):
            raise ValueError("Text exceeds the safe area")
        outline = round(w * 0.0026, 2)
        styles.append(
            f"Style: S{i},{family},{size},&H00F4FAFF,&H00F4FAFF,&H68242120,&H850E1820,0,0,0,0,100,100,0,0,1,{outline},2,7,0,0,0,1"
        )
        start = timestamp(event.start_frame, plan.fps)
        end = timestamp(event.start_frame + event.duration_frames, plan.fps)

        def line_event(layer, body):
            events.append(f"Dialogue: {layer},{start},{end},S{i},,0,0,0,,{body}")

        if event.template == "cinematic":
            length = round(w * 0.075)
            line_event(
                0,
                rf"{{\an7\pos({margin},{y - round(w * 0.027)})\fad(240,200)\bord0\shad0\1c&H99DAF5&\p1}}m 0 0 l {length} 0 {length} 3 0 3",
            )
        letters = 0
        available_ms = event.duration_frames / plan.fps * 1000
        pace = min(60, available_ms * 0.55 / max(1, len(event.text)))
        for j, line in enumerate(lines):
            yy = y + j * lineheight
            if event.template == "cinematic":
                tags = (
                    rf"\an7\move({margin},{yy + 12},{margin},{yy},0,460)\fad(260,200)"
                )
            elif event.template == "clean_pop":
                tags = rf"\an7\pos({margin},{yy})\fscx92\fscy92\t(0,180,\fscx100\fscy100)\fad(100,150)"
            else:
                tags = rf"\an7\pos({margin},{yy})\fad(0,160)"
                parts = []
                for char in line:
                    begin = round(letters * pace)
                    parts.append(
                        rf"{{\alpha&HFF&\t({begin},{begin + 90},\alpha&H00&)}}" + char
                    )
                    letters += 1
                line = "".join(parts)
            line_event(1, "{" + tags + "}" + line)
        checked.append(
            dict(
                text=event.text,
                font=family,
                glyphs_present=True,
                lines=len(lines),
                safe_box=[margin, y, w - margin, y + lineheight * len(lines)],
            )
        )
    (folder / "captions.ass").write_text(
        header
        + "\n".join(styles)
        + "\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
        + "\n".join(events)
        + "\n",
        encoding="utf-8",
    )
    return checked
