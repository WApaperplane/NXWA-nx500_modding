# -*- coding: utf-8 -*-
"""最小 telnet 客户端（Python 3.13 无 telnetlib）
   只做：连接 / 读 / 写 / 忽略 IAC 协商。不做终端仿真。
   ★ telnet 必串行：绝不在同一台相机上并发开两个会话。"""
import socket, time

IAC, DONT, DO, WONT, WILL, SB, SE = 255, 254, 253, 252, 251, 250, 240

class MiniTel:
    def __init__(self, host, port=23, timeout=25):
        self.s = socket.create_connection((host, port), timeout=timeout)
        self.s.settimeout(0.4)
        self.host = host
        self._buf = b''

    def _strip_iac(self, data):
        """剥离 telnet 协议字节，只留应用数据"""
        out = bytearray(); i = 0; n = len(data)
        while i < n:
            b = data[i]
            if b != IAC:
                out.append(b); i += 1; continue
            if i + 1 >= n: break
            c = data[i+1]
            if c == IAC:            # 转义的 255
                out.append(IAC); i += 2; continue
            if c in (DO, DONT, WILL, WONT):
                if i + 2 >= n: break
                opt = data[i+2]
                # 全部拒绝：回 WONT/DONT，不进入任何选项
                if c == DO:   self.s.sendall(bytes([IAC, WONT, opt]))
                elif c == WILL: self.s.sendall(bytes([IAC, DONT, opt]))
                i += 3; continue
            if c == SB:
                j = data.find(bytes([IAC, SE]), i)
                if j < 0: break
                i = j + 2; continue
            if c == SE: i += 2; continue
            i += 2
        return bytes(out)

    def read(self, sec=3.0):
        end = time.time() + sec
        chunks = []
        while time.time() < end:
            try:
                d = self.s.recv(65536)
                if not d:
                    break
                chunks.append(d)
                end = time.time() + min(0.5, sec)   # 收到就快速收尾
            except socket.timeout:
                continue
            except OSError:
                break
        raw = b''.join(chunks)
        return self._strip_iac(raw).decode('utf-8', 'replace')

    def send(self, cmd, wait=5.0):
        self.s.sendall(cmd.encode('utf-8') + b'\r\n')
        return self.read(wait)

    def close(self):
        try: self.s.close()
        except Exception: pass
