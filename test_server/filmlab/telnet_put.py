"""通过 telnet 把文件 base64 分块传到相机 rw 分区。

为什么不走 push 通道：push-cgi 的 path 白名单只允许 `nx-rc/web_root/`，
而我们要放的是可执行文件到 /opt/usr/nx-ks/（rw 的 mmcblk0p14）。

三个必须注意的环境事实（2026-10-03 实测踩坑）：
1. **相机没有裸 `base64` 命令**，只有 busybox applet：
   `/opt/usr/nx-ks/busybox base64 -d`（busybox 不在 PATH，裸调用 command not found）
2. **Git Bash 会把 POSIX 路径 `/opt/usr/...` 转成 Windows 路径**
   （`C:/Users/.../opt/usr/...`）—— 所以远端路径统一用变量 `${R}` 传，
   由 shell 自己展开，Python 侧不做字符串拼接。
3. 一次只开一个 telnet 连接（相机单核，并发两个连接会把它打挂）。

用法：python telnet_put.py <ip> <local-file> <remote-path>
"""
import base64
import socket
import sys
import time
from pathlib import Path

CHUNK_LINES = 200
BATCH_LINES = 10
BUSYBOX = "/opt/usr/nx-ks/busybox"


class Telnet:
    def __init__(self, host: str, port: int = 23, timeout: float = 10.0):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(2)
        self._drain(2.0)
        self.s.sendall(b"root\n")
        self._drain(1.5)

    def _drain(self, t: float = 1.5) -> str:
        end = time.time() + t
        out = b""
        while time.time() < end:
            try:
                c = self.s.recv(65536)
                if not c:
                    break
                out += c
            except socket.timeout:
                pass
        clean = bytearray()
        i = 0
        while i < len(out):
            if out[i] == 0xFF and i + 2 < len(out):
                i += 3
                continue
            clean.append(out[i])
            i += 1
        return clean.decode("utf-8", errors="replace")

    def run(self, cmd: str, wait: float = 1.5) -> str:
        self.s.sendall((cmd + "\n").encode())
        time.sleep(0.2)
        return self._drain(wait)

    def close(self):
        self.s.close()


def put(host: str, local: Path, remote: str) -> bool:
    data = local.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    lines = [b64[i : i + 76] for i in range(0, len(b64), 76)]
    print("local : %s  (%d bytes)" % (local, len(data)))
    print("target: %s" % remote)
    print("b64   : %d bytes / %d lines, %d chunks of %d"
          % (len(b64), len(lines), (len(lines) + CHUNK_LINES - 1) // CHUNK_LINES, CHUNK_LINES))

    t = Telnet(host)
    # 远端路径用 shell 变量传入。必须配合 MSYS_NO_PATHCONV=1 运行
    # （见 run.bat），否则 Git Bash 会把 /opt/usr/... 转成 Windows 路径。
    t.run('R=%s; D=$(dirname "$R"); echo "TARGET=$R"; mkdir -p "$D"; rm -f "$R".b64 "$R".part; : > "$R".part; %s ls -ld "$D"' % (remote, BUSYBOX), wait=3.0)
    print("[1/3] target dir ready: %s" % remote)

    total = 0
    for i in range(0, len(lines), CHUNK_LINES):
        chunk = lines[i : i + CHUNK_LINES]
        # 两个关键点，都是实测踩出来的：
        #
        # 1) busybox 的 `echo a b c` 把多个参数用空格连成**一行**。
        #    实测 `echo "aaa" "bbb" "ccc" >> f` 产出 `aaa bbb ccc\n`（1 行），
        #    所以每行必须独立一次 echo。
        #
        # 2) 单条命令里堆 50 个 echo（≈4KB）会被 telnet 层截断，
        #    实测 .part 变成 0 字节。降到 10 个 echo/命令（≈900 字节）稳定。
        for j in range(0, len(chunk), BATCH_LINES):
            sub = chunk[j : j + BATCH_LINES]
            payload = ";".join("echo '%s' >> \"$R\".b64" % x for x in sub)
            t.run(payload, wait=0.5)
        # 等 busybox 把这一批解码落盘再发下一条。单核相机写 SD 卡很慢，
        # 指令发太密会「上一条还在写、下一条已到达」导致内容交错/丢失。
        t.run('%s base64 -d "$R".b64 >> "$R".part && rm -f "$R".b64' % BUSYBOX, wait=4.0)
        total += len(chunk)
        # 校验：解码后 .part 至少要有这么多个字节（每 4 个 b64 字符 -> 3 字节）。
        # 单调增长能立刻暴露「某批静默失败」，否则要等到最后才发现白传。
        want_min = int(total / len(lines) * len(data) * 0.9)
        r = t.run('wc -c < "$R".part', wait=1.0)
        got = 0
        for tok in r.replace("\r", " ").split():
            if tok.isdigit():
                got = int(tok)
                break
        flag = "ok" if got >= want_min else "SLOW/BLOCKED"
        print("      %d/%d lines (%.0f%%)  part=%d bytes  expect>=%d  %s"
              % (total, len(lines), total * 100.0 / len(lines), got, want_min, flag))
        if total < len(lines) and got == 0:
            print("      WARN: .part still 0 bytes, aborting to avoid wasted time")
            t.close()
            return False
    print("[2/3] base64 written")

    # 注意：每批都已经 `base64 -d` 过了，所以 $R.part 里累积的**已经是二进制**，
    # 收尾只需改名 + 裁掉可能的尾部多余字节，**绝不能再解一次**。
    # （踩过：多解一次得到 0 字节文件，以为传输失败。）
    exp_b64_lines = len(lines)
    out = t.run(
        'echo "" >> "$R".b64 2>/dev/null; true',  # no-op, 保持 shell 语义清晰
        wait=0.3)
    out = t.run(
        'SZ=$(wc -c < "$R".part); echo "part=$SZ expect=%d"; '
        'if [ "$SZ" -gt %d ]; then %s dd if="$R".part of="$R".t bs=1 count=%d 2>/dev/null; mv "$R".t "$R"; '
        'else mv "$R".part "$R"; fi; rm -f "$R".b64; chmod +x "$R"; ls -la "$R"; md5sum "$R"'
        % (len(data), len(data), BUSYBOX, len(data)),
        wait=8.0)
    print(out)
    print("[3/3] installed")
    t.close()
    return True


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    return 0 if put(sys.argv[1], Path(sys.argv[2]), sys.argv[3]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
