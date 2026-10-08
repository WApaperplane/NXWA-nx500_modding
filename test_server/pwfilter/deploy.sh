#!/bin/sh
BB=/opt/usr/nx-ks/busybox
S=/mnt/mmc/_pwtest
D=/opt/usr/nx-ks

echo "=== 备份原文件 ==="
for f in gui_exit.sh; do
  if [ -f $D/$f ] && [ ! -f $D/$f.orig ]; then
    $BB cp $D/$f $D/$f.orig && echo "  备份 $f -> $f.orig"
  else
    echo "  $f 无需备份（不存在或已备份）"
  fi
done
if [ -f $D/gui_ini.NX500 ] && [ ! -f $D/gui_ini.NX500.orig ]; then
  $BB cp $D/gui_ini.NX500 $D/gui_ini.NX500.orig && echo "  备份 gui_ini.NX500"
fi

echo "=== 部署 ==="
$BB mkdir -p $D/filmlab
$BB cp $S/flab.sh $D/filmlab.sh && $BB chmod 755 $D/filmlab.sh && echo "  OK filmlab.sh"
$BB cp $S/nxflab.arm $D/filmlab/nxflab.arm && $BB chmod 755 $D/filmlab/nxflab.arm && echo "  OK nxflab.arm"
for f in gui_filmlab.NX500 gui_filmlab1b.NX500 gui_filmlab2.NX500 gui_filmlab3.NX500 gui_exit.sh flab_ui.sh; do
  $BB cp $S/$f $D/$f && $BB chmod 755 $D/$f && echo "  OK $f"
done

echo "=== 把 FilmLab 挂进主菜单 ==="
if ! $BB grep -qa gui_filmlab $D/gui_ini.NX500; then
  $BB grep -av "^button|返回\|^button|取消\|^$" $D/gui_ini.NX500 > $D/gui_ini.tmp
  echo "button|胶片配方 FilmLab|@$D/gui_filmlab.NX500" >> $D/gui_ini.tmp
  $BB cp $D/gui_ini.tmp $D/gui_ini.NX500
  $BB rm -f $D/gui_ini.tmp
  echo "  已插入到 gui_ini.NX500"
else
  echo "  已存在，跳过"
fi

echo "=== 验证 ==="
$D/filmlab.sh list 2>&1 | $BB tail -4
echo "--- 主菜单 ---"
$BB cat $D/gui_ini.NX500
echo "DEPLOY_DONE"
