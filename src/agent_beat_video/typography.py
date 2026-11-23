import os
import shutil
import subprocess
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import ImageFont


def font_for(template):
    path = os.getenv("ABV_FONT")
    preferred = "Noto Serif CJK SC" if template == "cinematic" else "Noto Sans CJK SC"
    index = 0
    if not path and shutil.which("fc-match"):
        match = subprocess.check_output(
            ["fc-match", "-f", "%{file}\n%{index}", preferred], text=True
        ).splitlines()
        path, index = match[0], int(match[1] or 0)
    if not path and os.name == "nt":
        path = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc")
    if not path or not Path(path).is_file():
        raise ValueError("Set ABV_FONT to a licensed Chinese .ttf/.otf/.ttc font.")
    face = TTFont(path, fontNumber=index, lazy=True)
    name = face["name"].getDebugName(16) or face["name"].getDebugName(1)
    cmap = set(face.getBestCmap())
    face.close()
    return path, index, name, cmap


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
        path, index, family, cmap = font_for(event.template)
        missing = [c for c in event.text if not c.isspace() and ord(c) not in cmap]
        if missing:
            raise ValueError(
                "Font lacks required glyphs: " + "".join(dict.fromkeys(missing))
            )
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
