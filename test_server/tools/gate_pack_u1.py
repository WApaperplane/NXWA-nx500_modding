#!/usr/bin/env python3
"""U1 只读上机脚本包生成器 (gate_pack_u1.py)

生成 `test_server/u1/` 下的相机端脚本 + runbook，并把本项目的**操作纪律写成可核对的形式**
——不是写在文档里让人记得，而是写成 `@gate` 头注释，由 `gate_flow.py` 每次重新解析。

U1 = 一次只读上机（合并 5 问），见 WORKFLOW_PLAN §3。本包覆盖其中 4 问：
  ① `/dev/mem` 四点对照（含阳性/阴性对照，铁律 118）
  ② IPC 寄存器区 0x20800000-0x2081FFFF 分行扫描（U03 从未扫过的 128KB）
  ③④ 输入设备侦察 + 事件流抓取（波轮 keysym / 触摸）
  ⑤ `st cap iqr` 全量 dump + epmc 读 ISP 参数块（目标矩阵 C14）
  附：P8 定案判据（`/proc/diskstats` 的 p8 写入扇区）

设计纪律（写进脚本、由 gate 复核）
--------------------------------
* **脚本按 idx 参数一次只读一段**，绝不"一个脚本扫完 43 段"——铁律 88：
  危险的不是读了多少字节，是**单次运行的循环总量**（压死过相机 5 次）。
* **所有地址算术在 PC 侧预计算成十进制字面量**。相机端 busybox ash 的
  `$(( ))` 可能是 32 位（`0x810fd100` 会溢出），不能赌。
* **只有 dd / sleep / kill / mkdir / md5sum 这类核心 applet**，
  不依赖 `timeout` / `evtest` 等不一定存在的工具。
* **一次运行的输出量压到最小**：二进制写文件，屏幕只回一行。

用法
----
  python test_server/tools/gate_pack_u1.py            # 生成 + 自检
  python test_server/tools/gate_pack_u1.py --dry-run  # 只看会生成什么

★ 本生成器**不联网、不碰相机**。上机动作全部由 runbook 里的人工步骤驱动。
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_flow  # noqa: E402  —— 用同一个 linter 自检，避免"生成端与门控端判据漂移"

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, gate_flow.U1_DIR)

CAM = "/mnt/mmc/u1"          # 相机端脚本/日志根（SD 卡；FTP 根 == SD 卡根）
CAM_OUT = "/mnt/mmc/u1/out"  # 原始输出落点，PC 侧 FTP 拉这里
BB = "/opt/usr/nx-ks/busybox"

# 铁律 88：单次连续段 <= 768 regs(3KB)
SEG_REGS = 768

# ---- ① /dev/mem 四点对照 -------------------------------------------------
# ★ 顺序就是判据顺序（铁律 118：对照失败禁止输出主结论）：
#   先证明"这套方法在本机读得动"（阳性对照），再证明"设备寄存器区读不动"（阴性对照），
#   最后才问两个 LUT 缓冲——否则"读不到"无法解释，会被当成"里面没东西"。
DRAM_SEGS = [
    ("ctl_dram_94000000", 0x94000000, SEG_REGS, "阳性对照：Linux CMA 窗口，已知 dd 可读"),
    ("ctl_dev_2082b000", 0x2082B000, SEG_REGS, "阴性对照：设备寄存器区，预期 dd 失败"),
    ("lut_a_810fd100", 0x810FD100, SEG_REGS, "问题本体：p7 LUT 缓冲 A"),
    ("lut_b_81115200", 0x81115200, SEG_REGS, "问题本体：p7 LUT 缓冲 B（= LUT0）"),
]

# ---- ② IPC 寄存器区 ------------------------------------------------------
IPC_BASE = 0x20800000
IPC_TOTAL = 0x20000          # 128KB
IPC_SEGS = []
_n = IPC_TOTAL // (SEG_REGS * 4)
_rem = IPC_TOTAL - _n * SEG_REGS * 4
for i in range(_n):
    IPC_SEGS.append((f"ipc_{IPC_BASE + i*SEG_REGS*4:08x}", IPC_BASE + i * SEG_REGS * 4, SEG_REGS,
                     f"IPC 区第 {i+1}/{_n + (1 if _rem else 0)} 段"))
if _rem:
    IPC_SEGS.append((f"ipc_{IPC_BASE + _n*SEG_REGS*4:08x}", IPC_BASE + _n * SEG_REGS * 4,
                     _rem // 4, "IPC 区尾段"))

ALL_SEGS = DRAM_SEGS + IPC_SEGS

# ---- ⑤ epmc 只读项（严格落在铁律 88 之内）---------------------------------
# ★★★ 关键语义（epmc.c 第 103-114 行）：nz 模式里 `nreg` 是【结束下标】而不是个数——
#      for (i = from/4; i < nreg; i++)
#   所以 "从 0x1300 起扫 512 个" 必须写成 `epmc 0 1728 nz 0x1300`
#   （0x1300/4 = 1216, 1216 + 512 = 1728）。写成 `epmc 0 512 nz 0x1300` 会得到负长度、
#   一次都不扫却打印 "NZ nonzero 0/-704" —— 这属于"看着有输出其实是空的"，
#   是本项目最忌讳的假结论形态。每条都要写对。
#   元组 = (idx, nreg_end, from_hex, 有效扫描 regs, 说明)
EPMC_STEPS = [
    (8, 4, None, 4, "自证：3dlut 前 4 个，应与已知 OnOff=0x1 / Cfg=0x100 / Pulse=0x0 / LUT0=0x81115200 对上"),
    (0, 1728, "0x1300", 512, "ISP 参数块 A+B 非零面（0x20821300 / 0x20821700，落在 top 块内）"),
    (2, 768, None, 768, "mc 块前 768 regs 非零面（0x20824000）"),
]
# ★ 以下超出铁律 88（>768 regs），**故意不生成脚本**，只作为 runbook 里的 NOTE：
#    epmc 2 2048 nz 0xc00   —— mc 块其后部分；epmc 作者称 nz 模式可压住输出量，
#    但"1024/2048 regs 压死相机"是实测事实 ⇒ 必须先用 768-nz 跑通、有人看着再升级。

PLACEHOLDER = "<!--GENERATED-->\n"


def sec_regs(tbl):
    return {name: regs for name, _a, regs, _w in tbl}


def sh_body_u1_rd():
    arms = []
    for idx, (name, addr, regs, _why) in enumerate(ALL_SEGS, start=1):
        skip = addr // 4                     # ★ 十进制字面量：相机端不做算术
        arms.append(f'  {idx}) NAME={name}; SKIP={skip}; COUNT={regs} ;;')
    arm_txt = "\n".join(arms)
    hdr = []
    for name, addr, regs, why in ALL_SEGS:
        hdr.append(f"# @seg name={name} addr=0x{addr:08x} bytes={regs*4} regs={regs}  # {why}")
    hdr_txt = "\n".join(hdr)
    n = len(ALL_SEGS)
    return f"""#!/bin/sh
