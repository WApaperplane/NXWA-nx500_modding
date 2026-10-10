#!/bin/bash
# 打开 NX-KS 主菜单（mod_gui 加载 gui_ini.机型）
#
# ★ 2026-10-10 提速版：
#   旧版用 2~4 个 `grep` 子进程分别去 /etc/version.info 里找型号与版本
#   （`$(/bin/grep ^NX500$ ...)` / `$(/bin/grep ^1.12$ ...)` …）⇒ 每次开菜单 2~4 次 fork。
#   现改为【读一次文件 + bash 内部分行】，0 个 grep 子进程。
#   其余行为与社区原版逐字保持一致（prefman 偏移、DIALMODE 映射、gen_menu、mod_gui）。
BB=/opt/usr/nx-ks/busybox

# ---- 型号/版本：只读一次（原：最多 4 个 grep 子进程）----
VI=$($BB head -2 /etc/version.info 2>/dev/null)
VI=${VI//$'\r'/}
MODEL=${VI%%$'\n'*}
VER=${VI#*$'\n'}

ADDR=""
case "$MODEL:$VER" in
    NX500:1.12) to=$(prefman get 0 0x0000a690 b); ADDR=0x0000a690 ;;
    NX1:1.41)   to=$(prefman get 0 0x00000658 b); ADDR=0x00000658 ;;
    *)          to=1 ;;      # 未知机型：不动 prefman，菜单照常可用
esac
to=( $to )
to=${to[5]}
if [ -n "$ADDR" ] && [ "$to" = "0" ]; then
    prefman set 0 $ADDR b 1
fi
#
if [ "$to" = "0" ]; then
	dm=$(st cap capdtm getusr DIALMODE);  dm=( $dm )
	dm=${dm[2]}
	case "$dm" in
	"DIALMODE_SMARTAUTO") st app mode auto 
	    ;;
	"DIALMODE_APERTURE") st app mode a
	    ;;
	"DIALMODE_SHUTTERSPEED") st app mode s 
	  ;;
	"DIALMODE_MANUAL") st app mode m  
	   ;;
	"DIALMODE_SMARTPRO") st app mode smart-pro
	   ;;
	*) 
	st app mode p
	;;
	esac 
fi
#
# 动态生成主菜单(IP/Telnet 状态写入标签), 失败不影响菜单启动
/opt/usr/nx-ks/gen_menu.sh 2>/dev/null
nice -n +15 /opt/usr/nx-ks/mod_gui /opt/usr/nx-ks/gui_ini & nice -n +19 /opt/usr/nx-ks/br_menu.sh &
