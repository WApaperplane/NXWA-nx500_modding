import socket
import time
import re
import struct

s = socket.create_connection(('192.168.0.105', 23), timeout=20)
s.settimeout(4.0)


def drain(t=4.0):
    end = time.time() + t
    out = b''
    while time.time() < end:
        try:
            c = s.recv(65536)
        except socket.timeout:
            continue
        if not c:
            break
        out += c
    cl = bytearray()
    i = 0
    while i < len(out):
        if out[i] == 0xFF and i + 2 < len(out):
            i += 3
            continue
        cl.append(out[i])
        i += 1
    return bytes(cl).decode('utf-8', 'replace')


def run(c, w=4.0):
    s.sendall((c + '\n').encode())
    time.sleep(0.5)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

LIB = '/usr/lib/libSLP-db-util.so.0.1.0'
print(run('ls -la ' + LIB))
print()

# base64 取回文件
run('/opt/usr/nx-ks/busybox base64 %s > /tmp/slp.b64' % LIB, 6.0)
r = run('wc -c /tmp/slp.b64')
m = re.search(r'(\d+)\s*/tmp/slp.b64', r)
size = int(m.group(1)) if m else 0
print('b64 size:', size)

buf = ''
CH = 700
for k in range(1, size // CH + 2):
    rr = run('sed -n %d,%dp /tmp/slp.b64' % ((k - 1) * CH + 1, k * CH), 1.8)
    for ln in rr.split('\n'):
        t = ln.strip()
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
            buf += t

import base64
data = base64.b64decode(buf + '===')
print('文件大小:', len(data))
open(r'D:\download\NX-KS2-88\test_server\pwfilter\libSLP-db-util.so', 'wb').write(data)
print('已保存到 PC')
s.close()