#=====================================================================
# u1_rd.sh -- U1 ①/②：按 idx 只读一段 /dev/mem（一次调用只读一段）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 为什么按 idx 拆：铁律 88 说危险的不是"读了多少字节"，
#   是【单次运行的循环总量】。所以扫描必须由人一段一段驱动。
# ★ 为什么 skip 是十进制字面量：busybox ash 的 $(( )) 可能是 32 位，
#   0x810fd100 会溢出 —— 地址算术一律在 PC 侧算好。
# @gate script=u1_rd.sh opens=rdonly one_shot=1
{hdr_txt}
BB={BB}
OUT={CAM_OUT}
IDX="$1"

case "$IDX" in
{arm_txt}
  *) echo "usage: sh u1_rd.sh <idx 1..{n}>"; exit 2 ;;
esac

$BB mkdir -p "$OUT"

# ---- 一次连续的只读 + 落盘，屏幕只回一行 ----
nice -n 19 $BB dd if=/dev/mem of="$OUT/$NAME.bin" bs=4 count="$COUNT" skip="$SKIP" > "$OUT/$NAME.log" 2>&1
RC=$?
echo "dd_rc=$RC" >> "$OUT/$NAME.log"

$BB md5sum "$OUT/$NAME.bin" > "$OUT/$NAME.md5" 2>/dev/null
$BB sync
SZ=$($BB wc -c < "$OUT/$NAME.bin" 2>/dev/null)
echo "idx=$IDX name=$NAME skip=$SKIP count=$COUNT bytes=$SZ dd_rc=$RC"
$BB cat "$OUT/$NAME.log"
exit $RC
# 注：dd 失败（如设备寄存器区 /dev/mem 对 MMIO 被拒）时 dd_rc != 0，且 .bin 可能为 0 字节
#     —— 这本身就是结论，必须原样记录，不许因为"读不到"就跳过（铁律 118）。
#     退出码原样传递，便于由人/脚本判"这段到底读成了没有"。
"""


def sh_body_probe():
    return f"""#!/bin/sh
