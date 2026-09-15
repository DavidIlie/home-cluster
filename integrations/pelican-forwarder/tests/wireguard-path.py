import socket
import struct
import subprocess
import uuid

KUBECTL = ['kubectl', '--kubeconfig', '/Users/david/dev/home-cluster/kubeconfig']
OWNER = str(uuid.uuid4())
HOST = 'wireguard-test.mc-forward.davidapps.dev'

def route(method):
    code = "$f=app(DavidApps\\Forwarder\\Services\\Forwarder::class);$f->request('" + method + "',['hostname'=>'" + HOST + "','owner'=>'" + OWNER + "','backend'=>'192.168.100.163:25599']);"
    subprocess.run(KUBECTL + ['exec', 'deploy/pelican', '--', 'php', 'artisan', 'tinker', '--execute=' + code], check=True, stdout=subprocess.DEVNULL)

def varint(n):
    result = bytearray()
    while n > 127:
        result.append((n & 127) | 128)
        n >>= 7
    result.append(n)
    return bytes(result)

backend = None
try:
    route('PUT')
    backend = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', 'david@192.168.100.163', 'python3 -u -'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    backend.stdin.write("""import socket
s=socket.socket()
s.settimeout(25)
s.bind(('192.168.100.163',25599))
s.listen(1)
print('READY',flush=True)
c,a=s.accept()
c.settimeout(5)
assert c.recv(2048)
c.sendall(b'WIREGUARD_FORWARD_OK')
c.close()
s.close()
""")
    backend.stdin.close()
    assert backend.stdout.readline().strip() == 'READY', 'Test listener did not start'
    host = HOST.encode()
    packet = b'\x00' + varint(765) + varint(len(host)) + host + struct.pack('>H', 25565) + b'\x01'
    with socket.create_connection(('79.76.102.151', 25565), timeout=10) as client:
        client.sendall(varint(len(packet)) + packet + b'\x01\x00')
        assert client.recv(1024) == b'WIREGUARD_FORWARD_OK', 'Unexpected relay response'
    print('PASS: public Minecraft handshake -> mc-router -> WireGuard -> Wings host allocation')
finally:
    route('DELETE')
    if backend is not None:
        backend.wait(timeout=30)
