import socket
import time
import re
import base64
import sys

HOST = '192.168.0.105'
REMOTE = sys.argv[1]
LOCAL = sys.argv[2]

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


def run(c, w=5.0):
    s.sendall((c + '\n').encode())
    time.sleep(0.6)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


drain(2.5)
s.sendall(b'root\n')
drain(2.5)

print('远端文件:', run('ls -la ' + REMOTE)[:120])

run('/opt/usr/nx-ks/busybox base64 %s > /tmp/f.b64' % REMOTE, 12.0)
r = run('wc -c /tmp/f.b64')
print('wc 输出:', repr(r.strip()[-90:]))
# wc 输出里有回显 + 多行，取所有数字里跟 .b64 同行或紧邻的那个最大整数
nums = [int(x) for x in re.findall(r'(\d+)', r)]
sz = max(nums) if nums else 0
print('b64 字节数:', sz)
if sz == 0:
    print('解析失败')
    s.close()
    sys.exit(1)

buf = ''
CH = 600
total = sz // CH + 1
for k in range(1, total + 1):
    rr = run('sed -n %d,%dp /tmp/f.b64' % ((k - 1) * CH + 1, k * CH), 2.2)
    got = 0
    for ln in rr.split('\n'):
        t = ln.strip()
        if re.match(r'^[A-Za-z0-9+/=]{20,}$', t):
            buf += t
            got += len(t)
    if k % 10 == 0 or k == total:
        print('  %d/%d 累计 %d 字符' % (k, total, len(buf)), flush=True)

data = base64.b64decode(buf + '===')
open(LOCAL, 'wb').write(data)
print('已保存 %d 字节 -> %s' % (len(data), LOCAL))
# 校验 ELF
if data[:4] == b'\x7fELF':
    print('ELF 头正常')
else:
    print('警告: 不是有效 ELF，可能截断')
s.close()