#=====================================================================
# u1_probe.sh -- U1 步骤 0：环境侦察 + P8 定案判据（全只读）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 本步同时承载两件事：
#   (a) 上机负载基线（铁律 104：'进程活着' != '系统没被拖垮'，参照物必须先取）
#   (b) p8(rtos_data) 全零悬案的**写死判据**（P8_ZERO_INVESTIGATION 的 P0 项）：
#       /proc/diskstats 里 p8 累计写入扇区 == 0  =>  定案"从未被写入"
#   (c) 自证：把 st / dd 的解析路径打出来，避免"用了不存在的工具"这类假结论
# @gate script=u1_probe.sh opens=rdonly one_shot=1
BB={BB}
OUT={CAM_OUT}
LOG="$OUT/probe.log"

$BB mkdir -p "$OUT"
{{
  echo "== version.info"
  $BB cat /etc/version.info 2>/dev/null
  echo "== uname"; $BB uname -a
  echo "== uptime"; $BB uptime
  echo "== loadavg"; $BB cat /proc/loadavg
  echo "== ps lines"; $BB ps | $BB wc -l
  echo "== which (自证：确认工具真实存在)"
  $BB which st 2>/dev/null || echo "st NOT in PATH"
  $BB which dd 2>/dev/null || echo "dd NOT in PATH"
  echo "PATH=$PATH"
  echo "== EV_MOBILE.sh md5 (preflight 第 2 项：机上必须不是 55c47b89)"
  $BB md5sum /opt/usr/nx-ks/EV_MOBILE.sh 2>/dev/null
  echo "== /dev/input"
  $BB ls -l /dev/input/ 2>/dev/null
  echo "== input devices"
  $BB cat /proc/bus/input/devices 2>/dev/null
  echo "== diskstats"
  $BB cat /proc/diskstats 2>/dev/null
  echo "== p8 sysfs"
  for f in ro start size stat force_ro; do
    printf "p8 %s=" "$f"
    $BB cat "/sys/block/mmcblk0p8/$f" 2>/dev/null || echo "N/A"
  done
  echo "== parttab"
  $BB cat /etc/parttab 2>/dev/null
  echo "== df"
  $BB df -k 2>/dev/null
}} > "$LOG" 2>&1

$BB sync
echo "probe lines=$($BB wc -l < "$LOG" 2>/dev/null)"
echo "probe md5=$($BB md5sum "$LOG" 2>/dev/null)"
exit 0
"""


def sh_body_input():
    return f"""#!/bin/sh
#=====================================================================
# u1_input.sh -- U1 ③/④：抓一小段输入事件流（波轮 keysym / 触摸）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 为什么不用 timeout：不确定 busybox 是否编了 timeout applet；
#   这里只用 dd + sleep + kill（核心 applet 必定存在）做一个有界读取。
# ★ 用法前先看 u1_probe.sh 的 /proc/bus/input/devices 输出，确定哪个 eventN 是波轮/触摸。
#   运行期间请人【转动波轮 / 触摸屏幕】，否则读不到事件。
# @gate script=u1_input.sh opens=rdonly one_shot=1
BB={BB}
OUT={CAM_OUT}
N="$1"
SEC="$2"

if [ -z "$N" ]; then echo "usage: sh u1_input.sh <eventN> [secs]"; exit 2; fi
[ -z "$SEC" ] && SEC=20
if [ ! -r "/dev/input/event$N" ]; then echo "not readable: /dev/input/event$N"; exit 3; fi

$BB mkdir -p "$OUT"
BIN="$OUT/input_event$N.bin"

