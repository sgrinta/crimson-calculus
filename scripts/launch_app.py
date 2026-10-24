"""Open an existing Crimson instance or start one from the Finder launcher."""
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import threading
import time
from urllib.request import urlopen
import webbrowser

PROJECT = Path(__file__).resolve().parents[1]


def is_crimson(url):
    try:
        with urlopen(url + '/health', timeout=1) as response:
            health = json.load(response)
        return health.get('status') == 'ok' and health.get('app') == 'Crimson Calculus'
    except (OSError, ValueError, AttributeError):
        return False


def port_occupied(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
            return True
    except OSError:
        return False


def open_when_ready(url):
    for _ in range(60):
        if is_crimson(url):
            webbrowser.open(url)
            return
        time.sleep(.5)
    print(f'If the browser has not opened, visit {url} once the server is ready.', flush=True)


def main():
    try:
        port = int(os.environ.get('PORT', '8069'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        print('PORT must be a number from 1 to 65535.')
        return 1
    url = f'http://127.0.0.1:{port}'
    if is_crimson(url):
        print(f'Crimson Calculus is already running. Opening {url}')
        webbrowser.open(url)
        return 0
    if port_occupied(port):
        print(f'Port {port} is in use, but Crimson Calculus is not ready there. '
              'Wait a few seconds and try again, or use a different PORT.')
        return 1
    os.chdir(PROJECT)
    sys.path.insert(0, str(PROJECT))
    print('Starting Crimson Calculus. Your browser will open when it is ready.\n'
          'Keep this Terminal window open; press Control+C to stop the app.', flush=True)
    threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    try:
        # Run in this process; the app disables the reloader. No extra server tree.
        runpy.run_path(str(PROJECT / 'app.py'), run_name='__main__')
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
