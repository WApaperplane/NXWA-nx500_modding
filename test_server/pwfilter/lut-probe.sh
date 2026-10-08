#!/bin/sh
# lut-probe.sh — 3D LUT 逆向探针·阶段 1（纯 telnet，输出极小，无需 FTP）
#
# 目的：定位"谁加载了 libudd5"= 真正管3D LUT 的 ISP 守护进程
# 依据：di-camera-app 4.7MB 全文扫描 0 个3dl/3DL/d5_ep 引用（只有 dfms_start/stop_ipcc）
#       → 调用者在独立守护进程里
#
# 用法（telnet 逐条执行，不要一次贴全部）：
#   sh lut-probe.sh maps      # 谁加载了 libudd5
#   sh lut-probe.sh uddusers  # 扫所有进程找 libudd5
#   sh lut-probe.sh devs# 设备节点与权限
#   sh lut-probe.sh libs      # 相机上所有色彩相关 .so
#   sh lut-probe.sh dbg       # 找 libudd5.so.debug
#   sh lut-probe.sh regbase   # 读 3D LUT 寄存器基址
#
# 铁律：telnet 必须串行；busybox 用绝对路径 /opt/usr/nx-ks/busybox；
#       本文件已由 push_sh.py 转成 LF。

BB=/opt/usr/nx-ks/busybox
XFER=/mnt/mmc/_xfer

case "$1" in

maps)
  echo "=== [1] 谁加载了 libudd5 ==="
  FOUND=0
  for p in /proc/[0-9]*; do
    if grep -q libudd5 $p/maps 2>/dev/null; then
      pid=$($BB basename $p)
      echo "LOADER pid=$pid com=$($BB cat $p/comm 2>/dev/null) exe=$($BB readlink $p/exe 2>/dev/null)"
      FOUND=1
    fi
  done
  [ $FOUND -eq 0 ] && echo "(无进程加载 libudd5)"

  echo "=== [2] 全部进程 (pid comm exe) ==="
  for p in /proc/[0-9]*; do
    pid=$($BB basename $p)
    exe=$($BB readlink $p/exe 2>/dev/null)
    [ -z "$exe" ] && exe="(kthread)"
    echo "$pid $($BB cat $p/comm 2>/dev/null) $exe"
  done
  echo "=== 完maps-all完 ==="
  ;;

mapsx)
  # 详细版：宽泛扫 + 色彩设备占用。输出长，分开跑。
  echo "=== [X1] 宽泛扫 libudd/libd5/libep ==="
  for p in /proc/[0-9]*; do
    if grep -qE 'libudd|libd5|/usr/lib/lib.*ep' $p/maps 2>/dev/null; then
      echo "pid=$($BB basename $p) com=$($BB cat $p/comm 2>/dev/null)"
      $BB grep -oE '/[^ ]*\.so[^ ]*' $p/maps 2>/dev/null | sort -u
    fi
  done
  echo "=== 完x1 ==="
  ;;

devusers)
  echo "=== [X2] 谁开着 d5_ipcc / d5_sma / drime5 ==="
  for p in /proc/[0-9]*; do
    if grep -qE 'd5_ipcc|d5_sma|drime5' $p/maps 2>/dev/null; then
      echo "pid=$($BB basename $p) com=$($BB cat $p/comm 2>/dev/null) exe=$($BB readlink $p/exe 2>/dev/null)"
    fi
  done
  echo "=== 完x2 ==="
  ;;

uddusers)
  echo "=== 相机上所有 libudd / lib*d5* / ipcc 相关 .so ==="
  for d in /usr/lib /lib /usr/apps /opt/usr; do
    [ -d $d ] || continue
    for f in $(find $d -name '*.so*' 2>/dev/null); do
      if $BB strings $f 2>/dev/null | grep -q 'd5_ep_3dl\|ep_3dlut_reg_base'; then
        echo "HAS_3DL: $f  ($($BB stat -c %s $f 2>/dev/null) bytes)"
      fi
    done
  done
  echo "--- 含 d5_ipcc 字样的（可能都不止 libudd5）---"
  for d in /usr/lib /lib; do
    for f in $(find $d -name '*.so*' 2>/dev/null); do
      if $BB strings $f 2>/dev/null | grep -q 'd5_ipcc'; then
        echo "IPCC: $f  ($($BB stat -c %s $f 2>/dev/null) bytes)"
      fi
    done
  done
  echo "=== 完 ==="
  ;;

devs)
  echo "=== ISP 设备节点 ==="
  for d in d5_ipcc d5_lock d5_sma drime5_ep; do
    ls -l /dev/$d 2>/dev/null || echo "  /dev/$d 不存在"
  done
  echo "=== 完 ==="
  ;;

dbg)
  echo "=== 找 libudd5 调试符号文件 ==="
  for d in /usr/lib /lib /opt/usr /mnt/mmc; do
    find $d -name 'libudd5*' 2>/dev/null
  done
  echo "--- 带 debug 后缀的 ---"
  find / -name '*.so.debug' 2>/dev/null | head -20
  echo "=== 完 ==="
  ;;

