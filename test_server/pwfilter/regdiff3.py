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


def grab(fn):
    """dump ep 寄存器, base64 拉回, 解析成 {addr: [words]}"""
    run('st cap path dump ep > %s 2>&1' % fn, 7.0)
    b = fn + '.b64'
    run('/opt/usr/nx-ks/busybox base64 %s > %s' % (fn, b), 5.0)
    r = run('wc -c %s' % b)
    head = r.split(b)[0]
    m = re.search(r'(\d+)', head)
    sz = int(m.group(1)) if m else 0
    buf = ''
    for k in range(1, sz // 700 + 2):
        rr = run('sed -n %d,%dp %s' % ((k - 1) * 700 + 1, k * 700, b), 1.6)
        for ln in rr.split('\n'):
            t = ln.strip()
            if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
                buf += t
    txt = base64.b64decode(buf + '===').decode('utf-8', 'replace')
    d = {}
    #格式: \x00[20821000] 00000000 00000000 ... (每行 4 个 8 位 hex)
    for m2 in re.finditer(r'\[([0-9a-fA-F]{6,10})\]\s+((?:[0-9A-Fa-f]{8}\s+){1,6})', txt):
        d[m2.group(1)] = m2.group(2).split()
    return d


def diff(a, b, label):
    print('=== %s ===' % label)
    n = 0
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k, []), b.get(k, [])
        for i in range(min(len(va), len(vb))):
            if va[i] != vb[i]:
                print('  [%s]+%02x: %s -> %s' % (k, i * 4, va[i], vb[i]))
                n += 1
    if n == 0:
        print('  无差异')
    return n


def val(o):
    r = run('prefman get 0 0x%05x l' % o)
    m = re.search(r'value = (-?\d+)', r)
    return int(m.group(1)) if m else None


PB = 0x0a3ec
V_SAT = PB + 4 * 52 + 1 * 4      # VIVID slot1 SAT
V_CON = PB + 6 * 52 + 1 * 4      # VIVID slot1 CONTRAST
CWB_R = 0x00a3c4

drain(2.0)
s.sendall(b'root\n')
drain(2.0)

def valq(o):
    r = run('prefman get 0 0x%05x l' % o)
    m = re.search(r'value = (-?\d+)', r)
    return int(m.group(1)) if m else None

print('VIVID SAT=%s CONTRAST=%s  CWB_R=0x%06x' % (valq(V_SAT), valq(V_CON), valq(CWB_R)))
print()

print('--- 抓基线 ---', flush=True)
a = grab('/tmp/g1.txt')
print('  解析 %d 个地址' % len(a))

# 一次改多个参数, 最大化差分命中率
print('--- 写入 VIVID SAT=0 CONTRAST=1 CWB_R=0x00FF00 ---', flush=True)
run('prefman set 0 0x%05x l 0' % V_SAT)
run('prefman set 0 0x%05x l 1' % V_CON)
run('prefman set 0 0x%05x l 0x00FF00' % CWB_R)
run('prefman save')
time.sleep(1.0)
print('  读回 SAT=%s CON=%s CWB_R=0x%06x' % (valq(V_SAT), valq(V_CON), valq(CWB_R)))

print()
print('--- 抓对比 ---', flush=True)
b = grab('/tmp/g2.txt')
print('  解析 %d 个地址' % len(b))

n = diff(a, b, '寄存器差异 (SAT/CONTRAST/CWB 同时改)')
print()
print('总计差异:', n)
print()
print('>>> 请看取景器: 画面变化了吗? <<<')

# 还原
run('prefman set 0 0x%05x l 10' % V_SAT)
run('prefman set 0 0x%05x l 10' % V_CON)
run('prefman set 0 0x%05x l 115712' % CWB_R)
run('prefman save')
print('已还原')
s.close()
