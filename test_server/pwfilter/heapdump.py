import socket
import time
import re
import base64
import struct

HOST = '192.168.0.105'
PID = 252

s = socket.create_connection((HOST, 23), timeout=30)
s.settimeout(6.0)


def drain(t=6.0):
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


def run(c, w=6.0, pre=0.8):
    s.sendall((c + '\n').encode())
    time.sleep(pre)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


def sz_of(path):
    r = run('wc -c %s' % path, 4.0)
    n = [int(x) for x in re.findall(r'(\d+)', r)]
    return max(n) if n else 0


drain(3.0)
s.sendall(b'root\n')
drain(3.0)

# 只取 heap 段 —— iqr 数组最可能在这里
targets = []
r = run('grep "rw" /proc/%d/maps' % PID, 6.0)
for ln in r.split('\n'):
    m = re.match(r'\s*([0-9a-f]+)-([0-9a-f]+)\s+(rw..)\s+\S+\s+\S+\s+\S+\s*(.*)', ln.strip())
    if not m:
        continue
    a, b, perm, path = int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4).strip()
    sz = b - a
    if 'r' not in perm or sz < 262144 or sz > 30 * 1024 * 1024:
        continue
    targets.append((a, sz, path))

# 只扫 heap（最大的那个 rw 段）
targets.sort(key=lambda x: -x[1])
print('候选段:')
for a, sz, p in targets[:6]:
    print('  0x%08x  %9d  %s' % (a, sz, p))

if not targets:
    print('无合适段')
    s.close()
    raise SystemExit

A, SZ, P = targets[0]
print()
print('取最大段 0x%08x (%d B) ...' % (A, SZ), flush=True)

# 相机侧: dd 到 SD 卡再 base64
run('rm -f /tmp/m.b64', 2.0)
r = run('dd if=/proc/%d/mem bs=4096 skip=%d count=%d of=/tmp/mem.bin 2>/dev/null; /opt/usr/nx-ks/busybox base64 /tmp/mem.bin > /tmp/m.b64; rm -f /tmp/mem.bin'
        % (PID, A // 4096, SZ // 4096 + 1), 45.0, 2.0)
tot = sz_of('/tmp/m.b64')
print('段内容 b64 字节:', tot, flush=True)

if tot == 0:
    print('dump 失败')
    s.close()
    raise SystemExit

buf = ''
CH = 600
total = tot // CH + 1
for k in range(1, total + 1):
    s.sendall(('sed -n %d,%dp /tmp/m.b64\n' % ((k - 1) * CH + 1, k * CH)).encode())
    time.sleep(0.4)
    rr = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(2.0))
    for ln in rr.split('\n'):
        t = ln.strip()
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
            buf += t
    if k % 30 == 0 or k == total:
        print('  %d/%d  %d 字符' % (k, total, len(buf)), flush=True)

raw = base64.b64decode(buf + '===')
print('解出%d 字节' % len(raw))
open(r'D:\download\NX-KS2-88\test_server\pwfilter\heapdump.bin', 'wb').write(raw)

PAT1 = struct.pack('<I', 0x000FD80A)
PAT16 = PAT1 * 4
n1 = raw.count(PAT1)
n16 = raw.count(PAT16)
print()
print('=== 搜索结果 ===')
print('  4字节单值 (0x000FD80A) 命中: %d' % n1)
print('  16字节连续 (iqr 数组特征) 命中: %d' % n16)
if n16:
    st = 0
    while True:
        i = raw.find(PAT16, st)
        if i < 0:
            break
        print('   ★ 0x%08x' % (A + i))
        st = i + 1
        if st > i + 1 and len([1 for _ in range(0)]) > 0:
            pass
elif n1:
    st = 0
    c = 0
    while c < 12:
        i = raw.find(PAT1, st)
        if i < 0:
            break
        print('   单值 0x%08x  前后: %s' % (A + i, raw[i - 8:i + 20].hex()))
        st = i + 1
        c += 1
else:
    print('  未找到特征串 -> iqr 不是内存里的独立存储')

s.close()
