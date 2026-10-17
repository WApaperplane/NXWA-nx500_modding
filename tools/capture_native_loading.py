#!/usr/bin/env python3
"""Run only the reviewed native-loading metadata probe; save evidence on the PC.

Uses short here-document lines and unique complete-line markers, not an echoed
prompt as completion. Does not upload scripts or log files, use FTP, restart,
attach, write memory or change camera parameters. Shell-local setup disables
echo/history for this connection only. Camera target is the project's known IP.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import time
from datetime import datetime, timezone
import uuid

from native_ui_loading import parse_probe

REPO = Path(__file__).resolve().parents[1]
HOST = os.environ.get("NXHOST", "192.168.0.106")
PROBE = REPO / "test_server/dicam/probe_native_loading.sh"


class TelnetCodec:
    def __init__(self):
        self.pending = b""

    def feed(self, data):
        data = self.pending + data
        output, replies = bytearray(), bytearray()
        position = 0
        while position < len(data):
            if data[position] != 255:
                output.append(data[position])
                position += 1
                continue
            if position + 1 >= len(data):
                break
            command = data[position + 1]
            if command == 255:
                output.append(255)
                position += 2
            elif command in (251, 252, 253, 254):
                if position + 2 >= len(data):
                    break
                if command in (251, 253):
                    replies.extend((255, 254 if command == 251 else 252, data[position + 2]))
                position += 3
            elif command == 250:
                end = data.find(b"\xff\xf0", position + 2)
                if end < 0:
                    break
                position = end + 2
            else:
                position += 2
        self.pending = data[position:]
        if len(self.pending) > 65536:
            raise RuntimeError("Oversized telnet negotiation")
        return bytes(output), bytes(replies)


def clean_lines(data):
    return data.replace(b"\r", b"").split(b"\n")


def extract_frame(data, nonce, allow_remote_error=False):
    lines = clean_lines(data)
    begin = ("NXWA_CAPTURE_BEGIN_" + nonce).encode()
    end_pattern = re.compile(("NXWA_CAPTURE_END_" + nonce + ":[0-9]+").encode())
    ends = [line for line in lines if end_pattern.fullmatch(line)]
    if lines.count(begin) != 1 or len(ends) != 1:
        raise ValueError("Missing/duplicate complete capture markers or nonzero remote status")
    end = ends[0]
    if not allow_remote_error and not end.endswith(b":0"):
        raise ValueError("Remote capture returned nonzero status")
    left, right = lines.index(begin), lines.index(end)
    if right <= left:
        raise ValueError("Capture markers out of order")
    return b"\n".join(lines[left + 1:right]).strip() + b"\n"


class CaptureError(RuntimeError):
    def __init__(self, message, transcript, nonce):
        super().__init__(message)
        self.transcript, self.nonce = transcript, nonce


def collect(script, host=HOST, timeout=25, allow_remote_error=False):
    codec = TelnetCodec()
    transcript = bytearray()
    nonce = uuid.uuid4().hex
    ready = ("NXWA_READY_" + nonce).encode()
    begin = "NXWA_CAPTURE_BEGIN_" + nonce
    end = "NXWA_CAPTURE_END_" + nonce

    with socket.create_connection((host, 23), timeout=10) as connection:
        connection.settimeout(0.5)

        def read_until(predicate, timeout):
            received = bytearray()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    raw = connection.recv(65536)
                except socket.timeout:
                    continue
                if not raw:
                    raise ConnectionError("Camera closed connection before complete capture")
                text, replies = codec.feed(raw)
                if replies:
                    connection.sendall(replies)
                received.extend(text)
                transcript.extend(text)
                if len(transcript) > 2 * 1024 * 1024:
                    raise RuntimeError("Capture exceeded 2 MiB limit")
                if predicate(bytes(received)):
                    return bytes(received)
            raise TimeoutError("Telnet phase did not return its explicit completion marker")

        banner = read_until(lambda data: b"login:" in data, 10)
        connection.sendall(b"root\n")
        login = read_until(lambda data: b"Password:" in data or bool(re.search(rb"[#$] ?$", data)), 10)
        if b"Password:" in login:
            connection.sendall(b"\n")
            read_until(lambda data: bool(re.search(rb"[#$] ?$", data)), 10)
        # Never match the prompt text echoed from a setup command as completion.
        setup = "unset HISTFILE; stty -echo 2>/dev/null; export TERM=dumb; printf '\\n%s\\n' '%s'\n" % ("%s", ready.decode())
        connection.sendall(setup.encode())
        read_until(lambda data: ready in clean_lines(data), 10)
        terminator = "NXWA_SCRIPT_" + nonce
        command = ("printf '\\n%s\\n' '%s'\n/bin/sh <<'%s'\n%s\n%s\n"
                   "nxwa_capture_rc=$?\nprintf '\\n%s:%%s\\n' \"$nxwa_capture_rc\"\n") % (
                       "%s", begin, terminator, script.rstrip(), terminator, end)
        connection.sendall(command.encode("utf-8"))
        try:
            pattern = re.compile((end + ":[0-9]+").encode())
            result = read_until(lambda data: any(pattern.fullmatch(line) for line in clean_lines(data)), timeout)
            body = extract_frame(result, nonce, allow_remote_error=allow_remote_error)
        except Exception as error:
            raise CaptureError(str(error), bytes(transcript), nonce) from error
        connection.sendall(b"exit\n")
    return body, bytes(transcript), nonce


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new PC evidence directory")
    parser.add_argument("--resident", action="store_true",
                        help="read only 41 known App/catalog bytes; no attach or debugger")
    options = parser.parse_args()
    if options.out.exists():
        parser.error("Output must not already exist")
    probe = PROBE.with_name("probe_native_resident.sh") if options.resident else PROBE
    script = probe.read_text(encoding="utf-8")
    if "\r" in script or "opens=rdonly" not in script:
        parser.error("Probe must be reviewed LF-only read-only source")
    started = datetime.now(timezone.utc).isoformat()
    body, transcript, nonce = collect(script)
    report = parse_probe(body.decode("utf-8")) if not options.resident else None
    receipt = {"schema": "nxwa.native-loading-receipt/1", "host": HOST,
               "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
               "nonce": nonce, "framed_remote_rc": 0,
               "probe": probe.name,
               "probe_sha256": hashlib.sha256(script.encode("utf-8")).hexdigest(),
               "capture_sha256": hashlib.sha256(body).hexdigest(),
               "transcript_sha256": hashlib.sha256(transcript).hexdigest(),
               "transport": "telnet_complete_line_nonce_frame_no_camera_logfile",
               "scope": "readonly_metadata_with_session_local_echo_history_setup"}
    options.out.mkdir(parents=True, exist_ok=False)
    (options.out / "capture.txt").write_bytes(body)
    (options.out / "transcript.txt").write_bytes(transcript)
    for filename, content in (("report.json", report), ("receipt.json", receipt)):
        if content is None:
            continue
        (options.out / filename).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if options.resident:
        print(json.dumps({"evidence": str(options.out), "capture_sha256": receipt["capture_sha256"],
                          "scope": "bounded_readonly_resident_attempt_not_full_app_verification"}, indent=2))
        return 0
    print(json.dumps({"evidence": str(options.out), "process_stable": report["process_stable"],
                      "process": report["process"], "target_file": report["target_file"],
                      "process_exe_file": report["process_exe_file"], "loadavg": report["loadavg"],
                      "locale": report["locale"], "catalog_map_lines": report["catalog_map_lines"]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
