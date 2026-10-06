# -*- coding: utf-8 -*-
"""抓完整 oops 栈（把 telnet 原始输出落盘），用于精确定位崩溃源码行
用法: python ep_oops.py <arm_binary_name> [args...]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from minitel import MiniTel
import ftplib

HOST = '192.168.0.105'
X = '/mnt/mmc/_xfer'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw7')
BIN = sys.argv[1]
ARGS = ' '.join(sys.argv[2:])

os.makedirs(OUT, exist_ok=True)

t = MiniTel(HOST); t.read(3); t.send('root', 2); t.send('', 2)
t.send('{0} chmod 755 {0}/{1}'.format(X, BIN), 3)
r = t.send('{0}/{1} {2} 2>&1; echo RC=$?'.format(X, BIN, ARGS), 40)
time.sleep(2)
# 抓 dmesg 尾部（oops 通常在这里）
d = t.send('dmesg | tail -40', 12)
time.sleep(1)
t.close()

raw = (r or '') + '\n===== dmesg tail =====\n' + (d or '')
p = os.path.join(OUT, 'oops_%s.txt' % BIN)
open(p, 'w', encoding='utf-8', errors='replace').write(raw)
print('=== RAW (%d chars) ===' % len(raw))
print(' '.join(raw.split()))
print('\nsaved ->', p)
