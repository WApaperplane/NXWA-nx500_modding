#!/usr/bin/env python3
"""Pure framing/codec regression; no sockets or camera access."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from capture_native_loading import TelnetCodec, extract_frame


class CaptureTests(unittest.TestCase):
    def test_fragmented_option_negotiation(self):
        codec = TelnetCodec()
        self.assertEqual(codec.feed(b"hello\xff"), (b"hello", b""))
        self.assertEqual(codec.feed(b"\xfd"), (b"", b""))
        self.assertEqual(codec.feed(b"\x01world"), (b"world", b"\xff\xfc\x01"))

    def test_subnegotiation_and_literal_iac(self):
        codec = TelnetCodec()
        self.assertEqual(codec.feed(b"a\xff\xfa\x1fabc"), (b"a", b""))
        self.assertEqual(codec.feed(b"\xff\xf0b\xff\xff"), (b"b\xff", b""))

    def test_quoted_echo_is_not_a_frame(self):
        with self.assertRaises(ValueError):
            extract_frame(b"printf 'NXWA_CAPTURE_BEGIN_n'\nNXWA_CAPTURE_END_n:0\n", "n")

    def test_complete_frame_ignores_prompt_and_preserves_payload(self):
        text = b"root# \r\nNXWA_CAPTURE_BEGIN_n\r\npayload\r\nNXWA_CAPTURE_END_n:0\r\nroot# "
        self.assertEqual(extract_frame(text, "n"), b"payload\n")

    def test_incomplete_nonzero_duplicate_and_reversed_frames_rejected(self):
        for data in (b"NXWA_CAPTURE_BEGIN_n\npayload\n", b"NXWA_CAPTURE_BEGIN_n\nNXWA_CAPTURE_END_n:7\n",
                     b"NXWA_CAPTURE_BEGIN_n\nNXWA_CAPTURE_BEGIN_n\nNXWA_CAPTURE_END_n:0\n",
                     b"NXWA_CAPTURE_END_n:0\nNXWA_CAPTURE_BEGIN_n\n"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                extract_frame(data, "n")

    def test_explicit_nonzero_capture_retains_failure_evidence(self):
        data = b"NXWA_CAPTURE_BEGIN_n\nrollback=verified\nNXWA_CAPTURE_END_n:20\n"
        self.assertEqual(extract_frame(data, "n", allow_remote_error=True), b"rollback=verified\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
