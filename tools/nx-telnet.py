#!/usr/bin/env python3
"""nx-telnet.py - NX500 相机 telnet 批量命令执行器 (纯 socket, 无 telnetlib)

用法:
  python nx-telnet.py -c "cmd1" -c "cmd2"        # 多条命令
  python nx-telnet.py -f cmds.txt                # 从文件读命令(每行一条)
  python nx-telnet.py --raw -c "cmd"             # 只输出原始流

输出: 每条命令以 <<< CMD: xxx  分隔, 便于解析。
"""
import os, socket, sys, time, argparse, re

HOST = os.environ.get("NXHOST", "192.168.0.106")
PORT = 23
IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240


def _negotiate(sock):
    """读取并应答 telnet IAC 协商流, 返回净化后的数据。"""
    try:
        data = sock.recv(4096)
    except socket.timeout:
        return b""
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        if b == IAC and i + 1 < len(data):
            cmd = data[i + 1]
            if cmd == SB:  # 子协商, 跳到 SE
                j = i + 2
                while j < len(data) - 1 and not (data[j] == IAC and data[j + 1] == SE):
                    j += 1
                i = j + 2
                continue
            if cmd in (DO, DONT, WILL, WONT) and i + 2 < len(data):
                opt = data[i + 2]
                if cmd == DO:
                    sock.sendall(bytes([IAC, WONT, opt]))
                elif cmd == WILL:
                    sock.sendall(bytes([IAC, DONT, opt]))
                i += 3
                continue
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


def _recv_until(sock, patterns, timeout=8.0, quiet=0.6):
    """收数据直到匹配任一 pattern 或静默超时。patterns: list of bytes/regex str。"""
    buf = b""
    end = time.time() + timeout
    last = time.time()
    while time.time() < end:
        try:
            sock.settimeout(0.4)
            d = sock.recv(4096)
            if not d:
                break
            buf += d
            last = time.time()
            for p in patterns:
                if isinstance(p, bytes):
                    if p in buf:
                        return buf
                else:
                    if re.search(p, buf.decode("utf-8", "replace")):
                        return buf
        except socket.timeout:
            if time.time() - last > quiet and buf:
                return buf
        except Exception:
            break
    return buf


def run(cmds, raw_only=False, verbose=False):
    s = socket.create_connection((HOST, PORT), timeout=10)
    s.settimeout(3)
    time.sleep(0.8)
    banner = _negotiate(s)
    if verbose:
        sys.stderr.write("--- banner ---\n" + banner.decode("utf-8", "replace"))
    if b"login:" in banner:
        s.sendall(b"root\n")
        r = _recv_until(s, [b"Password:", b"# ", b"$ "], timeout=6)
        if b"Password:" in r:
            s.sendall(b"\n")
            r += _recv_until(s, [b"# ", b"$ "], timeout=6)
    # 设置无回显 + 宽终端
    s.sendall(b"export PS1='NXWA# '; stty -echo 2>/dev/null; export TERM=dumb\n")
    _recv_until(s, [b"NXWA# "], timeout=4)

    for c in cmds:
        s.sendall(c.encode() + b"\n")
        out = _recv_until(s, [b"NXWA# "], timeout=25, quiet=1.0)
        txt = out.decode("utf-8", "replace")
        txt = txt.replace("NXWA# ", "")
        txt = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", txt)
        txt = txt.replace("\r", "")
        if not raw_only:
            print(f"<<< CMD: {c}")
        print(txt.strip())
        print()
    s.sendall(b"exit\n")
    s.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", action="append", default=[])
    ap.add_argument("-f")
    ap.add_argument("--raw", action="store_true")
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    cmds = list(a.c)
    if a.f:
        with open(a.f, "r", encoding="utf-8") as fh:
            cmds += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    if not cmds:
        print("no commands", file=sys.stderr)
        sys.exit(2)
    run(cmds, raw_only=a.raw, verbose=a.v)


if __name__ == "__main__":
    main()
