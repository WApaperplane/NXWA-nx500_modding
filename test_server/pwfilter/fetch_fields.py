import socket
import time
import re

s = socket.create_connection(('192.168.0.105', 23), timeout=15)
s.settimeout(3.0)


def drain(t=2.0):
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


def run(c, w=2.0):
    s.sendall((c + '\n').encode())
    time.sleep(0.5)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

r = run('prefman info 0 > /tmp/pi.txt 2>&1; wc -l /tmp/pi.txt')
print('总行数:', r.strip()[-30:])
time.sleep(2.0)

# 用 base64 分块取回, 避免控制字符/回显污染
run('/opt/usr/nx-ks/busybox base64 /tmp/pi.txt > /tmp/pi.b64', 6.0)
r = run('wc -c /tmp/pi.b64')
print('b64 大小:', r.strip()[-30:])

size = int(re.search(r'(\d+)\s*/tmp/pi.b64', r).group(1)) if re.search(r'(\d+)\s*/tmp/pi.b64', r) else 0
print('源文件约', size * 3 // 4, '字节')

# 分块取 b64
CH = 700
lines = size // CH + 2
buf = ''
for k in range(1, lines + 1):
    st = (k - 1) * CH + 1
    en = k * CH
    rr = run('sed -n %d,%dp /tmp/pi.b64' % (st, en), 1.6)
    for ln in rr.split('\n'):
        t = ln.strip()
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
            buf += t
print('取回 b64 字符数:', len(buf))

try:
    import base64
    data = base64.b64decode(buf + '===')
    txt = data.decode('utf-8', 'replace')
    open(r'D:\download\NX-KS2-88\test_server\pwfilter\prefman_info_full.txt', 'w', encoding='utf-8').write(txt)
    rows = re.findall(r'^\s*(0x[0-9a-fA-F]+)\s+([0-9a-fA-Fx]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*$', txt, re.M)
    print('保存完成, 解析到字段:', len(rows))
    print('首:', rows[0] if rows else None)
    print('末:', rows[-1] if rows else None)
except Exception as e:
    print('解码失败:', e)
    print('buf 前200:', buf[:200])

s.close()
