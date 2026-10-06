import socket
import time
import re

HOST = '192.168.0.105'
SH = '/opt/storage/sdcard/_pwtest/filmlab-apply.sh'

# (标签, 配方)  顺序：先基线，再彩色，再黑白，最后暗角，最后还原
STEPS = [
    ('基线 / 中性', 'reset'),
    ('1/5  Portra 400 人像暖调', 'portra400'),
    ('2/5  Velvia 50 风光高饱和', 'velvia50'),
    ('3/5  TriX 400 黑白粗颗粒', 'trix400'),
    ('4/5  Vignette 暗角叠加', 'vignette'),
    ('还原 / 中性', 'reset'),
]

GAP = 20      # 用户要求每档停留 20 秒
PRE_WAIT = 3  # 执行后先等3s 让引擎与取景器稳定


def drain(t):
    end = time.time() + t
    out = b''
    while time.time() < end:
        try:
            c = s.recv(8192)
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


def clean(t):
    return re.sub(r'[\x00-\x08\x0b-\x1f\x7f-\xff]+', ' ', t)


def run(cmd, wait=1.0):
    s.sendall((cmd + '\n').encode())
    time.sleep(0.3)
    return clean(drain(wait))


s = socket.create_connection((HOST, 23), timeout=10)
s.settimeout(2.0)
drain(2.0)
s.sendall(b'root\n')
drain(2.0)

def q(idx):
    r = run('st cap capdtm getusr %d' % idx, 1.2)
    m = re.search(r'UserData is (\S+)', r)
    return m.group(1) if m else '?'


def pv(off):
    r = run('prefman get 0 0x%05x l' % off, 1.2)
    m = re.search(r'value = (-?\d+)', r)
    return m.group(1) if m else '?'


def tint_hex(v):
    try:
        return '0x%06x' % int(v)
    except ValueError:
        return v


for i, (label, rid) in enumerate(STEPS):
    print('[%d/%d] >>> %s  (apply %s)' % (i + 1, len(STEPS), label, rid), flush=True)
    run('sh %s apply %s' % (SH, rid), 20.0)
    time.sleep(PRE_WAIT)

    # 独立单条复查, 避免串口缓冲串扰
    print('      PW=%s | SmartFilter=%s' % (q(20), q(62)), flush=True)
    print('      K=%s tint=%s' % (pv(0x0a394), tint_hex(pv(0x0a3bc))), flush=True)
    print('      >>>>> 请看取景器，留意这一档的画面 <<<<<', flush=True)
    print('', flush=True)

    if i < len(STEPS) - 1:
        time.sleep(GAP)

print('全部完成，相机已还原到中性。', flush=True)
s.close()
