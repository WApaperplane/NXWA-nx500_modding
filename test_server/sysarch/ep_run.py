# -*- coding: utf-8 -*-
"""极轻量部署执行器：上传 → telnet 发一条 → FTP 拉回

★★★ 三次踩坑换来的设计（相机被压死两次）：
  v1 telnet 会话里堆 4 条命令           → 相机重启
  v2 stdout 直接回读                   → 只拿到 1 字符（telnet 读多行不可靠）
  v3 telnet 只发一条 + 重定向 + FTP 拉  → 但工具本身循环太长仍压死
  v4 ★ 换成epmc.c（极轻量）+ 本脚本    → 进程秒退

★ 本脚本的纪律：
  1. 一次只跑一条命令，绝不堆叠
  2. 执行前先探端口，相机不在线就退出（不做任何写操作）
  3. 结果一律走 FTP 拉文件，不靠 telnet 回显
  4. 全程 O_RDONLY，不碰任何寄存器写入

用法: python ep_run.py <arm文件> <tag> <参数...>
例:   python ep_run.py epmc.arm t1 8 4      读 3dlut 前 4 个（自证，最轻）
      python ep_run.py epmc.arm t2 2 64     读 mc 前 64 个（Q3 主目标）
"""
import sys, os, time, socket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw8')

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

ARMF = sys.argv[1]
TAG = sys.argv[2]
ARGS = sys.argv[3:]
ARM = os.path.join(HERE, ARMF)
REMOTE = '%s/ep_%s.txt' % (X, TAG)

os.makedirs(OUT, exist_ok=True)


def port(port_no, gap=6, tries=25):
    for i in range(tries):
        s = socket.socket()
        s.settimeout(4)
        try:
            s.connect((HOST, port_no))
            return True
        except Exception:
            time.sleep(gap)
        finally:
            try:
                s.close()
            except Exception:
                pass
    return False


def ftp(tries=4, gap=6):
    last = None
    for _ in range(tries):
        try:
            f = ftplib.FTP(HOST, timeout=45)
            f.login()
            return f
        except Exception as e:
            last = e
            time.sleep(gap)
    raise last


if not port(21):
    print('★ FTP 不可达 —— 相机不在线，停止')
    sys.exit(1)

f = ftp()
f.cwd('/_xfer')
with open(ARM, 'rb') as fh:
    f.storbinary('STOR ' + ARMF, fh)
f.quit()
print('uploaded %s (%d B)' % (ARMF, os.path.getsize(ARM)))

if not port(23, gap=4, tries=8):
    print('★ telnet 不可达，停止')
    sys.exit(1)

cmdline = '%s %s > %s 2>&1; echo RC=$?' % (ARGS[0] if ARGS else '', ' '.join(ARGS[1:]), REMOTE)
line = 'nice -n 19 %s/%s %s' % (X, ARMF, ' '.join(ARGS))
print('\n>>> %s' % line)
t = MiniTel(HOST)
t.read(3)
t.send('root', 2)
t.send('', 2)
time.sleep(1)
r = t.send('%s > %s 2>&1; echo RC=$?' % (line, REMOTE), 8)
print('exec: %s' % ' '.join(r.split())[-30:])
time.sleep(4)
try:
    t.close()
except Exception:
    pass

print('\npulling ...')
got = None
for attempt in range(10):
    time.sleep(4)
    try:
        f = ftp(tries=2, gap=4)
        f.cwd('/_xfer')
        p = os.path.join(OUT, 'ep_%s.txt' % TAG)
        with open(p, 'wb') as fh:
            f.retrbinary('RETR ' + os.path.basename(REMOTE), fh.write)
        f.quit()
        if os.path.getsize(p) > 0:
            got = p
            break
    except Exception as e:
        print('  attempt %d: %s' % (attempt + 1, type(e).__name__))

if not got:
    print('★ 未拉到结果')
    sys.exit(1)
print('PULLED %d B\n' % os.path.getsize(got))
print(open(got, encoding='utf-8', errors='replace').read())
