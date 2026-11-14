"""Create deterministic small transparent R8 icons from project-owned sprite sources.

Run with: python tools/build_r8_icons.py
Requires Pillow only. R8 ships the generated PNGs, so running this is optional.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / 'game'
OUT = ROOT / 'assets' / 'r7'
OUT.mkdir(parents=True, exist_ok=True)
SOURCE = ROOT / 'actors' / 'assets' / 'weapons' / 'sword.png'

def coin():
    im = Image.new('RGBA', (48,48)); d = ImageDraw.Draw(im)
    for x,y,r in ((19,26,12),(27,22,12),(22,17,10)):
        d.ellipse((x-r+1,y-r+1,x+r+1,y+r+1), fill='#4b3525',outline='#271e21',width=2)
        d.ellipse((x-r+2,y-r+2,x+r-2,y+r-2), fill='#b58d45',outline='#e1c977',width=2)
        d.arc((x-r+5,y-r+5,x+r-5,y+r-5),30,220,fill='#ffde8a',width=2)
        d.line([(x-2,y+3),(x+2,y-3)], fill='#75522f',width=2)
    im.save(OUT/'coin.png')

def rock():
    p=OUT/'iron.png'
    im=Image.open(p).convert('RGBA'); px=im.load()
    for y in range(im.height):
        for x in range(im.width):
            r,g,b,a=px[x,y]
            if a:
                v=int(0.32*r+0.45*g+0.23*b)
                px[x,y]=(min(255,int(v*0.92)+12),min(255,int(v*0.96)+13),min(255,int(v*1.04)+15),a)
    im.save(OUT/'stone.png')

def sword():
    src=Image.open(SOURCE).convert('RGBA').resize((48,48), Image.Resampling.NEAREST)
    for i in range(5):
        im=src.copy()
        if i:
            px=im.load()
            for y in range(48):
                for x in range(48):
                    r,g,b,a=px[x,y]
                    if not a:continue
                    boost=i*12
                    px[x,y]=(min(255,r+boost),min(255,g+boost//2),min(255,b+(16 if i>=3 else 0)),a)
        im.save(OUT/f'sword_{i}.png')

def gear(kind,quality):
    im=Image.new('RGBA',(48,48));d=ImageDraw.Draw(im)
    metal=['#797367','#9699a1','#b7bbc5','#cca65a','#e6bd72'][quality]
    shine=['#aaa08b','#c9d3d5','#ecedef','#f6da8a','#f8e2b9'][quality]
    shadow='#2b2627';leather='#635043';bright='#a07851'
    if kind=='armor':
        pts=[(17,8),(31,8),(35,14),(44,18),(40,29),(36,28),(36,41),(12,41),(12,28),(8,29),(4,18),(13,14)]
        d.polygon(pts, fill=leather,outline=shadow);d.polygon([(18,11),(30,11),(36,19),(33,38),(15,38),(12,19)],fill=metal,outline=shadow)
        d.polygon([(18,10),(24,15),(30,10)],fill=shadow)
        d.line([(16,19),(32,19)],fill=shine,width=2)
        d.line([(24,20),(24,37)],fill=bright,width=2)
        d.rectangle((15,36,33,39),fill=shadow);d.rectangle((20,36,28,39),fill=shine)
    if kind=='helmet':
        d.arc((11,7,37,38),180,359,fill=shadow,width=8)
        d.polygon([(9,23),(12,14),(17,8),(31,8),(36,14),(39,23),(36,34),(32,32),(28,27),(20,27),(16,32),(12,34)],fill=metal,outline=shadow)
        d.polygon([(17,22),(31,22),(29,31),(19,31)],fill=shadow)
        d.line([(15,16),(33,16)],fill=shine,width=2)
        d.line([(24,10),(24,22)],fill=shine,width=2)
    if kind=='boots':
        for off in [-9,9]:
            x=24+off
            d.polygon([(x-6,10),(x+4,10),(x+6,31),(x+8,34),(x+9,40),(x-9,40),(x-10,35),(x-6,28)],fill=metal,outline=shadow)
            d.line([(x-6,17),(x+5,17)],fill=shine,width=2)
            d.line([(x-8,37),(x+8,37)],fill=shadow,width=3)
    im.save(OUT / f'{kind}_{quality}.png')

def fallback():
    im=Image.new('RGBA',(48,48));d=ImageDraw.Draw(im)
    d.ellipse((7,10,41,44),fill='#312c29');d.polygon([(15,14),(32,14),(38,26),(32,38),(13,38),(9,27)],fill='#887253',outline='#342923')
    d.rectangle((21,21,27,32),fill='#e2c78d');d.rectangle((21,34,27,37),fill='#e2c78d')
    im.save(OUT/'unknown_item.png')

if __name__=='__main__':
    coin();rock();sword();fallback()
    for kind in ['armor','helmet','boots']:
        for i in range(5):gear(kind,i)
    print('Generated 25 transparent icons in',OUT)
