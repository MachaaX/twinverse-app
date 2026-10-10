#!/usr/bin/env python3
"""Run with Python 3.10+: python3 run.py"""
import argparse
import os
import sys
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
    print('[Startup] Loaded .env file')
except ImportError:
    print('[Startup] python-dotenv not available, skipping .env load')

from backend.server import make_server

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='TwinVerse local sample prototype')
    parser.add_argument('--port',type=int,default=8000)
    args=parser.parse_args()
    try:server=make_server(args.port)
    except OSError as exc:
        sys.exit(f'Could not start the server: {exc}. Try python3 run.py --port 8001')
    shown=server.faculty_password if server.faculty_password_source=='default' else '(set by TWINVERSE_FACULTY_PASSWORD)'
    dev=server.developer_password if not os.environ.get('TWINVERSE_DEVELOPER_PASSWORD') else '(set by TWINVERSE_DEVELOPER_PASSWORD)'
    print(f'\nTwinVerse is ready at http://127.0.0.1:{args.port}\nLocal demo only • Synthetic samples • No API keys required\n\nFaculty password: {shown}\nDeveloper password: {dev}\n\nPress Ctrl+C to stop.\n',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:print('\nStopped.')
    finally:server.server_close();server.store.db.close()
