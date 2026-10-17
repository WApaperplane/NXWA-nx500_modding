#!/bin/bash
# Download/extract development tools locally; does not install system packages.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p out/deps
cd out/deps
if [ ! -f .ready ]; then
    apt-get download libx11-dev x11proto-dev libxft-dev libfreetype-dev \
        libfontconfig-dev libxrender-dev libxau-dev libxdmcp-dev libxft2 \
        xvfb xserver-common libxfont2 libfontenc1 libxkbfile1 xfonts-base x11-xkb-utils
    for package in ./*.deb; do dpkg-deb -x "$package" .; done
    touch .ready
fi
LD_LIBRARY_PATH="$PWD/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    usr/bin/Xvfb -help > xvfb-help.txt 2>&1 || true
head -2 xvfb-help.txt
gcc -shared -fPIC ../../xvfb_local_paths.c -ldl -o ../xvfb_local_paths.so
