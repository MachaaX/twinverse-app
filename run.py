#!/usr/bin/env python3
"""Run with Python 3.10+: python3 run.py"""
import argparse
import os
import sys
from backend.cloud_storage import load_environment, CloudStorageError

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='TwinVerse local sample prototype')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    try:load_environment()
    except CloudStorageError as exc:sys.exit(str(exc))
    # Load configuration before importing the optional AI service, too.
    from backend.server import make_server
    try:server=make_server(args.port)
    except (OSError,ValueError) as exc:
        sys.exit(f'Could not start the server: {exc}. Try python3 run.py --port 8001')
    dev=server.developer_password if not os.environ.get('TWINVERSE_DEVELOPER_PASSWORD') else '(set by TWINVERSE_DEVELOPER_PASSWORD)'
    address=server.public_origin or f'http://127.0.0.1:{args.port}'
    print(f'\nTwinVerse is ready at {address}\nCreate an account as Medical student or Faculty.\nAccount storage: {server.auth.mode}\nDeveloper password: {dev}\n\nPress Ctrl+C to stop.\n',flush=True)
    storage=server.cloud_storage.status()
    print('Approval storage: '+('AWS (PostgreSQL + S3)' if storage['enabled'] else 'local SQLite'),flush=True)
    if storage['errors']:print('Cloud setup: '+' '.join(storage['errors']))
    server.speech.start()
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nStopped.')
    finally:
        server.server_close();server.speech.close()
        if not server.speech.thread.is_alive():server.store.db.close()
