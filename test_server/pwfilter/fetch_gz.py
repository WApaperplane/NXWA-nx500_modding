import socket
import time
import re
import base64
import gzip
import sys

HOST = '192.168.0.105'
REMOTE = sys.argv[1]
LOCAL = sys.argv[2]

s = socket.create_connection((HOST, 23), timeout=40)
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


def run(c, w=6.0, pre=0.7):
    s.sendall((c + '\n').encode())
    time.sleep(pre)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


def sz_of(path):
    r = run('wc -c %s' % path, 3.0)
    nums = [int(x) for x in re.findall(r'(\d+)', r)]
    return max(nums) if nums else 0


drain(3.0)
s.sendall(b'root\n')
drain(3.0)

print('源文件:', run('ls -la ' + REMOTE, 3.0)[:130])

# 相机侧先 gzip 压缩
print('相机端 gzip 压缩中（大文件需 30-60s）...', flush=True)
run('rm -f /tmp/g.b64', 2.0)
r = run('/opt/usr/nx-ks/busybox gzip -9 -c %s | /opt/usr/nx-ks/busybox base64 > /tmp/g.b64' % REMOTE, 90.0, 3.0)
tot = sz_of('/tmp/g.b64')
print('压缩后 b64 字节:', tot, flush=True)

if tot == 0:
    print('压缩失败，尝试无压缩分块')
    run('rm -f /tmp/g.b64', 2.0)
    run('/opt/usr/nx-ks/busybox base64 %s > /tmp/g.b64' % REMOTE, 60.0, 2.0)
    tot = sz_of('/tmp/g.b64')
    print('原样 b64 字节:', tot)

buf = ''
CH = 600
total = tot // CH + 1
for k in range(1, total + 1):
    run('sed -n %d,%dp /tmp/g.b64' % ((k - 1) * CH + 1, k * CH), 2.4, 0.5)
    rr = run('true', 0.3, 0.35)   # 触发上一步输出已 drain
    # 重新取（上面 drain 已消耗），改为一次性
    pass

# 重新做：每块发送后立即读取
buf = ''
for k in range(1, total + 1):
    s.sendall(('sed -n %d,%dp /tmp/g.b64\n' % ((k - 1) * CH + 1, k * CH)).encode())
    time.sleep(0.45)
    rr = re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(2.0))
    for ln in rr.split('\n'):
        t = ln.strip()
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
            buf += t
    if k % 20 == 0 or k == total:
        print('  %d/%d  %d 字符' % (k, total, len(buf)), flush=True)

raw = base64.b64decode(buf + '===')
print('解码后 %d 字节' % len(raw))
if raw[:2] == b'\x1f\x8b':
    data = gzip.decompress(raw)
    print('gzip 解压后 %d 字节' % len(data))
else:
    data = raw
open(LOCAL, 'wb').write(data)
print('已保存 -> %s' % LOCAL)
print('ELF 头:', '正常' if data[:4] == b'\x7fELF' else '异常')
s.close()
