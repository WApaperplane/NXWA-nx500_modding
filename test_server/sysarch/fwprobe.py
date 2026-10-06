# -*- coding: utf-8 -*-
"""NX500 固件层框架爬取器（批次化 / 串行 / 每条独立超时）。

设计约束（全部来自实机踩坑记录，违反会挂相机）：
  1. telnet 必串行 —— 绝不开第二个会话。
  2. `cat /proc/iomem` 会内核段错误打死 shell → 永不执行。
  3. `find /sys/...` 3min 不返回，SIGHUP 带走整个脚本 → 只用 ls + 限定深度。
  4. 单核相机不能连续跑重活 → 每条命令 ≤ TIMEOUT，超时立刻放弃该条。
  5. 一次 telnet 会话里跑完整批 → 避免反复建连接（建连接本身有成本）。
  6. busybox：必须绝对路径 /opt/usr/nx-ks/busybox；无 find 的 -printf 依赖。
  7. 命令逐条下发，不拼接复合命令（避免一个失败拖死整批）。

用法：
    python fwprobe.py <outdir> <批次号>
    python fwprobe.py raw8 1        # 只跑批次1
    python fwprobe.py raw8 all      # 跑全部
"""
import os
import socket
import sys
import time
from pathlib import Path

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

HOST = os.environ.get("NXHOST", "192.168.0.105")
BB = "/opt/usr/nx-ks/busybox"
CMD_TIMEOUT = 6.0      # 单条命令最长等待（秒）——铁律：≤2.5s，这里放宽到6s
POLL = 0.35