# 有界读取：后台 dd + 到点 kill（bs=16 = 32 位 input_event 结构体大小）
$BB dd if="/dev/input/event$N" of="$BIN" bs=16 count=256 2>"$OUT/input_event$N.log" &
DDPID=$!
$BB sleep "$SEC"
$BB kill -TERM "$DDPID" 2>/dev/null
$BB sleep 1
$BB kill -9 "$DDPID" 2>/dev/null
wait 2>/dev/null
$BB sync

SZ=$($BB wc -c < "$BIN" 2>/dev/null)
echo "event$N bytes=$SZ  (events = bytes / 16，PC 侧再除)"
echo "md5=$($BB md5sum "$BIN" 2>/dev/null)"
exit 0
"""


def sh_body_iqr():
    return f"""#!/bin/sh
#=====================================================================
# u1_iqr.sh -- U1 ⑤：st cap iqr 全量 dump（184 个 eIQ_ID_*）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ 这是固件级改动"改了生效没有"的**唯一客观判据**（铁律 86 / 门 G5）。
#   离线跑必然失败（IPCC UDD open is failed），只有机上能拿到。
# ★ 只读：st cap iqr 是查询，不下发任何参数。
# @gate script=u1_iqr.sh opens=rdonly one_shot=1
BB={BB}
OUT={CAM_OUT}

$BB mkdir -p "$OUT"
{{ echo "== st cap iqr"; st cap iqr ; echo "iqr_rc=$?" ; }} > "$OUT/iqr_dump.txt" 2>&1

$BB sync
echo "iqr lines=$($BB wc -l < "$OUT/iqr_dump.txt" 2>/dev/null)"
echo "iqr ids=$($BB grep -o 'eIQ_ID_[A-Za-z0-9_]*' "$OUT/iqr_dump.txt" 2>/dev/null | $BB sort -u | $BB wc -l)"
exit 0
"""


def sh_body_epmc():
    steps = "\n".join(
        f"#   epmc {i} {n}" + (f" nz {frm}" if frm else "") + f"   -- {why}  [有效 {eff} regs]"
        for i, n, frm, eff, why in EPMC_STEPS)
    segs = "\n".join(
        f"# @seg name=epmc{i}_{(frm or 'base')} addr=0x20820000+{frm or '0'} bytes={eff*4} regs={eff}"
        for i, _n, frm, eff, _why in EPMC_STEPS)
    return f"""#!/bin/sh
#=====================================================================
# u1_epmc.sh -- U1 ⑤：epmc 只读 EP 寄存器（ISP 参数块 / 3dlut 自证 / mc 块）
#=====================================================================
# ★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py
# ★ epmc 源码在 test_server/sysarch/epmc.c，经 /dev/drime5_ep 只读 mmap；
#   idx 0..9 对应 top/ldc/mc/rsz/lvr/bblt/fd/jpeg/3dlut/nog（与 p7_ep_windows.py 的
#   OFFICIAL 表双源互证：idx8=0x2082b000=3dlut，idx2=0x20824000=mc，idx9=nog）。
# ★ 本脚本的每一条调用有效扫描量都 <= {SEG_REGS} regs（铁律 88）。
# ★★ nz 模式里 nreg 是【结束下标】不是个数（epmc.c: for (i = from/4; i < nreg; i++)）：
#      "从 0x1300 起扫 512 个"  =>  epmc 0 1728 nz 0x1300
#    写成 epmc 0 512 nz 0x1300 会得到负长度、一次都不扫，却仍打印 "NZ nonzero 0/-704"。
# @gate script=u1_epmc.sh opens=rdonly one_shot=1
# 计划内的调用（runbook 逐步驱动）：
{steps}
{segs}
BB={BB}
OUT={CAM_OUT}
BIN={CAM}/epmc.arm

if [ ! -x "$BIN" ]; then echo "epmc.arm 缺失或不可执行: $BIN"; exit 3; fi

$BB mkdir -p "$OUT"
IDX="$1"; NREG="$2"; MODE="$3"; FROM="$4"
if [ -z "$IDX" ] || [ -z "$NREG" ]; then echo "usage: sh u1_epmc.sh <idx 0..9> <nreg> [nz [from]]"; exit 2; fi

