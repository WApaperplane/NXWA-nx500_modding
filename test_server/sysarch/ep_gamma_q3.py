# -*- coding: utf-8 -*-
"""Q3 普查 v3：可靠取回（telnet 只用于触发执行，结果走 FTP 拉文件）

## ★★★ 为什么改成这样（两次踩坑换来的）
  v1：telnet 会话里堆 4 条命令        → 相机在第 3 条时重启（单核压死）
  v2：stdout 直接回读                → 只拿到 1 字符（telnet 读多行不可靠）
  v3：命令重定向到远端小文件 + FTP 拉 → 可靠，且每次只发一条命令

★ 铁律：一次只发一条命令；结果一律走 FTP 落文件再拉回，绝不靠 telnet 回显。
"""
import sys, os, time
import socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, 'epgamma.arm')
OUT = os.path.join(HERE, 'raw8')
TAG = sys.argv[1] if len(sys.argv) > 1 else 'x'
ARGS = sys.argv[2:] or ['map']
CMD = ' '.join(ARGS)
REMOTE = '%s/epg_%s.txt' % (X, TAG)

os.makedirs(OUT, exist_ok=True)


def wait_port(port, want_open=True, tries=20, gap=8):
    """★ 相机重启期间服务会时有时无 ⇒ 每次操作前先探端口。
    返回 True 表示到达期望状态。"""
    for i in range(tries):
        s = socket.socket()
        s.settimeout(5)
        try:
            s.connect((HOST, port))
            s.close()
            if want_open:
                print('port %d ready (第 %d 次探测)' % (port, i + 1))
                return True
        except Exception:
            pass
        finally:
            try:
                s.close()
            except Exception:
                pass
        time.sleep(gap)
    return False


def ftp_connect(tries=6, gap=10):
    last = None
    for i in range(tries):
        try:
            f = ftplib.FTP(HOST, timeout=60)
            f.login()
            return f
        except Exception as e:
            last = e
            print('  ftp 尝试 %d 失败: %s' % (i + 1, type(e).__name__))
            time.sleep(gap)
    raise last


# ── 1) 等相机就绪 + 上传工具
if not wait_port(21):
    print('★ FTP 21 不可达，相机不在线 —— 停止（不做任何写操作）')
    sys.exit(1)

f = ftp_connect()
f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR epgamma.arm', fh)
f.quit()
print('uploaded %d B' % os.path.getsize(ARM))

# ── 2) telnet 只发一条命令（★ 会话用完即弃）
print('\n>>> epgamma.arm %s   (输出 -> %s)' % (CMD, REMOTE))
if not wait_port(23, tries=6, gap=5):
    print('★ telnet 23 不可达，停止')
    sys.exit(1)
t = MiniTel(HOST)
t.read(3)
t.send('root', 2)
t.send('', 2)
time.sleep(1)
line = 'nice -n 19 %s/epgamma.arm %s > %s 2>&1; echo RC=$?' % (X, CMD, REMOTE)
r = t.send(line, 8)
print('exec:', ' '.join(r.split())[-40:])
time.sleep(3)
try:
    t.close()
except Exception:
    pass

# ── 3) FTP 拉结果（等文件出现，最多 60s）
print('\npulling ...')
got = None
for attempt in range(12):
    time.sleep(5)
    try:
        f = ftp_connect(tries=2, gap=5)
        f.cwd('/_xfer')
        p = os.path.join(OUT, 'epg_%s.txt' % TAG)
        with open(p, 'wb') as fh:
            f.retrbinary('RETR ' + os.path.basename(REMOTE), fh.write)
        f.quit()
        sz = os.path.getsize(p)
        if sz > 0:
            got = p
            print('PULLED %d B after %ds' % (sz, (attempt + 1) * 5))
            break
    except Exception as e:
        print('  attempt %d: %s' % (attempt + 1, type(e).__name__))

if not got:
    print('★ 未拉到结果（相机可能在执行中，或命令仍在跑）')
    sys.exit(1)

with open(got, 'r', encoding='utf-8', errors='replace') as fh:
    print('\n========== %s ==========' % os.path.basename(got))
    print(fh.read())
