import socket
import time
import re

s = socket.create_connection(('192.168.0.105', 23), timeout=12)
s.settimeout(2.5)


def drain(t=2.0):
    end = time.time() + t
    out = b''
    while time.time() < end:
        try:
            c = s.recv(4096)
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
    time.sleep(0.35)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


def val(off):
    r = run('prefman get 0 0x%05x l' % off)
    m = re.search(r'value = (-?\d+)', r)
    return int(m.group(1)) if m else None


def wr(off, v):
    run('prefman set 0 0x%05x l %d' % (off, v))


R, G, B = 0x00a3c4, 0x00a3c8, 0x00a3cc

drain(2.0)
s.sendall(b'root\n')
drain(2.0)

orig = (val(R), val(G), val(B))
print('=== CWB 原始值 ===')
print('  R=0x%06x  G=0x%06x  B=0x%06x' % orig)
print('  拆解:')
for lbl, v in zip('RGB', orig):
    print('    %s: hi16=%-6d lo16=%d' % (lbl, (v >> 16) & 0xFFFF, v & 0xFFFF))
print()

print('=== 测试 1: prefman 是否裁剪 CWB ===')
for probe in [0, 1, 0x7F, 0xFF, 0x100, 0xFFFF, 0x10000, 0x1FFFF, 0x7FFFF, 0xFFFFFF, -1]:
    wr(R, probe)
    got = val(R)
    mark = '' if got == probe else '<-- 裁剪/变形'
    print('  set R=%-10s read=%-10s %s' % (probe, got, mark))
wr(R, orig[0])
print('  还原 R=%s' % val(R))
print()

print('=== 测试 2: 三通道独立范围 ===')
for lbl, off in (('R', R), ('G', G), ('B', B)):
    print('  %s:' % lbl, end=' ')
    for probe in [0, 0xFFFF, 0x10000]:
        wr(off, probe)
        print('%s->%s ' % (probe, val(off)), end='')
    wr(off, (R, G, B)[('R', 'G', 'B').index(lbl)] and 0)
print()

print('=== 还原 ===')
wr(R, orig[0]); wr(G, orig[1]); wr(B, orig[2])
run('prefman save'); run('sync')
print('  R=0x%06x G=0x%06x B=0x%06x (saved)' % (val(R), val(G), val(B)))
s.close()
