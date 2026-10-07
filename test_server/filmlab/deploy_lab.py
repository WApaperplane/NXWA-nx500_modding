# -*- coding: utf-8 -*-
"""部署 FilmLab 配方库到 SD 卡 + 重跑 probe
   ★★ 起因：step1 probe 报 load_recipes -> -1，
      真因不是"SD卡没插"（我判断错了，/mnt/mmc -> /opt/storage/sdcard 一直在线），
      而是【配方库从未部署到 SD 卡】—— /mnt/mmc/filmlab/ 目录根本不存在。

用法:
  python deploy_lab.py lib     推送配方库（写 /mnt/mmc/filmlab/recipes.txt）
  python deploy_lab.py probe   重跑 probe（只读）
"""
import sys, os, time, socket, ftplib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'sysarch'))
from minitel import MiniTel

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
SRC = os.path.join(os.path.dirname(HERE), 'filmsim', 'recipes', 'nx500_recipes.txt')


def port(p, gap=6, tries=25):
    for _ in range(tries):
        s = socket.socket()
        s.settimeout(4)
        try:
            s.connect((HOST, p)); return True
        except Exception:
            time.sleep(gap)
        finally:
            try: s.close()
            except Exception: pass
    return False


def ftp(tries=4, gap=8):
    last = None
    for _ in range(tries):
        try:
            f = ftplib.FTP(HOST, timeout=45); f.login(); return f
        except Exception as e:
            last = e; time.sleep(gap)
    raise last


step = sys.argv[1] if len(sys.argv) > 1 else 'lib'

if not port(21):
    print('★ FTP 不可达，停止'); sys.exit(1)

if step == 'lib':
    # 先看 PC 侧源文件
    n = sum(1 for L in open(SRC, encoding='utf-8')
            if L.strip() and not L.startswith('#'))
    print('PC 源: %s  (%d 条配方)' % (os.path.basename(SRC), n))

    f = ftp(); f.cwd('/_xfer')
    with open(SRC, 'rb') as fh:
        f.storbinary('STOR recipes.txt', fh)
    f.quit()
    print('uploaded recipes.txt')

    # ★ 用 busybox 绝对路径建目录 + 移动（记忆铁律）
    if not port(23, gap=4, tries=8):
        print('★ telnet 不可达，停止'); sys.exit(1)
    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
    time.sleep(1)
    BB = '/opt/usr/nx-ks/busybox'
    t.send('%s mkdir -p /mnt/mmc/filmlab && %s cp %s/recipes.txt /mnt/mmc/filmlab/recipes.txt && %s ls -la /mnt/mmc/filmlab/' % (BB, BB, X, BB), 15)
    time.sleep(4)
    try: t.close()
    except Exception: pass

    print('\nverifying ...')
    time.sleep(2)
    f = ftp(); f.cwd('/_xfer')
    p = os.path.join(HERE, 'raw9', 'verify_lib.txt')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    t2 = MiniTel(HOST); t2.read(3); t2.send('root', 2); t2.send('', 2)
    time.sleep(1)
    t2.send('%s wc -l /mnt/mmc/filmlab/recipes.txt; %s cat /mnt/mmc/filmlab/recipes.txt' % (BB, BB), 15)
    time.sleep(3)
    txt = t2.send('%s cat /mnt/mmc/filmlab/recipes.txt' % BB, 15)
    try: t2.close()
    except Exception: pass
    print('\n--- remote recipes.txt ---')
    print(txt.strip()[-1200:])

elif step == 'probe':
    if not port(23, gap=4, tries=8):
        print('★ telnet 不可达，停止'); sys.exit(1)
    t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
    time.sleep(1)
    t.send('nice -n 19 %s/nxfilmui_v3.arm probe > %s/o_probe2.txt 2>&1' % (X, X), 30)
    time.sleep(4)
    try: t.close()
    except Exception: pass
    print('pulling ...')
    for i in range(10):
        time.sleep(4)
        try:
            f = ftp(); f.cwd('/_xfer')
            p = os.path.join(HERE, 'raw9', 'o_probe2.txt')
            with open(p, 'wb') as fh: f.retrbinary('RETR o_probe2.txt', fh.write)
            f.quit()
            if os.path.getsize(p) > 0:
                print('--- %d B ---' % os.path.getsize(p))
                print(open(p, encoding='utf-8', errors='replace').read())
                break
        except Exception: pass

else:
    print(__doc__)
