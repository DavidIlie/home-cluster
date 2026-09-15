import hmac
import json
import os
import re
import subprocess
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE = Path(os.environ.get('FORWARDER_STATE', '/root/mc-router/data/routes.json'))
TOKEN = os.environ['FORWARDER_TOKEN']
LOCK = threading.Lock()
HOST = re.compile(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$')
UUID = re.compile(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
BACKEND = re.compile(r'192\.168\.100\.163:([0-9]{1,5})$')


def validate(host, owner, backend):
    match = BACKEND.fullmatch(backend)
    return bool(HOST.fullmatch(host) and UUID.fullmatch(owner) and match and 1024 <= int(match[1]) <= 65535)


def save(state):
    fd, name = tempfile.mkstemp(dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(state, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o644)
        os.replace(name, STATE)
        directory = os.open(STATE.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def dispatch(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN):
            return self.reply(401, {'error': 'Unauthorized'})
        if self.path != '/routes':
            return self.reply(404, {'error': 'Not found'})
        try:
            with LOCK:
                state = json.loads(STATE.read_text())
                if self.command == 'GET':
                    with urllib.request.urlopen('http://127.0.0.1:8092/routes', timeout=3) as response:
                        active = json.load(response)
                    return self.reply(200, {'mappings': state['mappings'], 'owners': state['owners'], 'active': active})
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 2048:
                    return self.reply(400, {'error': 'Invalid body length'})
                body = json.loads(self.rfile.read(length))
                host, owner, backend = (body.get(k, '') for k in ('hostname', 'owner', 'backend'))
                if not all(isinstance(v, str) for v in (host, owner, backend)) or not validate(host, owner, backend):
                    return self.reply(422, {'error': 'Invalid route'})
                if host in state['mappings'] and state['owners'].get(host) != owner:
                    return self.reply(409, {'error': 'Hostname belongs to another server'})
                if self.command == 'PUT':
                    state['mappings'][host] = backend
                    state['owners'][host] = owner
                else:
                    state['mappings'].pop(host, None)
                    state['owners'].pop(host, None)
                save(state)
                subprocess.run(['/usr/bin/docker', 'kill', '--signal=HUP', 'mc-router-router-1'], check=True, capture_output=True, timeout=10)
                return self.reply(200, {'saved': True})
        except (ValueError, TypeError):
            return self.reply(400, {'error': 'Invalid request'})
        except Exception:
            return self.reply(503, {'error': 'Router unavailable; retry synchronization'})

    do_GET = dispatch
    do_PUT = dispatch
    do_DELETE = dispatch


if __name__ == '__main__':
    ThreadingHTTPServer(('192.168.2.5', 8091), Handler).serve_forever()
