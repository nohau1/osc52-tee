from __future__ import annotations

import base64
import importlib.machinery
import importlib.util
import os
import pathlib
import stat
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "osc52-tee"

_loader = importlib.machinery.SourceFileLoader("osc52_tee", str(BIN))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec is not None
mod = importlib.util.module_from_spec(_spec)
_loader.exec_module(mod)


def osc(payload: bytes, target: bytes = b"c", end: bytes = b"\x07") -> bytes:
    return b"\x1b]52;" + target + b";" + base64.b64encode(payload) + end


class ParserTests(unittest.TestCase):
    def test_bel(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(osc(b"hello")), [b"hello"])

    def test_st(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(osc(b"hello", end=b"\x1b\\")), [b"hello"])

    def test_split_across_reads(self) -> None:
        parser = mod.Osc52Parser()
        data = osc(b"hello\nworld")
        out: list[bytes] = []
        for index in range(0, len(data), 3):
            out += parser.feed(data[index : index + 3])
        self.assertEqual(out, [b"hello\nworld"])

    def test_multiple_copies(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(osc(b"one") + osc(b"two")), [b"one", b"two"])

    def test_read_query_ignored(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(b"\x1b]52;c;?\x07"), [])

    def test_empty_payload_ignored(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(b"\x1b]52;c;\x07"), [])

    def test_malformed_base64_ignored(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(b"\x1b]52;c;%%%%\x07"), [])

    def test_max_bytes(self) -> None:
        parser = mod.Osc52Parser(max_bytes=4)
        self.assertEqual(parser.feed(osc(b"hello")), [])
        self.assertEqual(parser.feed(osc(b"hi")), [b"hi"])

    def test_unbounded_payload_is_dropped(self) -> None:
        parser = mod.Osc52Parser(max_bytes=4)
        parser.feed(b"\x1b]52;c;" + b"A" * 10000)
        self.assertGreaterEqual(parser.dropped, 1)

    def test_non_utf8_payload(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(osc(b"\xff\xfe")), [b"\xff\xfe"])

    def test_text_around_sequence(self) -> None:
        parser = mod.Osc52Parser()
        self.assertEqual(parser.feed(b"before" + osc(b"x") + b"after"), [b"x"])


class CopySinkTests(unittest.TestCase):
    def test_command_receives_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "clip")
            code = "import sys; open(sys.argv[1], 'ab').write(sys.stdin.buffer.read())"
            sink = mod.CopySink([sys.executable, "-c", code, target])
            sink.submit(b"one")
            sink.submit(b"two")
            sink.close()
            with open(target, "rb") as handle:
                self.assertEqual(handle.read(), b"onetwo")

    def test_no_command_is_noop(self) -> None:
        sink = mod.CopySink([])
        sink.submit(b"data")
        sink.close()


class LogTests(unittest.TestCase):
    def test_log_and_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "log")
            stream_path = os.path.join(tmp, "stream")
            log_fd = mod.open_append(log_path)
            stream_fd = mod.open_append(stream_path)
            assert log_fd is not None and stream_fd is not None
            try:
                mod.write_copy(log_fd, stream_fd, b"hello\nworld")
            finally:
                os.close(log_fd)
                os.close(stream_fd)

            with open(log_path, "rb") as handle:
                log = handle.read()
            self.assertIn(b"hello\nworld", log)
            self.assertIn(b"===== copy ", log)
            self.assertEqual(stat.S_IMODE(os.stat(log_path).st_mode), 0o600)

            with open(stream_path, "rb") as handle:
                line = handle.read().strip()
            self.assertEqual(base64.b64decode(line), b"hello\nworld")


if __name__ == "__main__":
    unittest.main()
