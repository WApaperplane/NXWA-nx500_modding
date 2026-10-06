#!/bin/sh
B=/opt/usr/nx-ks/busybox
K=/opt/usr/nx-ks
L=/mnt/mmc/_fl2/fixecore.log
: > $L

# ★ 备份 init.sh
if [ ! -f $K/init.sh.orig ]; then
  cp $K/init.sh $K/init.sh.orig && echo "已备份 → init.sh.orig" >> $L
else
  echo "备份已存在，跳过" >> $L
fi

echo "--- 原始行 ---" >> $L
$B grep -n "ECORE_INPUT" $K/init.sh >> $L 2>&1

echo "--- 改为 500 ---" >> $L
$B sed -i "s/ECORE_INPUT_TIMEOUT_FIX=0/ECORE_INPUT_TIMEOUT_FIX=500/" $K/init.sh
$B grep -n "ECORE_INPUT" $K/init.sh >> $L 2>&1

echo "" >> $L
echo "--- 行尾检查（前3 字节，须 23 21 2f = #!/）---" >> $L
$B od -A d -t x1 -N 3 $K/init.sh >> $L 2>&1

echo "--- 语法检查 ---" >> $L
if sh -n $K/init.sh 2>>$L; then
  echo "语法 OK" >> $L
else
  echo "★ 语法错误（已回滚）" >> $L
  cp $K/init.sh.orig $K/init.sh
  echo "已回滚" >> $L
fi

echo "--- 相关段（18-28 行）---" >> $L
$B sed -n "18,28p" $K/init.sh >> $L
echo "=== DONE ===" >> $L
echo done
