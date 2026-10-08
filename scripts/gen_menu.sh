#!/bin/bash
# 动态生成主菜单: 把当前 WiFi IP 与 Telnet 状态写进菜单标签。
# 由 menu.sh / loadgui.sh 在启动 mod_gui 前调用(纯 sed, 耗时可忽略)。
#
# 设计: gui_tpl.NX500 / gui_tpl.NX1 是模板(%%IP%% / %%TN%% 占位符),
# 生成结果覆盖 gui_ini.NX500 / gui_ini.NX1 —— mod_gui 按
# "目录参数 + gui_ini.机型" 读取, 覆盖它即可让每次开菜单都显示最新状态。
# 模板不存在时跳过生成, 保证菜单永远可用(防呆)。

MODEL=$(/bin/grep -m1 . /etc/version.info 2>/dev/null)
case "$MODEL" in
    NX1)
        TPL=/opt/usr/nx-ks/gui_tpl.NX1
        DST=/opt/usr/nx-ks/gui_ini.NX1
        ;;
    *)
        TPL=/opt/usr/nx-ks/gui_tpl.NX500
        DST=/opt/usr/nx-ks/gui_ini.NX500
        ;;
esac

[ -f "$TPL" ] || exit 0

# 当前 WiFi IP(mlan0)
IP=$(ip addr ls 2>/dev/null | grep inet | grep mlan0 | cut -d/ -f 1 \
     | grep -o '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}')
[ -z "$IP" ] && IP="WiFi未开"

# Telnet 状态
if ps -w 2>/dev/null | grep telnetd | grep -qv grep; then
    TN="Telnet开"
else
    TN="Telnet关"
fi

sed -e "s/%%IP%%/$IP/g" -e "s/%%TN%%/$TN/g" "$TPL" > "$DST.tmp" \
    && mv -f "$DST.tmp" "$DST"
exit 0