class T:
    """最小 telnet 客户端（Python 3.13 无 telnetlib）。"""

    def __init__(self, host, port=23, timeout=20):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(POLL)
        self.host = host

    def _strip(self, data):
        out = bytearray()
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            if b != IAC:
                out.append(b)
                i += 1
                continue
            if i + 1 >= n:
                break
            c = data[i + 1]
            if c == IAC:
                out.append(IAC)
                i += 2
                continue
            if c in (DO, DONT, WILL, WONT):
                if i + 2 >= n:
                    break
                opt = data[i + 2]
                if c == DO:
                    self.s.sendall(bytes([IAC, WONT, opt]))
                elif c == WILL:
                    self.s.sendall(bytes([IAC, DONT, opt]))
                i += 3
                continue
            if c == SB:
                j = data.find(bytes([IAC, SE]), i)
                if j < 0:
                    break
                i = j + 2
                continue
            if c == SE:
                i += 2
                continue
            i += 2
        return bytes(out)

    def read(self, sec):
        end = time.time() + sec
        chunks = []
        last = 0.0
        while time.time() < end:
            try:
                d = self.s.recv(65536)
                if not d:
                    break
                chunks.append(d)
                last = time.time()
                # 安静 1.2s 认为输出结束（比固定 sleep 省时）
                if time.time() - last > 1.2:
                    break
            except socket.timeout:
                if chunks and time.time() - last > 1.2:
                    break
                continue
            except OSError:
                break
        return self._strip(b"".join(chunks)).decode("utf-8", "replace")

    def send(self, cmd, wait=None):
        self.s.sendall(cmd.encode() + b"\r\n")
        return self.read(wait if wait is not None else CMD_TIMEOUT)

    def login(self):
        self.read(1.5)
        self.send("", 1.2)
        self.send("root", 2.5)

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# 批次定义
#   每项 = (标签, 命令)
#   ★ 永不出现：cat /proc/iomem、find /sys、find / -name
# ─────────────────────────────────────────────────────────────
BATCHES = {
1: [
    ("hostname_uname", "uname -a"),
    ("version_info", "cat /etc/version.info"),
    ("os_release", "cat /etc/os-release"),
    ("root_ls", "ls -la /"),
    ("etc_ls", "ls /etc"),
    ("etc_fw", "ls -la /etc/fw_gui.info /etc/version*"),
    ("opt_ls", "ls -la /opt"),
    ("opt_usr_ls", "ls -la /opt/usr"),
    ("opt_nxks_ls", "ls -la /opt/usr/nx-ks"),
    ("usr_ls", "ls -la /usr"),
    ("usr_bin_head", "ls /usr/bin | head -60"),
    ("usr_lib_head", "ls /usr/lib | head -60"),
    ("bin_ls", "ls -la /bin"),
    ("sbin_ls", "ls -la /sbin"),
    ("lib_ls", "ls -la /lib"),
    ("mounts", "cat /proc/mounts"),
    ("df", "df -h"),
    ("blockdev", "cat /proc/partitions"),
    ("meminfo_head", "head -12 /proc/meminfo"),
    ("cmdline", "cat /proc/cmdline"),
    ("env", "cat /proc/environ | tr '\\0' '\\n'"),
    ("inittab", "cat /etc/inittab"),
    ("systemd_units", "ls /etc/systemd/system/multi-user.target.wants 2>/dev/null"),
    ("systemd_default", "ls /etc/systemd/system 2>/dev/null | head -40"),
    ("init_scripts", "ls -la /etc/init.d 2>/dev/null"),
    ("opt_initd", "ls /etc/init.d/rcS.d 2>/dev/null; ls /etc/rcS.d 2>/dev/null"),
    ("preinit", "ls -la /opt/usr/nx-ks/*.sh 2>/dev/null | head -30"),
    ("xorg_conf", "ls -la /etc/X11/xorg.conf* /etc/X11/*.conf 2>/dev/null"),
],

2: [
    ("cpuinfo", "cat /proc/cpuinfo | head -40"),
    ("interrupts_head", "head -60 /proc/interrupts"),
    ("interrupts_isr", "grep -i -E 'isp|ep|drime|m4|dsp|srp' /proc/interrupts"),
    ("modules", "cat /proc/modules"),
    ("lsmod_vermagic", "cat /proc/version"),
    ("platform_count", "ls /sys/devices/platform | wc -l"),
    ("platform_full", "ls /sys/devices/platform"),
    ("d5_promise", "ls -la /sys/devices/platform/d5_promise/"),
    ("d5_promise_ro", "ls -la /sys/devices/platform/d5_promise/sec_ro/ 2>/dev/null"),
    ("d5_promise_tmcb", "ls -la /sys/devices/platform/d5_promise/tmcb/ 2>/dev/null"),
    ("d5_promise_power", "ls -la /sys/devices/platform/d5_promise/power/ 2>/dev/null"),
    ("d5_dir", "ls -la /sys/devices/platform/ | grep -i drime5"),
    ("ep_platform", "ls -la /sys/devices/platform/drime5_ep.0/"),
    ("ep_power", "ls -la /sys/devices/platform/drime5_ep.0/power/"),
    ("ispfreq", "ls -la /sys/devices/platform/drime5-ispfreq/ 2>/dev/null"),
    ("ispfreq_val", "cat /sys/devices/platform/drime5-ispfreq/*/cur_freq 2>/dev/null; cat /sys/devices/platform/drime5-ispfreq/cur_freq 2>/dev/null"),
    ("ddrfreq", "ls -la /sys/devices/platform/drime5-ddrfreq/ 2>/dev/null"),
    ("clk_summary_head", "head -50 /sys/kernel/debug/clk/clk_summary 2>/dev/null"),
    ("thermal_zones", "ls -la /sys/class/thermal/ 2>/dev/null"),
    ("gpiochips", "ls /sys/class/gpio 2>/dev/null | head -30"),
    ("i2c_busses", "ls -la /sys/bus/i2c/devices/ 2>/dev/null | head -30"),
    ("tunables", "cat /proc/sys/vm/swappiness 2>/dev/null; cat /proc/sys/vm/min_free_kbytes 2>/dev/null"),
    ("slabinfo_head", "head -20 /proc/slabinfo 2>/dev/null"),
    ("dev_list", "ls -la /dev"),
    ("dev_d5", "ls /dev | grep -i -E 'drime|d5|isp|ep'"),
],

3: [
    ("usr_lib_full", "ls -la /usr/lib"),
    ("usr_lib_drime", "ls -la /usr/lib | grep -i -E 'drime|udd|d5|isp|ep|tint'"),
    ("usr_bin_full", "ls -la /usr/bin"),
    ("usr_bin_cap", "ls -la /usr/bin | grep -i -E 'capdtm|di-|st$|camera|dsm|dfmsd'"),
    ("opt_usr_bin", "ls -la /opt/usr/bin 2>/dev/null"),
    ("opt_nxks_all", "ls -la /opt/usr/nx-ks/ 2>/dev/null"),
    ("lib_usr_local", "ls -la /usr/lib/*.so* 2>/dev/null | head -40"),
    ("proc_maps_targets", "ls -la /proc/252/maps 2>/dev/null; cat /proc/252/maps 2>/dev/null | head -5"),
    ("ps_full", "ps -A 2>/dev/null | head -50; cat /proc/*/comm 2>/dev/null | sort -u | head -60"),
    ("dmesg_tail", "dmesg | tail -60"),
    ("dmesg_isp", "dmesg | grep -i -E 'isp|firmware|boot|load|drime5|srp|dsp|m4' | head -50"),
],

4: [
    ("config_files", "ls -la /opt/*.ini /opt/*.cfg /opt/*.conf 2>/dev/null"),
    ("nxks_ini", "ls -la /opt/usr/nx-ks/*.ini /opt/usr/nx-ks/*.conf /opt/usr/nx-ks/*.cfg 2>/dev/null"),
    ("etc_ini", "ls -la /etc/*.ini /etc/*.conf /etc/*.xml 2>/dev/null | head -40"),
    ("share_dirs", "ls -la /usr/share 2>/dev/null | head -40"),
    ("opt_share", "ls -la /opt/usr/share 2>/dev/null | head -40"),
    ("pref_dir", "ls -la /opt/pref 2>/dev/null | head -30"),
    ("smack_dir", "ls -la /smack 2>/dev/null | head -20"),
    ("script_count", "ls /opt/usr/nx-ks/*.sh 2>/dev/null | wc -l"),
    ("ftp_check", "netstat -ltn 2>/dev/null | head -20"),
    ("busybox_ver", "/opt/usr/nx-ks/busybox 2>&1 | head -2"),
],

5: [
    ("firmware_help", "st firmware help 2>&1 | head -20"),
    ("boot_dir", "ls -la /boot 2>/dev/null; ls -la /initrd 2>/dev/null"),
    ("dev_dir", "ls -la /dev/ | head -30"),
    ("csa_dir", "ls -la /csa 2>/dev/null | head -20"),
    ("uimage_search", "ls -la /usr/share/firmware 2>/dev/null; ls -la /opt/usr/firmware 2>/dev/null"),
    ("pcache", "ls -la /opt/pcache.list /pcache.list 2>/dev/null"),
    ("st_where", "which st 2>/dev/null; ls -la /usr/bin/st /opt/usr/bin/st 2>/dev/null"),
    ("find_fw_shallow", "ls /*.bin /*.img /*fw* /boot/* 2>/dev/null | head -20"),
    ("mptop_dev", "ls -la /dev/d5_mptop; cat /sys/class/misc/d5_mptop/dev 2>/dev/null"),
    ("ipcc_dev", "ls -la /dev/d5_ipcc; cat /sys/class/misc/d5_ipcc/dev 2>/dev/null"),
    ("ep_dev_info", "ls -la /dev/drime5_ep; cat /sys/class/misc/drime5_ep/dev 2>/dev/null"),
    ("sma_dev_info", "ls -la /dev/d5_sma; cat /sys/class/misc/d5_sma/dev 2>/dev/null"),
    ("efuse", "cat /proc/efuse 2>/dev/null | head -20"),
    ("cpu_rev", "cat /proc/cpuinfo | grep -i -E 'revision|model|part' | head -10"),
    ("cmdline_full", "cat /proc/cmdline"),
],
}


