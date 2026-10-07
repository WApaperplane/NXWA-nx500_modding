# -*- coding: utf-8 -*-
"""N02 分步上机：nxfilmui v3

★★★ 为什么分两步（这是最重要的设计）
   step1 `probe` —— 只读：读配方 + 回读 slot9 当前值 + 读当前 enum。
                    ★★ 全程【不写 prefman】，最坏结果只是"看不到东西"，
                       不可能损坏相机状态。
   step2 `gui`   —— 才写prefman。★ 前置条件：step1 三项都过。

★★ 操作纪律（来自 12:00–12:45 五次压死相机的教训）
   ① 一个 telnet 会话只发一条命令
   ② 结果一律走 FTP 拉文件，不靠 telnet 回显
   ③ 上传前先探端口，不在线就退出
   ④ 全程不做任何寄存器写入（这个工具本来也不做）

用法:
  python nxui_step.py 1              部署+ 跑 probe（只读）
  python nxui_step.py 2              部署 + 跑 pwbak save（只读备份）
  python nxui_step.py 3              启动 GUI（★ 会占住前台，需手动退出）
  python nxui_step.py log            拉回 filmui.log
"""
import sys, os, time, socket

HERE = os.path.dirname(os.path.abspath(__file__))
# ★ minitel 在 test_server/sysarch/ 下（共用它，不要复制第二份）
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'sysarch'))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
OUT = os.path.join(HERE, 'raw9')
ARM = os.path.join(HERE, 'nxfilmui_v3.arm')
SH = os.path.join(HERE, 'pwbak.sh')

os.makedirs(OUT, exist_ok=True)


def port(p, gap=6, tries=25):
    for _ in range(tries):
        s = socket.socket()
        s.settimeout(4)
        try:
            s.connect((HOST, p))
            return True
        except Exception:
            time.sleep(gap)
        finally:
            try:
                s.close()
            except Exception:
                pass
    return False


def ftp(tries=4, gap=8):
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


def upload(name, path):
    f = ftp()
    f.cwd('/_xfer')
    with open(path, 'rb') as fh:
        f.storbinary('STOR ' + name, fh)
    f.quit()
    print('uploaded %s (%d B)' % (name, os.path.getsize(path)))


def run_one(cmdline, tag, wait=30):
    """★ 铁律：一个会话一条命令，发完就关；结果走 FTP 拉"""
    if not port(23, gap=4, tries=8):
        print('telnet 不可达，停止')
        return None
    print('\n>>> %s' % cmdline)
    t = MiniTel(HOST)
    t.read(3)
    t.send('root', 2)
    t.send('', 2)
    time.sleep(1)
    t.send('%s > %s/o_%s.txt 2>&1; echo RC=$?' % (cmdline, X, tag), wait)
    time.sleep(3)
    try:
        t.close()
    except Exception:
        pass

    print('pulling...')
    for i in range(10):
        time.sleep(4)
        try:
            f = ftp(tries=2, gap=4)
            f.cwd('/_xfer')
            p = os.path.join(OUT, 'o_%s.txt' % tag)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR o_%s.txt' % tag, fh.write)
            f.quit()
            if os.path.getsize(p) > 0:
                print('--- %s (%d B) ---' % (p, os.path.getsize(p)))
                print(open(p, encoding='utf-8', errors='replace').read())
                return p
        except Exception:
            pass
    print('★ 未拉到结果')
    return None


step = sys.argv[1] if len(sys.argv) > 1 else '1'

if not port(21):
    print('★ FTP 不可达 —— 相机不在线，停止')
    sys.exit(1)

if step in ('1', '2', '3'):
    upload('nxfilmui_v3.arm', ARM)
    upload('pwbak.sh', SH)

if step == '1':
    # ★★ 只读：probe 不进 elm_run、不写 prefman
    run_one('nice -n 19 %s/nxfilmui_v3.arm probe' % X, 'probe', wait=30)

elif step == '2':
    # ★ 只读备份 slot9
    run_one('/opt/usr/nx-ks/busybox sh %s/pwbak.sh save' % X, 'pwbak', wait=25)

elif step == '3':
    # ★★ 开 GUI —— 会占前台，需在机身上按 LEFT / XF86PowerOff 退出
    print('\n★★★ GUI 模式：★ 它会占住前台，直到你在机身上按退出键')
    print('   退出键：LEFT / XF86PowerOff / 半按快门')
    print('   ★ 要回收结果先在机身操作，然后跑 `python nxui_step.py log`\n')
    if not port(23, gap=4, tries=8):
        print('telnet 不可达，停止')
        sys.exit(1)
    t = MiniTel(HOST)
    t.read(3)
    t.send('root', 2)
    t.send('', 2)
    time.sleep(1)
    # 后台跑，日志落文件
    t.send('nice -n 19 %s/nxfilmui_v3.arm gui > %s/o_gui.txt 2>&1 &' % (X, X), 8)
    time.sleep(5)
    try:
        t.close()
    except Exception:
        pass
    print('GUI 已在后台启动。★ 现在去机身看屏幕。')
    print('操作完（转波轮 / 点配方 / 按退出）后跑 `log` 回收结果。')

elif step == 'log':
    # ★ 只读取回日志
    for tag in ('probe', 'pwbak', 'gui'):
        try:
            f = ftp()
            f.cwd('/_xfer')
            p = os.path.join(OUT, 'o_%s.txt' % tag)
            with open(p, 'wb') as fh:
                f.retrbinary('RETR o_%s.txt' % tag, fh.write)
            f.quit()
            print('\n========== o_%s.txt ==========' % tag)
            print(open(p, encoding='utf-8', errors='replace').read())
        except Exception as e:
            print('o_%s.txt: %s' % (tag, type(e).__name__))
    # ★ filmui.log 是程序自己写的运行日志，最重要
    try:
        f = ftp()
        p = os.path.join(OUT, 'filmui.log')
        with open(p, 'wb') as fh:
            f.retrbinary('RETR /mnt/mmc/filmlab/filmui.log', fh.write)
        f.quit()
        print('\n========== filmui.log (%d B) ==========' % os.path.getsize(p))
        print(open(p, encoding='utf-8', errors='replace').read())
    except Exception as e:
        print('filmui.log: %s' % type(e).__name__)

else:
    print(__doc__)
