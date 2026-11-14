"""Generate lightweight transparent action frames for the supplied single-pose creature art.
These are short cutout animation proxies, not hand-animated source sprite sheets.
Guard sprites keep the original supplied individual action frames.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image,ImageEnhance
import math

ROOT=Path(__file__).resolve().parents[1]/'game'/'assets'/'r7'
OUT=ROOT/'animations';OUT.mkdir(exist_ok=True)
KINDS=[f'{k}_{i}' for k in ['wolf','boar','spider','ghoul','swamp','raven'] for i in (0,1)]+[f'hostile_{i}' for i in range(5)]
COUNT={'idle':3,'run':4,'sprint':4,'attack':5,'hurt':2,'death':4,'dodge':3}

for key in KINDS:
    original=Image.open(ROOT/f'{key}.png').convert('RGBA')
    # Neutral 64px canvas accommodates large creatures and the 48x64 bandit silhouettes.
    src=Image.new('RGBA',(80,80))
    src.alpha_composite(original,((80-original.width)//2,80-original.height-7))
    for action,n in COUNT.items():
        for index in range(n):
            frame=Image.new('RGBA',(80,80))
            t=index/max(1,n-1)
            x=y=0
            changed=src
            if action=='idle':y=[0,-1,0][index]
            elif action in ['run','sprint']:
                x=(-2,0,2,0)[index];y=(0,-3,0,-2)[index]
            elif action=='attack':
                x=(0,0,4,7,1)[index];y=(0,-1,-3,-2,0)[index]
            elif action=='dodge':x=(-6,-2,5)[index];y=(-1,-4,0)[index]
            elif action=='hurt':x=(0,-2)[index];changed=ImageEnhance.Color(src).enhance(0.50 if index==0 else 0.85)
            elif action=='death':
                changed=src.rotate((0,20,55,78)[index],resample=Image.Resampling.NEAREST,expand=False,center=(40,65));y=(0,2,7,13)[index]
                changed=changed.copy();changed.putalpha(changed.getchannel('A').point(lambda a:int(a*(1-0.19*index))))
            frame.alpha_composite(changed,(x,y))
            frame.save(OUT/f'{key}_{action}_{index}.png', optimize=True)
print('Created',len(KINDS)*sum(COUNT.values()),'action-frame PNGs in',OUT)
