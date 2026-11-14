"""Source and Windows bundle entry point; writable data always lives outside the bundle."""
import argparse
import os
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser(description='C world backend, one worker')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--db', default=os.environ.get('WORLD_DB_PATH', 'runtime/worlds.sqlite3'))
    args = parser.parse_args()
    os.environ['WORLD_DB_PATH'] = str(Path(args.db).resolve())
    from server.main import app
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == '__main__':
    main()
