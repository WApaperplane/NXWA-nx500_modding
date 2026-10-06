import socket
import time
import re

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


def grab(tag):
    """dump 全部 EP 寄存器并拉回"""
    run('st cap path dump ep > /tmp/e_%s.txt 2>&1' % tag, 7.0)
    run('st cap path dump > /tmp/a_%s.txt 2>&1' % tag, 7.0)
    res = {}
    for pre, fn in (('e', '/tmp/e_%s.txt' % tag), ('a', '/tmp/a_%s.txt' % tag)):
        r = run('wc -l %s' % fn)
        m = re.search(r'(\d+)\s', r)
        n = int(m.group(1)) if m else 0
        buf = ''
        CH = 700
        sz = 0
        run('/opt/usr/nx-ks/busybox base64 %s > /tmp/b.b64' % fn, 5.0)
        rb = run('wc -c /tmp/b.b64')
        mb = re.search(r'(\d+)\s', rb.split('/tmp/b.b64')[0])
        sz = int(mb.group(1)) if mb else 0
        for k in range(1, sz // CH + 2):
            rr = run('sed -n %d,%dp /tmp/b.b64' % ((k - 1) * CH + 1, k * CH), 1.6)
            for ln in rr.split('\n'):
                t = ln.strip()
                if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
                    buf += t
        import base64
        try:
            txt = base64.b64decode(buf + '===').decode('utf-8', 'replace')
        except Exception:
            txt = ''
        d = {}
        for ln in txt.split('\n'):
            m2 = re.match(r'\s*\[([0-9a-fA-F]+)\]\s+((?:[0-9A-Fa-f]{8}\s+){1,4})', ln)
            if m2:
                d[m2.group(1)] = m2.group(2).split()
        res[pre] = d
        print('  %s: %d 行, 解析 %d 个地址' % (fn, n, len(d)), flush=True)
    return res


def diff(a, b, label):
    print()
    print('=== %s ===' % label)
    total = 0
    for tag in ('e', 'a'):
        if tag not in a or tag not in b:
            continue
        name = 'EP' if tag == 'e' else 'ALL'
        keys = sorted(set(a[tag]) | set(b[tag]))
        cnt = 0
        for k in keys:
            va, vb = a[tag].get(k, []), b[tag].get(k, [])
            for i in range(min(len(va), len(vb))):
                if va[i] != vb[i]:
                    print('  %s [%s]+%02x: %s -> %s' % (name, k, i * 4, va[i], vb[i]))
                    cnt += 1
                    total += 1
        if cnt == 0:
            print('  %s: 无差异' % name)
    return total


drain(2.0)
s.sendall(b'root\n')
drain(2.0)

PB = 0x0a3ec
SAT_OFF = PB + 4 * 52 + 1 * 4      # VIVID slot1 的 SAT

def val(o):
    r = run('prefman get 0 0x%05x l' % o)
    m = re.search(r'value = (-?\d+)', r)
    return int(m.group(1)) if m else None

print('当前 VIVID SAT =', val(SAT_OFF))
print()
print('--- 抓基线 (SAT=10) ---', flush=True)
base = grab('t1')

print('--- 写 SAT=0 + save ---', flush=True)
run('prefman set 0 0x%05x l 0' % SAT_OFF)
run('prefman save')
time.sleep(1.0)
print('  读回 =', val(SAT_OFF))
print()
print('--- 抓对比 (SAT=0) ---', flush=True)
tst = grab('t2')

n = diff(base, tst, 'SAT 10 -> 0 的寄存器差异')
print()
print('总计差异:', n)
print()
print('>>>请现在看取景器: 画面有没有变化? <<<')

# 还原
run('prefman set 0 0x%05x l 10' % SAT_OFF)
run('prefman save')
print()
print('已还原 VIVID SAT = 10')
s.close()