LOG="$OUT/epmc_${{IDX}}_${{NREG}}_${{MODE:-plain}}_${{FROM:-0}}.log"
{{ nice -n 19 "$BIN" "$IDX" "$NREG" $MODE $FROM ; echo "epmc_rc=$?" ; }} > "$LOG" 2>&1
$BB sync
echo "log=$LOG"
$BB tail -n 8 "$LOG"
exit 0
# ★ 以下超出铁律 88（>768 regs），**故意不放进本脚本**：
#     epmc 2 2048 nz 0xc00
#   epmc 作者称 nz 模式把输出量压住即可，但"1024/2048 regs 压死相机"是实测事实。
#   ⇒ 必须先用 epmc 2 768 nz 跑通、且本人在机身看着，再考虑升级。见 runbook 的 NOTE。
"""


COLLECTOR = '''#!/usr/bin/env python3
"""U1 结果收集/下发（PC 侧）

★ 生成物，勿手改：python test_server/tools/gate_pack_u1.py

FTP 事实（本仓已确认）：
  * 相机 FTP 在 21 端口，root + 空密码，**FTP 根 = SD 卡**（/opt/storage/sdcard）
  * 所以 /mnt/mmc/u1/out/xxx 在 FTP 里是 /u1/out/xxx
  * **单文件 >约 60KB 会 550/553** ⇒ 大文件必须 32KB 分块 + md5sum 拼合校验

用法:
  python u1_collect.py push --host 192.168.0.105        # 把本目录脚本推到相机 /mnt/mmc/u1/
  python u1_collect.py pull --host 192.168.0.105        # 把 u1/out/ 全部拉回 raw8/gates/u1/
  python u1_collect.py ls   --host 192.168.0.105
