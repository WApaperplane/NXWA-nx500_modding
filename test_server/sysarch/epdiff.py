# -*- coding: utf-8 -*-
"""EP dump 差分器 —— 逐块逐 word 比对，报告哪些寄存器真的随输入变化

★★ 判据（记忆铁律 10/11）：判据不成立必须返回非零退出码。
   本脚本的判据 = 「至少有一个 word 变了，且变化可逆（A→B→A 复原）」。
   只输出 diff 不下判定 = 又一次假证据。
"""
import sys, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw7')

LINE = re.compile(r'^\s*(\w+)\+([0-9a-f]{4}):((?:\s+0x[0-9a-f]{8})+)')
BLKH = re.compile(r'^BLOCK (\w+) base=0x([0-9a-f]{8}) size=0x([0-9a-f]{4})'
                  r' shown=([0-9a-f]{4})/([0-9a-f]{4})')


def parse(path):
    """-> {block: {offset: value}}"""
    blocks, cur = {}, None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for ln in fh:
            if ln.startswith('BLOCK '):
                m = BLKH.match(ln)
                if m:
                    cur = m.group(1)
                    blocks[cur] = {}
                continue
            m = LINE.match(ln)
            if m and cur:
                off = int(m.group(2), 16)
                vals = re.findall(r'0x([0-9a-f]{8})', m.group(3))
                for k, v in enumerate(vals):
                    blocks[cur][off + k * 4] = int(v, 16)
    return blocks


def diff(a, b, la, lb):
    out = {}
    for blk in a:
        if blk not in b:
            out[blk] = []
            continue
        ch = [(o, a[blk][o], b[blk].get(o))
              for o in sorted(a[blk]) if a[blk][o] != b[blk].get(o)]
        if ch:
            out[blk] = ch
    return out


def main():
    if len(sys.argv) < 4:
        print('usage: epdiff.py <A.txt> <B.txt> <C.txt>   (C = 复原态)')
        print('  判据：diff(A,B) 非空 且 diff(A,C) 为空  => 变化真实且可逆')
        return 1
    pa, pb, pc = (os.path.join(OUT, sys.argv[i]) for i in (1, 2, 3))
    for p in (pa, pb, pc):
        if not os.path.exists(p):
            print('MISSING', p); return 1

    A, B, C = parse(pa), parse(pb), parse(pc)
    dAB = diff(A, B, sys.argv[1], sys.argv[2])
    dAC = diff(A, C, sys.argv[1], sys.argv[3])

    print('=' * 72)
    print('A = %s' % sys.argv[1])
    print('B = %s' % sys.argv[2])
    print('C = %s   (期望 == A)' % sys.argv[3])
    print('=' * 72)

    if not dAB:
        print('\n【结论】A 与 B 无差异 ⇒ 这次对照没有产生任何可观测变化。')
        print('         不能据此说「输入无效」，只能说「本次实验无效」。')
        return 2

    total = sum(len(v) for v in dAB.values())
    print('\n【A vs B】共 %d 个 word 变化，分布在 %d 个块：\n'
          % (total, len(dAB)))
    for blk in sorted(dAB):
        ch = dAB[blk]
        print('--- %-6s  %d 处---' % (blk, len(ch)))
        for o, va, vb in ch[:40]:
            print('   +0x%04x  0x%08x -> 0x%08x   xor=0x%08x'
                  % (o, va, vb, va ^ vb))
        if len(ch) > 40:
            print('   ... 另有 %d 处' % (len(ch) - 40))
        print()

    print('-' * 72)
    if dAC:
        print('【判定】✗ 不可逆：A 与 C 仍有 %d 处差异（C 没回到 A）。'
              % sum(len(v) for v in dAC.values()))
        print('        ⇒ 存在时间相关或状态相关的漂移，不能把上面的差异归因于输入。')
        return 3
    print('【判定】✓ 通过：A→B 有变化，且 B→C(复原) 完全回到 A。')
    print('        ⇒ 差异可归因于输入变量，且无状态漂移污染。')
    return 0


if __name__ == '__main__':
    sys.exit(main())