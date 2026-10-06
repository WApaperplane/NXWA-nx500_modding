import socket
import time
import re
import struct

HOST = '192.168.0.105'
PID = 252

s = socket.create_connection((HOST, 23), timeout=25)
s.settimeout(5.0)


def drain(t=5.0):
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


def run(c, w=5.0, pre=0.6):
    s.sendall((c + '\n').encode())
    time.sleep(pre)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


drain(3.0)
s.sendall(b'root\n')
drain(3.0)

# 拿可读段列表
r = run('cat /proc/%d/maps' % PID, 6.0)
segs = []
for ln in r.split('\n'):
    m = re.match(r'\s*([0-9a-f]+)-([0-9a-f]+)\s+(rw..)\s+\S+\s+\S+\s+\S+\s*(.*)', ln.strip())
    if m:
        a, b, perm, path = int(m.group(1), 16), int(m.group(2), 16), m.group(3), m.group(4)
        sz = b - a
        if 'r' in perm and sz < 40 * 1024 * 1024 and sz > 4096:
            segs.append((a, b, sz, path))
    if len(segs) > 200:
        break

print('可读段候选: %d' % len(segs))
big = sorted([s for s in segs if s[2] > 65536], key=lambda x: -x[2])[:12]
print('较大段 (候选):')
for a, b, sz, p in big:
    print('  0x%08x-0x%08x  %8d  %s' % (a, b, sz, p))

# 特征: iqr PW_HUE..CONTRAST 四个连续 0x000FD80A
PAT = struct.pack('<I', 0x000FD80A) * 4
PAT1 = struct.pack('<I', 0x000FD80A)
print()
print('特征串 (16B) =', PAT.hex())
print('单值 (4B)   =', PAT1.hex())

found = {}
for a, b, sz, p in big:
    # 相机侧 dd | base64,分块
    CH = 2048
    step = CH * 3 // 4# base64 每 3 字节->4 字符
    run('/opt/usr/nx-ks/busybox base64 -d > /dev/null 2>&1', 1.0)
    import base64 as B
    got = b''
    off = 0
    while off < sz:
        cnt = min(3000, sz - off)
        cmd = 'dd if=/proc/%d/mem bs=1 skip=%d count=%d 2>/dev/null | /opt/usr/nx-ks/busybox base64' % (PID, a + off, cnt)
        rr = run(cmd, 3.0, 0.35)
        lines = [t for t in rr.split('\n') if re.match(r'^[A-Za-z0-9+/=]{40,}$', t.strip())]
        if lines:
            try:
                got += B.b64decode(''.join(t.strip() for t in lines) + '===')
            except Exception:
                pass
        off += cnt
        if len(got) >= sz:
            break
    n4 = 0
    idx4 = []
    st = 0
    while True:
        i = got.find(PAT1, st)
        if i < 0:
            break
        n4 += 1
        if len(idx4) < 6:
            idx4.append(a + i)
        st = i + 1
        if n4 > 60:
            break
    n16 = 0
    st = 0
    idx16 = []
    while True:
        i = got.find(PAT, st)
        if i < 0:
            break
        n16 += 1
        idx16.append(a + i)
        st = i + 1
    print()
    print('段 0x%08x (%d B, %s): 单值命中 %d, 16B连续命中 %d' % (a, len(got), p, n4, n16))
    if idx4:
        print('   前几个单值地址: %s' % ', '.join('0x%08x' % x for x in idx4))
    if idx16:
        print('   ★16B 连续命中(可能是 iqr 数组): %s' % ', '.join('0x%08x' % x for x in idx16))

s.close()
