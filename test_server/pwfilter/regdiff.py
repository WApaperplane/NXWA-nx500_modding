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


def dump(tag):
    run('st cap path dump > /tmp/r_%s.txt 2>&1' % tag, 6.0)
    buf = ''
    for k in range(4):
        buf += run('sed -n %d,%dp /tmp/r_%s.txt' % (k * 20 + 1, (k + 1) * 20, tag), 1.6)
    lines = {}
    for l in buf.split('\n'):
        m = re.match(r'\s*\[(2[0-9a-f]{7})\]\s+((?:[0-9A-Fa-f]{8}\s+){4})', l)
        if m:
            lines[m.group(1)] = m.group(2).split()
    return lines


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

print('=== 基线: PW=STANDARD ===', flush=True)
run('st cap capdtm setusr 20 0x140000', 1.5)
time.sleep(1.5)
a = dump('std')
print('  寄存器行数 = %d' % len(a), flush=True)

print('=== 切到 VIVID (SAT=0 CONTRAST=1 R=20) ===', flush=True)
run('st cap capdtm setusr 20 0x140001', 1.5)
time.sleep(1.5)
b = dump('viv')
print('  寄存器行数 = %d' % len(b), flush=True)

print('=== 切到 PORTRAIT ===', flush=True)
run('st cap capdtm setusr 20 0x140002', 1.5)
time.sleep(1.5)
c = dump('por')

# 三态差分：只有三个风格都不同的位，才可能承载 PW 参数
print()
print('=== 三风格差分 (STANDARD / VIVID / PORTRAIT 互不相同的寄存器) ===')
allkeys = sorted(set(a) | set(b) | set(c))
found = 0
for k in allkeys:
    va, vb, vc = a.get(k, []), b.get(k, []), c.get(k, [])
    if not (va and vb and vc):
        continue
    for i in range(min(len(va), len(vb), len(vc))):
        if va[i] != vb[i] or vb[i] != vc[i]:
            print('  [%s] +%02x:STD=%s VIV=%s POR=%s' % (k, i * 4, va[i], vb[i], vc[i]))
            found += 1
if found == 0:
    print('  无三态互异位 → PW 参数不在这组寄存器里')

print()
print('=== 两态差分 (STANDARD vs VIVID, 包含只两态不同的) ===')
n2 = 0
for k in allkeys:
    va, vb = a.get(k, []), b.get(k, [])
    if not (va and vb):
        continue
    for i in range(min(len(va), len(vb))):
        if va[i] != vb[i]:
            print('  [%s] +%02x:STD=%s VIV=%s' % (k, i * 4, va[i], vb[i]))
            n2 += 1
print('  共 %d 处两态差异' % n2)

s.close()
