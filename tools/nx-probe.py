#!/usr/bin/env python3
"""nx-probe.py - NX500 相机只读探测: telnet 发一条复合命令 -> 落 SD 卡 -> FTP 取回

遵循门控 G1-4: 一会话一条命令 / 结果走 FTP 不走回显。

用法:
  python nx-probe.py -c "cmd1" -c "cmd2"      # 合成一条 { ... } 复合语句
  python nx-probe.py -f probe.sh              # 从文件读脚本

输出: SD 卡 nxwa_probe.txt 的内容 -> stdout
"""
import socket, time, re, argparse, sys, ftplib, io, os

HOST = "192.168.0.105"
REMOTE = f"nxwa_probe_{os.getpid()}.txt"   # FTP 根 = /mnt/mmc = SD 卡（带 pid 防并发覆盖）
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


def telnet_send(line, prompt=b"NXWA# ", timeout=90):
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
    s.sendall(b"PS1='NXWA# '; export PS1\n"); time.sleep(0.5)
    try: _strip_iac(s, s.recv(2048))
    except socket.timeout: pass
    s.sendall(line.encode() + b"\n")
    buf = b""; end = time.time() + timeout; last = time.time()
    while time.time() < end:
        try:
            s.settimeout(0.5)
            d = _strip_iac(s, s.recv(4096))
            if d: buf += d; last = time.time()
            if prompt in buf and time.time() - last > 0.8: break
        except socket.timeout:
            if buf and time.time() - last > 3: break
    s.sendall(b"exit\n"); time.sleep(0.3); s.close()
    return buf


def ftp_get(remote):
    f = ftplib.FTP(); f.connect(HOST, 21, timeout=20)
    f.login("root", "")
    buf = io.BytesIO()
    f.retrbinary(f"RETR {remote}", buf.write)
    f.quit()
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", action="append", default=[])
    ap.add_argument("-f")
    ap.add_argument("--keep", action="store_true", help="不删除远端文件")
    a = ap.parse_args()
    cmds = list(a.c)
    if a.f:
        with open(a.f, encoding="utf-8") as fh:
            cmds += [l.rstrip("\n") for l in fh if l.strip() and not l.lstrip().startswith("#")]
    if not cmds:
        print("no commands", file=sys.stderr); sys.exit(2)
    body = " ; ".join(cmds) if len(cmds) == 1 else "\n".join(cmds)
    wrapped = "{\n" + body + "\n} > /mnt/mmc/" + REMOTE + " 2>&1"
    telnet_send(wrapped)
    time.sleep(0.4)
    try:
        data = ftp_get(REMOTE)
    except Exception as e:
        print(f"FTP fetch failed: {e}", file=sys.stderr); sys.exit(3)
    txt = data.decode("utf-8", "replace").replace("\r", "")
    sys.stdout.write(txt)
    if not txt.endswith("\n"): print()
    if not a.keep:   # 默认清理远端临时文件，避免在 SD 卡根目录留垃圾
        try:
            f2 = ftplib.FTP(); f2.connect(HOST, 21, timeout=20); f2.login("root", "")
            f2.delete(REMOTE); f2.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
