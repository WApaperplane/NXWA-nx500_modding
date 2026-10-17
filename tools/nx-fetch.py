#!/usr/bin/env python3
"""nx-fetch.py - 相机文件抓取器: telnet 侧 cp→SD, FTP RETR→本地, 远端清理

用法:
  python nx-fetch.py <remote_path> <local_path> [--keep]
  python nx-fetch.py --cmd "shell 命令" <local_path> [--keep]   # 先用命令准备远端文件

前提: telnet(23)/FTP(21) 可达, root 空密码; FTP 根 = /mnt/mmc (SD 卡)。
遵守 G1-4: 结果文件走 FTP, 不信回显; 遵守 G1-5: 本工具只读(对相机侧: cp 到 SD 是可逆写, 完成后清理)。
"""
import socket, time, sys, ftplib, os

HOST = os.environ.get("NXHOST", "192.168.0.106")
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def _strip_iac(sock, data):
    out = bytearray(); i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd == SB:
                j = i + 2
                while j < len(data) - 1 and not (data[j] == IAC and data[j + 1] == SE):
                    j += 1
                i = j + 2; continue
            if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                opt = data[i + 2]
                if cmd == DO: sock.sendall(bytes([IAC, WONT, opt]))
                elif cmd == WILL: sock.sendall(bytes([IAC, DONT, opt]))
                i += 3; continue
            i += 2; continue
        out.append(b); i += 1
    return bytes(out)


def telnet_run(line, timeout=180):
    s = socket.create_connection((HOST, 23), timeout=10)
    s.settimeout(3); time.sleep(0.8)
    try: d = _strip_iac(s, s.recv(4096))
    except socket.timeout: d = b""
    if b"login:" in d:
        s.sendall(b"root\n")
        buf = b""; end = time.time() + 8
        while time.time() < end and b"#" not in buf:
            try: buf += _strip_iac(s, s.recv(2048))
            except socket.timeout: pass
        if b"Password:" in buf:
            s.sendall(b"\n"); time.sleep(0.8)
            try: _strip_iac(s, s.recv(2048))
            except socket.timeout: pass
    s.sendall(b"PS1='NXWA# '; export PS1\n"); time.sleep(0.4)
    try: _strip_iac(s, s.recv(2048))
    except socket.timeout: pass
    s.sendall(line.encode() + b"\n")
    buf = b""; end = time.time() + timeout; last = time.time()
    while time.time() < end:
        try:
            s.settimeout(0.5)
            d = _strip_iac(s, s.recv(4096))
            if d: buf += d; last = time.time()
            if b"NXWA# " in buf and time.time() - last > 0.8: break
        except socket.timeout:
            if buf and time.time() - last > 3: break
    s.sendall(b"exit\n"); time.sleep(0.3); s.close()
    return buf.decode("utf-8", "replace")


def ftp_pull(remote_name, local_path, tries=4):
    """RETR 带重试：SD(exFAT) 新建文件的目录项落盘有延迟，FTP 可能瞬时 550。"""
    last = None
    for i in range(tries):
        try:
            f = ftplib.FTP(); f.connect(HOST, 21, timeout=30); f.login("root", "")
            try:
                with open(local_path, "wb") as fh:
                    f.retrbinary("RETR " + remote_name, fh.write)
            finally:
                try: f.quit()
                except Exception: pass
            return
        except Exception as e:      # 550 / 瞬断
            last = e
            time.sleep(1.0 + i)
    raise last


def ftp_delete(remote_name):
    try:
        f = ftplib.FTP(); f.connect(HOST, 21, timeout=20); f.login("root", "")
        f.delete(remote_name); f.quit()
    except Exception:
        pass


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep = "--keep" in sys.argv
    if "--cmd" in sys.argv:
        i = sys.argv.index("--cmd")
        prep = sys.argv[i + 1]
        local = args[-1] if len(args) >= 1 else None
        # --cmd 模式下: remote 名从 prep 命令中的目标文件名提取（约定以 nxwa_fetch_ 命名）
    else:
        prep = None
        if len(args) < 2:
            print("usage: nx-fetch.py <remote_path> <local_path>  |  nx-fetch.py --cmd '...' <local_path>", file=sys.stderr)
            sys.exit(2)
        remote, local = args[0], args[1]
        # ★ 路径口径统一（10-16 实测）：telnet 侧 CWD 不是 /mnt/mmc ⇒ 必须绝对路径；
        #   而 FTP 已 chroot 到 /mnt/mmc ⇒ 只认相对根。此处统一以「FTP 相对」为入参，内部转换。
        if remote.startswith("/"):
            remote_rel = remote[len("/mnt/mmc/"):] if remote.startswith("/mnt/mmc/") else remote.lstrip("/")
            remote_abs = remote if remote.startswith("/mnt/mmc/") else "/mnt/mmc/" + remote.lstrip("/")
        else:
            remote_rel = remote
            remote_abs = "/mnt/mmc/" + remote
        tmp = "/mnt/mmc/nxwa_fetch_%d.bin" % os.getpid()
        # sync：强制 SD 落盘（exFAT 目录项延迟会让 FTP 瞬时 550，见 10-16 实测）
        prep = "cp -f '%s' '%s' && sync && ls -la '%s' && md5sum '%s'" % (remote_abs, tmp, tmp, tmp)

    out = telnet_run(prep)
    sys.stderr.write("--- telnet ---\n" + out + "\n")
    # 从命令输出找 md5（可选校验）
    name = None
    for line in out.splitlines():
        if "nxwa_fetch_" in line and line.strip():
            for tok in line.split():
                if tok.startswith("/mnt/mmc/nxwa_fetch_"):
                    name = tok.split("/")[-1]
    if name is None:
        # 兜底: 从 prep 命令里找
        import re
        m = re.search(r"/mnt/mmc/(nxwa_fetch_\d+\.bin)", prep)
        name = m.group(1) if m else None
    if name is None:
        print("!! 无法确定远端文件名", file=sys.stderr); sys.exit(3)
    ftp_pull(name, local)
    print("saved %s (%d bytes)" % (local, os.path.getsize(local)))
    if not keep:
        ftp_delete(name)


if __name__ == "__main__":
    main()