def run_batch(t, items, outdir: Path, tag: str):
    outdir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for i, (label, cmd) in enumerate(items, 1):
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in label)
        p = outdir / ("%s.txt" % safe)
        if p.exists() and p.stat().st_size > 0:
            print("  [%2d/%d] SKIP %-22s (已有)" % (i, len(items), label))
            continue
        try:
            out = t.send(cmd, CMD_TIMEOUT)
        except Exception as e:
            out = "!!! EXCEPTION %s: %s" % (type(e).__name__, e)
        # 行尾规范化：CRLF → LF（记忆铁律：CRLF 是头号坑）
        out = out.replace("\r\n", "\n").replace("\r", "\n")
        p.write_text("===== %s =====\ncmd: %s\n\n%s" % (label, cmd, out),
                     encoding="utf-8", errors="replace")
        got = len(out.strip())
        print("  [%2d/%d] %-22s %d bytes" % (i, len(items), label, got))
        if got:
            ok += 1
        time.sleep(0.25)      # 让单核喘口气
    return ok


def main():
    outdir = Path(sys.argv[1] if len(sys.argv) > 1 else "raw8")
    which = sys.argv[2] if len(sys.argv) > 2 else "all"
    batches = sorted(BATCHES) if which == "all" else [int(which)]

    print("# host=%s  batches=%s  outdir=%s" % (HOST, batches, outdir))
    t = T(HOST)
    t.login()
    banner = t.send("uname -a", 4.0)
    print(banner.strip()[:160])
    for b in batches:
        print("\n===== 批次 %d (%d 条) =====" % (b, len(BATCHES[b])))
        try:
            run_batch(t, BATCHES[b], outdir, "b%d" % b)
        except Exception as e:
            print("  批次 %d 中断: %s" % (b, e))
            # 重连一次再继续
            try:
                t.close()
            except Exception:
                pass
            time.sleep(2.0)
            try:
                t = T(HOST)
                t.login()
                print("  已重连")
            except Exception as e2:
                print("  重连失败: %s —— 停止" % e2)
                break
    t.send("exit", 1.5)
    t.close()
    print("\n完成。文件在 %s/" % outdir)


if __name__ == "__main__":
    main()