"""
from __future__ import annotations

import argparse
import hashlib
import ftplib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
DEST = os.path.join(REPO, "raw8", "gates", "u1")
CHUNK = 32 * 1024
CAM_DIR = "/u1"          # FTP 相对路径（根 = SD 卡）
CAM_OUT = "/u1/out"
# (远端名, 本地相对路径) —— 相对 test_server/u1/
# ★ epmc.arm 是唯一需要的裸 ELF：u1_epmc.sh 直接 exec 它 ⇒ 必须 x 位，
#   而 FTP 上传不带 x 位 ⇒ 上传后必须机上 chmod（do_push 末尾会提示）。
PUSH = (
    ("u1_probe.sh", "u1_probe.sh"),
    ("u1_rd.sh", "u1_rd.sh"),
    ("u1_input.sh", "u1_input.sh"),
    ("u1_iqr.sh", "u1_iqr.sh"),
    ("u1_epmc.sh", "u1_epmc.sh"),
    ("runbook.txt", "runbook.txt"),
    ("epmc.arm", os.path.join("..", "sysarch", "epmc.arm")),
)


def conn(host):
    f = ftplib.FTP(host, timeout=60)
    f.login("root", "")
    return f


def mkdirs(f, path):
    cur = ""
    for part in [p for p in path.split("/") if p]:
        cur += "/" + part
        try:
            f.mkd(cur)
        except Exception:
            pass


def md5f(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def do_push(a):
    f = conn(a.host)
    mkdirs(f, CAM_DIR)
    for remote, rel in PUSH:
        src = os.path.normpath(os.path.join(HERE, rel))
        if not os.path.exists(src):
            print("  跳过（不存在）", remote)
            continue
        data = open(src, "rb").read()
        if remote.endswith(".sh"):
            assert b"\\r\\n" not in data, f"{remote} 含 CRLF（铁律 99）"
        with open(src, "rb") as fh:
            f.storbinary("STOR %s/%s" % (CAM_DIR, remote), fh, blocksize=CHUNK)
        print("  推送 %-16s %7d B  md5=%s" % (remote, len(data), md5f(src)))
    f.quit()
    print("★ 机上还需: chmod +x /mnt/mmc/u1/epmc.arm （FTP 不带 x 位）")


def _remote_files(f, path):
    """列远端目录 -> [(name, size)]。
    ★ 相机 busybox ftpd 不支持 MLSD（实测回 500 Unknown command），
    只支持 NLST / SIZE / LIST ⇒ 必须用 NLST + SIZE 组合，否则 pull 永远失败。"""
    out = []
    for name in f.nlst(path):
        if "/" in name:
            base = name.rsplit("/", 1)[-1]
            full = name if name.startswith("/") else "%s/%s" % (path, name)
        else:
            base = name
            full = "%s/%s" % (path, name)
        try:
            sz = int(f.size(full) or 0)
        except Exception:
            sz = 0
        out.append((base, sz))
    return out


def do_ls(a):
    f = conn(a.host)
    try:
        for name, size in _remote_files(f, CAM_OUT):
            print("  %-8s %10d  %s" % ("file", size, name))
    except Exception as e:
        print("  列目录失败（目录可能还没生成）:", e)
    f.quit()


def do_pull(a):
    os.makedirs(DEST, exist_ok=True)
    f = conn(a.host)
    try:
        files = _remote_files(f, CAM_OUT)
    except Exception as e:
        print("拉取失败：/u1/out 不存在或不可读 ->", e)
        return 1
    print("远端 %d 个文件" % len(files))
    for name, size in files:
        dst = os.path.join(DEST, name)
        # ★ >60KB 走分块（REST 续传），小文件一次拉完
        with open(dst, "wb") as fh:
            if size <= 60 * 1024:
                f.retrbinary("RETR %s/%s" % (CAM_OUT, name), fh.write, blocksize=CHUNK)
            else:
                got = 0
                while got < size:
                    def w(b):
                        fh.write(b)
                    f.retrbinary("RETR %s/%s" % (CAM_OUT, name), w, blocksize=CHUNK, rest=got)
                    got = fh.tell()
        got_size = os.path.getsize(dst)
        flag = "OK " if got_size == size else "!! "
        print("  %s%-28s %8d/%8d  md5=%s" % (flag, name, got_size, size, md5f(dst)))
    f.quit()
    print("落盘目录:", os.path.relpath(DEST, REPO))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["push", "pull", "ls"])
    ap.add_argument("--host", default="192.168.0.105")
    a = ap.parse_args()
    return {"push": do_push, "pull": do_pull, "ls": do_ls}[a.cmd](a) or 0


if __name__ == "__main__":
    sys.exit(main())
'''


def build_runbook():
    n_dram = len(DRAM_SEGS)
    n_ipc = len(IPC_SEGS)
    n_all = len(ALL_SEGS)
    p0_ipc = list(range(n_dram + 1, min(n_dram + 9, n_all + 1)))   # 前 8 段
    L = []
    A = L.append

    A("#" * 78)
    A("# U1 只读上机 runbook   （生成物：python test_server/tools/gate_pack_u1.py）")
    A("#" * 78)
    A("#")
    A("# 进门条件：G0（21 端口可连）+ G1（preflight 全绿）。先跑：")
    A("#     python test_server/tools/gate_flow.py")
    A("#")
    A("# 三条不可协商的纪律：")
    A("#   1. telnet 里【一次会话只发一条命令】；结果一律 FTP 拉，不信回显")
    A("#   2. 每条 RUN 都用 /usr/bin/setsid 脱离 telnet 会话（掉线不中断）")
    A("#   3. 段间按要求等待（铁律 88）；本 runbook 所有等待 >= 60s")
    A("#")
    A("# 每条命令里不写 $() / 变量赋值嵌套 —— 跨 Windows/WSL 传参曾把宿主机字体")
    A("# 当成相机字体（假结论）。命令一律写死绝对路径。")
    A("")

    A("=" * 78)
    A("[0] PC 侧：下发脚本（先做完这一步再开 telnet）")
    A("=" * 78)
    A("PUT: python test_server/u1/u1_collect.py push --host 192.168.0.105")
    A("     推送目标：相机 SD 卡 /mnt/mmc/u1/（FTP 根 == SD 卡根 ⇒ 相对路径 /u1/）")
    A("     ★ 清单含 epmc.arm（test_server/sysarch/epmc.arm ⇒ /u1/epmc.arm）")
    A("CHMOD: /usr/bin/setsid /opt/usr/nx-ks/busybox chmod 755 /mnt/mmc/u1/epmc.arm")
    A("     ★ FTP 上传【不保留 x 位】；不 chmod 则 u1_epmc.sh 报 '缺失或不可执行' 直接退出")
    A("")

    A("=" * 78)
    A("[1] 环境侦察 + 负载基线 + P8 定案判据（1 条命令，全只读）")
    A("=" * 78)
    A("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_probe.sh")
    A("WAIT: 60")
    A("验收：probe.log 里有 uptime/loadavg/ps 行数（后续判'拖垮'的参照物）、")
    A("      /dev/input 列表、p8 的 ro/start/size 与 /proc/diskstats")
    A("判据：diskstats 里 mmcblk0p8 的第 3 列(已读扇区)与第 7 列(已写扇区)；")
    A("      若【已写扇区 == 0】且 p8 ro=0  =>  p8 '从未被写入' 定案（P8_ZERO_INVESTIGATION）")
    A("")

    A("=" * 78)
    A(f"[2] ① /dev/mem 四点对照（{n_dram} 条命令）—— 顺序即判据，不要打乱")
    A("=" * 78)
    A("★ 铁律 118：先阳性对照证明'方法在本机读得动'，再阴性对照，最后才问问题本体。")
    for i, (name, addr, regs, why) in enumerate(DRAM_SEGS, start=1):
        A(f"# idx={i}  {name}  0x{addr:08x}  {regs} regs -- {why}")
        A(f"RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_rd.sh {i}")
        A("WAIT: 90")
    A("验收：每段 .bin 与 .log 落盘；.log 里 dd_rc=0 表示读成功")
    A("判据（写死，避免事后解释）：")
    A("  idx=1 读成功 + idx=2 读失败  =>  方法可用，'读不到'= 该地址面真的不可读")
    A("  idx=1 读失败                 =>  整套方法失效，回到离机轨（禁止输出主结论）")
    A("  idx=3/4 任一读成功           =>  G2a：走读已知内容的表做差分，U11 直接解")
    A("                                    D1 降级为交叉验证，lutmod 补丁永久弃用")
    A("  idx=3/4 都读失败             =>  G2b：才评估 lutmod，且必须重推目标地址")
    A("  ★ 把四个 .bin 的 md5 与大小抄进 raw8/gates/u1/mem_compare.json（gate_flow 读它判 G2）")
    A("")

    A("=" * 78)
    A(f"[3] ② IPC 寄存器区 0x20800000-0x2081FFFF（共 {n_ipc} 条命令；P0 子集 {len(p0_ipc)} 条）")
    A("=" * 78)
    A("★ 这 128KB 从未被扫过（U03）。预期：/dev/mem 对 MMIO 可能直接失败——")
    A("  失败也是结论（说明必须改走驱动路径，像 epmc 那样）。")
    A(f"--- P0 子集（idx {p0_ipc[0]}..{p0_ipc[-1]}，前 8 段，本次必做）---")
    for i in p0_ipc:
        A(f"RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_rd.sh {i}")
        A("WAIT: 90")
    A(f"--- P1 其余 {n_ipc - len(p0_ipc)} 段（idx {p0_ipc[-1] + 1}..{n_all}）：另开一批，不必一次做完 ---")
    A("NOTE: 模板 —— /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_rd.sh <idx>")
    A("      每段之间等 90s；一次会话只发一条；跑完立刻重新看 loadavg。")
    A("验收：每段 dd_rc 与是否全零；若可读，PC 侧统计非零寄存器分布")
    A("")

    A("=" * 78)
    A("[4] ③④ 输入设备侦察 + 事件流抓取（波轮 / 触摸）")
    A("=" * 78)
    A("★ 已实测定位（2026-10-08 U1）：event0=GPIO kbd / event1=ADC kbd（四向） / event2=触摸（MT-B）。")
    A("★ 下面三条运行期间，请人在机身上【转动波轮·按方向键 / 触摸屏幕划动】。")
    A("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_input.sh 0 20   # GPIO 键盘 125/126/163/165/177/178")
    A("WAIT: 60")
    A("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_input.sh 1 20   # ADC 键盘四向 72/75/77/80")
    A("WAIT: 60")
    A("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_input.sh 2 20   # 触摸屏 MT protocol B")
    A("WAIT: 60")
    A("验收：input_eventN.bin 非空；PC 侧用 test_server/tools/u1_input_map.py 解出 (type, code, value)")
    A("      => raw8/gates/u1/input_map.json；★ 全集无 EV_REL ⇒ 无独立相对轴设备")
    A("")

    A("=" * 78)
    A("[5] ⑤ st cap iqr 全量 dump（184 个 eIQ_ID_*）+ epmc 读 ISP 参数块")
    A("=" * 78)
    A("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_iqr.sh")
    A("WAIT: 90")
    A("验收：iqr_dump.txt 里唯一 eIQ_ID_* 数 >= 184（少于此数先怀疑被截断 —— 铁律 94）")
    for idx, nreg, frm, eff, why in EPMC_STEPS:
        mode = ("nz " + frm) if frm else ""
        A(f"# epmc idx={idx} nreg={nreg} {mode}  -- {why}  [有效 {eff} regs]")
        A(("RUN: /usr/bin/setsid /bin/sh /mnt/mmc/u1/u1_epmc.sh "
           f"{idx} {nreg} {mode}").rstrip())
        A("WAIT: 90")
    A("NOTE: epmc 2 2048 nz 0xc00 —— mc 块其后部分。★ 超出铁律 88（>768 regs），")
    A("      本次【不做】。要升级必须先满足：epmc 2 768 nz 跑通、本人看着机身、且")
    A("      上一段的 loadavg 没有异常抬升。")
    A("NOTE: 关联表 = iqr(184 ID) x epmc(两块 21x10) => raw8/gates/u1/iqr_epmc_map.tsv")
    A("      ★ 必须记录【写入瞬间的运行时槽号】（U14：槽池 8 槽 x stride 0xc8，槽号运行时分配）")
    A("")

    A("=" * 78)
    A("[6] PC 侧：回收结果")
    A("=" * 78)
    A("PULL: python test_server/u1/u1_collect.py pull --host 192.168.0.105")
    A("      -> raw8/gates/u1/   （>60KB 自动分块，逐文件 md5）")
    A("THEN: python test_server/tools/gate_flow.py     # 看 G2 / G5 是否转绿")
    A("")
    A("=" * 78)
    A("# 收工纪律：把本次 loadavg / ps 行数与 [1] 的基线对照，由人判定'没拖垮'（铁律 104）。")
    A("=" * 78)
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    files = {
        "u1_rd.sh": sh_body_u1_rd(),
        "u1_probe.sh": sh_body_probe(),
        "u1_input.sh": sh_body_input(),
        "u1_iqr.sh": sh_body_iqr(),
        "u1_epmc.sh": sh_body_epmc(),
        "u1_collect.py": COLLECTOR,
        "runbook.txt": build_runbook(),
    }

    # 生成前就把自己的纪律检查一遍（铁律 99）
    for name, txt in files.items():
        assert "\r\n" not in txt, f"{name}: 生成器自身产出了 CRLF"
        if name.endswith((".sh", ".py")):
            assert txt.startswith("#!"), f"{name}: 缺 shebang"

    print(f"生成目标：{os.path.relpath(OUT_DIR, REPO)}")
    print(f"段表：DRAM {len(DRAM_SEGS)} 段 + IPC {len(IPC_SEGS)} 段 = {len(ALL_SEGS)} 段，"
          f"每段 <= {max(r for _n, _a, r, _w in ALL_SEGS)} regs")
    if a.dry_run:
        for name in files:
            print(f"  [dry] {name:16s} {len(files[name]):6d} B")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    for name, txt in files.items():
        p = os.path.join(OUT_DIR, name)
        with open(p, "wb") as fh:          # ★ 二进制写：绕过 Windows 的 \n -> \r\n
            fh.write(txt.encode("utf-8"))
        if name.endswith((".sh", ".py")):
            try:
                os.chmod(p, 0o755)
            except OSError:
                pass
        print(f"  写入 {name:16s} {len(txt):6d} B")

    # ---- 用门控端同一个 linter 自检（防止生成端/门控端判据漂移）----
    repo = gate_flow.Repo(REPO)
    lint = gate_flow.lint_u1(repo)
    print()
    print(f"自检：脚本 {len(lint['scripts'])} 个，段 {len(lint['segs'])} 段，"
          f"最大 {lint['max_regs']} regs，只读={lint['readonly']}，"
          f"one_shot={lint['one_shot']}，setsid={lint['setsid_ok']}，LF={lint['lf_only']}")
    if lint["problems"]:
        print("FAIL:")
        for p in lint["problems"]:
            print("  -", p)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
