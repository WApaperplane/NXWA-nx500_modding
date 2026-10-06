import socket
import time
import re
import base64

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


def fetch(path, pcname):
    run('/opt/usr/nx-ks/busybox base64 %s > /tmp/x.b64' % path, 8.0)
    r = run('wc -c /tmp/x.b64')
    m = re.search(r'(\d+)', r.split('/tmp/x.b64')[0])
    sz = int(m.group(1)) if m else 0
    print('  b64 size', sz, flush=True)
    buf = ''
    for k in range(1, sz // 700 + 2):
        rr = run('sed -n %d,%dp /tmp/x.b64' % ((k - 1) * 700 + 1, k * 700), 1.6)
        for ln in rr.split('\n'):
            t = ln.strip()
            if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
                buf += t
    data = base64.b64decode(buf + '===')
    open(pcname, 'wb').write(data)
    print('  saved %d bytes -> %s' % (len(data), pcname), flush=True)
    return len(data)


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

print('=== libudd5.so ===', flush=True)
print(run('ls -la /usr/lib/libudd5.so')[:200])
fetch('/usr/lib/libudd5.so', r'D:\download\NX-KS2-88\test_server\pwfilter\libudd5.so')

print()
print('=== libd5_ipcc 相关?找所有 d5/ipcc/sma 库 ===', flush=True)
print(run('ls /usr/lib/ | grep -iE "d5|ipcc|sma|udd|drime"')[:500])

print()
print('=== 主应用 ELF (取回分析) ===', flush=True)
print(run('ls -la /usr/apps/com.samsung.di-camera-app/bin/di-camera-app')[:200])
fetch('/usr/apps/com.samsung.di-camera-app/bin/di-camera-app',
      r'D:\download\NX-KS2-88\test_server\pwfilter\di-camera-app')

s.close()
