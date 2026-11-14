"""Static Godot source/resource checks; deliberately NOT a GDScript compiler."""
from pathlib import Path
import re
import json
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'

def check():
    checked=0;errors=[]
    for p in sorted(GAME.rglob('*')):
        if p.suffix not in ('.gd','.tscn','.tres','.godot','.gdshader'):continue
        if '.godot' in p.parts:continue
        text=p.read_text(encoding='utf-8-sig')
        for resource in re.findall(r'"(res://[^"\n]+)"',text):
            if '%' in resource:continue
            if Path(resource).suffix not in ('.gd','.tscn','.tres','.png','.svg','.gdshader','.json'):continue
            if not (GAME/resource[6:]).is_file():errors.append(f'{p.relative_to(ROOT)}: missing {resource}')
            checked+=1
        if p.suffix=='.gd':
            names=re.findall(r'^(?:@export\s+)?(?:var|const|signal)\s+(\w+)',text,re.M)
            if len(names)!=len(set(names)):errors.append(f'{p.relative_to(ROOT)}: repeated top-level declaration')
            parent=re.search(r'^extends\s+"res://([^"\n]+)"',text,re.M)
            visited=set()
            while parent:
                base=GAME/parent.group(1)
                if base in visited or not base.exists():break
                visited.add(base)
                source=base.read_text(encoding='utf-8-sig')
                inherited=set(re.findall(r'^(?:@export\s+)?(?:var|const|signal)\s+(\w+)',source,re.M))
                conflict=inherited.intersection(names)
                if conflict:errors.append(f'{p.relative_to(ROOT)}: inherited member conflict {sorted(conflict)}')
                parent=re.search(r'^extends\s+"res://([^"\n]+)"',source,re.M)
    for relative in ('maps/backend_world.json','maps/director_locations.json'):
        json.loads((GAME/relative).read_text(encoding='utf-8'))
    return checked,errors

if __name__=='__main__':
    count,errors=check()
    print(f'Static checks: {count} literal resource references; {len(errors)} problems.')
    for error in errors:print(error)
    print('This does not compile GDScript or validate visual/runtime behavior. Run Test_Game.bat with Godot locally.')
    raise SystemExit(bool(errors))
