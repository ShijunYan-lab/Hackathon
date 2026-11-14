"""Build a source handoff zip from an explicit allowlist, without runtime data or secrets."""
from pathlib import Path
import hashlib
import json
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'dist/c-world-backend-source.zip'
    output.parent.mkdir(exist_ok=True)
    files = [root / 'requirements.txt', root / 'requirements-build.txt']
    for folder in ('server', 'shared'):
        files.extend(path for path in (root / folder).rglob('*') if path.is_file()
                     and path.suffix in ('.py', '.json', '.html', '.css', '.js') and '__pycache__' not in path.parts)
    files.extend(root / 'docs' / name for name in ('BACKEND_QUICKSTART.md', 'COMBAT_API.md',
        'WORLD_ACTIONS_CONTRACT.md', 'EVALUATION_BACKEND.md', 'WORLD_ECONOMY.md', 'C_BACKEND_HANDOFF.md'))
    files.append(root / 'team/C_WORLD/STATUS.md')
    manifest = {str(path.relative_to(root)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in files}
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root))
        archive.writestr('MANIFEST.json', json.dumps(manifest, indent=2))
    print(output)
    print('SHA256', hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