regbase)
  # ep_3dlut_reg_base 是 libudd5 里的一个全局符号（文件偏移 0x57730，.data 段）
  # 运行时值 = *(基址+0x57730 - 库加载基址)  → 需先从 maps 拿加载基址
  echo "=== 3D LUT 寄存器基址（需先跑 maps 拿 libudd5 加载基址） ==="
  LIB=$($BB cat /proc/self/maps 2>/dev/null | grep libudd5 | head -1 | cut -d' ' -f1 | cut -d- -f1)
  echo "libudd5 首个映射段起始(十六进制) = $LIB"
  if [ -z "$LIB" ]; then
    echo "本进程未加载 libudd5。用 maps 子命令找 PID，然后："
    echo "  ls -l /proc/<PID>/exe   # 借用那个进程的视角"
    echo "  或直接 grep /proc/<PID>/maps | grep libudd5"
  else
    echo "--- 该进程视角下 /proc/self/maps 里的 libudd5 段 ---"
    grep libudd5 /proc/self/maps
  fi
  echo
  echo "=== 替代方案：直接看 /dev/mem 能不能读 ==="
  $BB dd if=/dev/mem bs=1 count=4 2>&1 | $BB od -A x -t x4 | head -2
  echo "（能读出非零 = /dev/mem 可用，我们就能自己mmap 寄存器）"
  echo "=== 完 ==="
  ;;

collect)
  echo "=== 阶段 2：把要拉的搬到 FTP 可达目录 ==="
  mkdir -p $XFER
  O=$XFER/odd3l
  mkdir -p $O

  # 2.1 libudd5 本体 + 调试符号
  for f in /usr/lib/libudd5.so /lib/libudd5.so /usr/lib/libudd5.so.debug; do
    if [ -f $f ]; then cp $f $O/ 2>/dev/null && echo "cp OK $f"
    else echo "MISS $f"; fi
  done

  # 2.2 ★ 谁加载了 libudd5 → 把那个可执行文件 + 它的 lib 全部搬过来
  echo "--- 定位加载者 ---"
  for p in /proc/[0-9]*; do
    if grep -q libudd5 $p/maps 2>/dev/null; then
      pid=$($BB basename $p)
      exe=$($BB readlink $p/exe 2>/dev/null)
      com=$($BB cat $p/comm 2>/dev/null)
      echo "LOADER pid=$pid comm=$com exe=$exe"
      echo "LOADER_EXE=$exe" >> $O/loaders.txt
      # 它加载的所有 .so（去重）
      grep -o '/[^ ]*\.so[^ ]*' $p/maps 2>/dev/null | sort -u > $O/so_$pid.txt
      wc -l < $O/so_$pid.txt
      # 逐个搬（限大小，只搬 <2MB 的，优先带 3dl 符号的）
      while read so; do
        [ -f "$so" ] || continue
        sz=$($BB stat -c %s "$so" 2>/dev/null || echo 0)
        [ "$sz" -lt 2097152 ] || continue
        cp "$so" $O/ 2>/dev/null && echo "  so cp $so ($sz)"
      done < $O/so_$pid.txt
    fi
  done
  [ -f $O/loaders.txt ] || echo "NO LOADER FOUND (库没被加载? 试 shooting 模式再跑)"

  # 2.3 全盘找 LUT 文件（出厂自带则格式白给）
  find / \( -name '*.cube' -o -name '*.lut' -o -name '*3dl*' -o -name '*3DL*' -o -name '*.1db' \) \
       > $O/find_lut.txt 2>/dev/null
  echo "find_lut.txt 行数: $($BB wc -l < $O/find_lut.txt)"
  cat $O/find_lut.txt

  # 2.4 色彩相关 .so 全清单（含大小）
  for d in /usr/lib /lib /opt/usr/lib; do
    [ -d $d ] || continue
    for f in $(find $d -name '*.so*' 2>/dev/null); do
      echo "$($BB stat -c %s $f 2>/dev/null) $f"
    done
  done > $O/all_so.txt 2>/dev/null
  echo "all_so.txt 行数: $($BB wc -l < $O/all_so.txt)"

  # 2.5 谁用了 3D LUT（按字符串）
  for d in /usr/lib /lib; do
    for f in $(find $d -name '*.so*' -size -2M 2>/dev/null); do
      if $BB strings $f 2>/dev/null | grep -q 'd5_ep_3dl\|ep_3dlut_reg'; then
        echo "HAS_3DL $f ($($BB stat -c %s $f 2>/dev/null))"
        cp $f $O/ 2>/dev/null
      fi
    done
  done > $O/has_3dl.txt 2>/dev/null
  cat $O/has_3dl.txt

  # 2.6 当前 maps 全量（谁加载了什么）
  cat /proc/self/maps > $O/maps_self.txt 2>/dev/null

  # 2.7 设备节点
  ls -l /dev/d5_ipcc /dev/d5_lock /dev/d5_sma /dev/drime5_ep /dev/mem > $O/devs.txt 2>&1

  echo "=== 完。共$($BB ls $O | $BB wc -l) 个文件在 $O ==="
  echo "=== PC 侧拉取: python ftp_get.py --batch test_server/pwfilter/odd3l /mnt/mmc/_xfer/odd3l ==="
  ;;

*)
  echo "用法: sh lut-probe.sh {maps|mapsx|devusers|uddusers|devs|dbg|regbase|collect}"
  echo "  maps    # [1]谁加载libudd5 [2]全部进程列表     ← 先跑这个"
  echo "  mapsx   # 宽泛扫 libudd/libd5/libep + 其全部 .so"
  echo "  devusers# 谁开着 d5_ipcc/d5_sma/drime5"
  echo "  collect # 搬运全部可疑文件到 FTP 可达目录    ← 跑完 maps 后再跑"
  ;;
esac
