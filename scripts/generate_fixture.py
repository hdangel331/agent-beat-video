"""Build ten illustrated stills, five moving clips and original 120 BPM music."""
import argparse
import math
from pathlib import Path
import subprocess
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageColor

PALETTES = [
    ("ffe5ab", "ef9774", "ffda75", "ac716e", "735c6a", "304755", "192e3d"),
    ("cadfd0", "79b5b1", "ffe7a4", "87a49c", "4c8790", "2f6471", "183c51"),
    ("e2c9e4", "9ba4c7", "fff0c7", "a39ab3", "767a9b", "4a577a", "293854"),
    ("f4d093", "dd9072", "fff2bb", "b4876a", "906e62", "5e5d58", "303e43"),
    ("b9dfdb", "94c5be", "fce5a9", "87aba7", "518d95", "366a7b", "23485a"),
]

def rgb(code):
    return ImageColor.getrgb("#" + code)

def landscape(i, size):
    w, h = size
    rng = np.random.default_rng(820 + i)
    sky, horizon, sun, *layers = map(rgb, PALETTES[i % len(PALETTES)])
    y = np.linspace(0, 1, h)[:, None, None]
    blend = np.clip(y * 1.6, 0, 1)
    canvas = np.broadcast_to((1-blend)*sky + blend*horizon, (h, w, 3)).astype("uint8").copy()
    image = Image.fromarray(canvas)
    d = ImageDraw.Draw(image)
    sx, sy = int(w*rng.uniform(.25,.76)), int(h*rng.uniform(.26,.44))
    r = int(w*rng.uniform(.09,.16))
    d.ellipse((sx-r,sy-r,sx+r,sy+r),fill=sun)
    for k in range(4):
        origin = .43 + k*.112
        xp = np.linspace(-.1,1.1,9 + k)
        ridges = rng.uniform(-.115,.09,len(xp))
        peaks = []
        for x in range(w):
            u=x/w
            fine = .008*math.sin(u*48+i+k) + .003*math.sin(u*112+i)
            yy=origin+np.interp(u,xp,ridges)+fine
            peaks.append((x, round(h*yy)))
        d.polygon([(0,h),*peaks,(w,h)],fill=layers[k])
        # fine contours below the ridge follow the same eroded surface
        for j in range(4):
            start=int(rng.uniform(.01,.65)*w)
            stop=min(w,start+int(rng.uniform(.13,.37)*w))
            delta=int(h*(.009+j*.007))
            color=tuple(int(c*.88+b*.12) for c,b in zip(layers[k],sun))
            d.line([(x,peaks[x][1]+delta+int(2*math.sin(x*.045))) for x in range(start,stop)],fill=color,width=1)
    if i % 3 == 0:
        sea=int(h*.76)
        d.rectangle((0,sea,w,h), fill=layers[2])
        for j in range(320):
            yy=int(rng.integers(sea,h))
            xx=int(rng.integers(0,w))
            length=int(rng.uniform(.007,.09)*w)
            bright=abs(xx-sx)<(yy-sea)*.48+w*.035
            color=tuple(int(c*.64+b*.36) for c,b in zip(layers[2],sun if bright else layers[1]))
            d.line((xx,yy,min(w,xx+length),yy), fill=color,width=1)
    for j in range(3+i%4):
        x0=int(w*(.18+j*.067))+i%31
        y0=int(h*.35+math.sin(j+i)*h*.019)
        scale=max(3,w//105)
        d.line([(x0-scale,y0-2),(x0,y0+1),(x0+scale,y0-3)],fill=layers[2],width=2)
    grain=rng.normal(0,1.8,(h,w,1))
    return Image.fromarray(np.clip(np.asarray(image)+grain,0,255).astype("uint8"))

def soundtrack(path):
    sr, duration, beat = 44100, 24, .5
    audio = np.zeros(sr*duration)
    rng = np.random.default_rng(204)
    def add(time, data):
        start=round(sr*time)
        n=min(len(data),len(audio)-start)
        if n>0: audio[start:start+n] += data[:n]
    def time(s): return np.arange(round(sr*s))/sr
    notes = [(57,60,64,67),(53,57,60,64),(48,52,55,59),(55,59,62,65)]
    for b in range(48):
        chord=notes[(b//8)%4]
        t=time(.32)
        add(b*beat,.54*np.sin(2*np.pi*(49*t+3*(1-np.exp(-35*t))))*np.exp(-14*t))
        t=time(.18)
        if b%2: add(b*beat,.13*rng.normal(size=len(t))*np.exp(-24*t))
        for half in range(2):
            t=time(.09)
            noise=rng.normal(size=len(t)+1)
            add(b*beat+half*.25,.054*np.diff(noise)*np.exp(-65*t))
        midi=chord[(b*3+b//4)%4]+12
        f=440*2**((midi-69)/12)
        t=time(.75)
        pluck=(np.sin(2*np.pi*f*t)+.23*np.sin(4*np.pi*f*t))*np.exp(-6*t)*(1-np.exp(-120*t))
        add(b*beat+.125,.18*pluck)
        add(b*beat+.375,.045*pluck)
        t=time(.44)
        f=440*2**((chord[0]-12-69)/12)
        add(b*beat,.18*np.sin(2*np.pi*f*t)*np.exp(-5*t)*(1-np.exp(-45*t)))
        if b%8==0:
            t=time(3.95)
            pad=sum(np.sin(2*np.pi*440*2**((k-69)/12)*t) for k in chord)
            add(b*beat,.035*pad*np.minimum(1,t/.22)*np.minimum(1,(3.95-t)/.35))
    audio*=.86/np.max(abs(audio))
    stereo=np.stack([audio,audio*.94+np.roll(audio,550)*.06],axis=1)
    with wave.open(str(path),"wb") as f:
        f.setparams((2,2,sr,0,"NONE","not compressed"))
        f.writeframes((stereo*32767).astype("<i2").tobytes())

def generate(root):
    assets=root/"assets"
    music=root/"music"
    for folder in [assets,music]: folder.mkdir(parents=True,exist_ok=True)
    if any(assets.glob("ridge-*")) or (music/"tide.wav").exists():
        raise ValueError("Demo already exists. Choose an empty demo folder.")
    for i in range(10):
        size=(960,540) if i in (1,4,8) else (720,1280)
        landscape(i,size).save(assets/f"ridge-{i:02}.jpg",quality=93)
    for i in range(5):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            still=Path(tmp)/"source.png"
            landscape(i+10,(720,1280)).save(still)
            vf="scale=1080:-2,zoompan=z='1.05+on*0.0008':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=150:s=540x960:fps=25"
            subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(still),"-vf",vf,"-frames:v","150","-c:v","libx264","-threads","2","-preset","veryfast","-pix_fmt","yuv420p",str(assets/f"ridge-motion-{i}.mp4")],check=True)
    soundtrack(music/"tide.wav")
    print(f"10 stills, 5 clips and one 24 s / 120 BPM original track in {root}")

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    generate(parser.parse_args().root.resolve())
