"""Build a fresh Windows backend directory and zip; never overwrite an old run's data."""
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    tag = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output = root / 'dist' / ('c-world-win-' + tag)
    command = [sys.executable, '-m', 'PyInstaller', '--onedir', '--name', 'CWorldBackend',
        '--distpath', str(output), '--workpath', str(root / 'build' / tag), '--specpath', str(root / 'build'),
        '--paths', str(root), '--collect-submodules', 'server', '--collect-submodules', 'shared',
        '--collect-submodules', 'uvicorn']
    # Only code/config sources. No dotenv, database, logs, private prompts or environment folders.
    for folder in ('server', 'shared'):
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and path.suffix in ('.py', '.json', '.html', '.css', '.js') and '__pycache__' not in path.parts:
                command.extend(['--add-data', str(path) + ';' + str(path.relative_to(root).parent)])
    command.append(str(root / 'server/launch.py'))
    subprocess.run(command, cwd=root, check=True)
    package = shutil.make_archive(str(output), 'zip', root_dir=output)
    print('WINDOWS_PACKAGE', package)
    print('EXECUTABLE', output / 'CWorldBackend/CWorldBackend.exe')


if __name__ == '__main__':
    main()
