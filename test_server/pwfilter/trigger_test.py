import socket
import time
import re

s = socket.create_connection(('192.168.0.105', 23), timeout=15)
s.settimeout(3.0)


def drain(t=3.0):
    end = time.time() + t
    out = b''
    while time.time() < end:
        try:
            c = s.recv(16384)
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


def run(c, w=3.0):
    s.sendall((c + '\n').encode())
    time.sleep(0.4)
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', drain(w))


def val(o):
    r = run('prefman get 0 0x%05x l' % o)
    m = re.search(r'value = (-?\d+)', r)
    return int(m.group(1)) if m else None


PB = 0x0a3ec
CWB_R = 0x00a3c4

drain(2.0)
s.sendall(b'root\n')
drain(2.0)

# 记录基线
print('=== 基线===')
print('  slot9 SAT =', val(PB + 4 * 52 + 9 * 4))
print('  CWB_R     = 0x%06x' % val(CWB_R))
print()

# 写入明显不同的值（不重启）
print('=== 写入 slot9 SAT=0 + CWB_R=0x00FF00 (不重启) ===')
run('prefman set 0 0x%05x l 0' % (PB + 4 * 52 + 9 * 4))
run('prefman set 0 0x%05x l 0x00FF00' % CWB_R)
run('prefman save')
time.sleep(1.0)
print('  写入后 slot9 SAT =', val(PB + 4 * 52 + 9 * 4))
print('  写入后 CWB_R     = 0x%06x' % val(CWB_R))
print()

# 切到 CUSTOM_1 (prefman 索引 9)
print('=== 切 PW=CUSTOM_1 (引擎切槽) ===')
run('st cap capdtm setusr 20 0x140009')
time.sleep(1.0)
r = run('st cap capdtm getusr 20')
m = re.search(r'UserData is (\S+)', r)
print('  PW =', m.group(1) if m else '?')

# 读 iqr 看引擎运行时值有没有跟着变
print()
print('=== iqr 引擎运行时值 (PW_SATURATION=idx85) ===')
for _ in range(2):
    r = run('st cap iqr')
    m = re.search(r'\[\s*85\]\|[^|]*\|\s*[^|]*\|\s*(-?\d+)\|', r)
    print('  iqr[85] PW_SATURATION =', m.group(1) if m else '?')
    break

print()
print('=== >>> 请现在看取景器: 画面有没有变化? <<<')
print('=== >>> 如果没变，尝试在相机 UI 上动一下 ===')
print('=== >>>   切一次白平衡模式(AWB<->自定义)或进入菜单再退出 ===')
s.close()
