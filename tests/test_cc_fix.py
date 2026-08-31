"""CC_main 修复回归测试（只新增本文件，不依赖伪造业务数据）。"""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from _paths import data_dir  # noqa: E402
from allocation_ledger import AmbiguousTermError, Ledger  # noqa: E402


LEDGER_DATA = ROOT / "data" / "gz"
LEDGER_READY = all(
    (LEDGER_DATA / filename).is_file()
    for filename in ("unit_attributes.json", "basic_units_wgs.json")
)
DEGRADED_READY = all(
    (LEDGER_DATA / filename).is_file()
    for filename in (
        "region.json",
        "unit_attributes.json",
        "basic_units_wgs.json",
        "territory_compiled.json",
    )
)


def _post_json(handler_cls, path: str, payload: dict) -> tuple[int, dict]:
    """通过 socketpair 调用真实 Handler，不监听本地 TCP 端口。"""
    client, server = socket.socketpair()
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = (
        f"POST {path} HTTP/1.0\r\n"
        "Host: localhost\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("ascii") + body
    client.settimeout(3)
    errors = []

    def serve():
        try:
            handler_cls(server, ("local", 0), object())
        except BaseException as exc:  # surface handler failures in the test thread
            errors.append(exc)

    worker = threading.Thread(target=serve)
    try:
        client.sendall(request)
        worker.start()
        chunks = []
        expected = None
        while True:
            try:
                chunk = client.recv(65536)
            except socket.timeout:
                break
            if not chunk:
                break
            chunks.append(chunk)
            response = b"".join(chunks)
            if b"\r\n\r\n" in response:
                headers, response_body = response.split(b"\r\n\r\n", 1)
                match = re.search(rb"Content-Length: (\d+)", headers,
                                  flags=re.IGNORECASE)
                expected = int(match.group(1)) if match else 0
                if len(response_body) >= expected:
                    break
        response = b"".join(chunks)
        worker.join(timeout=3)
        self_error = errors[0] if errors else None
    finally:
        client.close()
        server.close()
    if worker.is_alive():
        raise AssertionError("Handler 未在限定时间内完成")
    if self_error is not None:
        raise self_error
    headers, response_body = response.split(b"\r\n\r\n", 1)
    status = int(headers.splitlines()[0].split()[1])
    length = re.search(rb"Content-Length: (\d+)", headers,
                       flags=re.IGNORECASE)
    if length:
        response_body = response_body[: int(length.group(1))]
    return status, json.loads(response_body.decode("utf-8"))


class TestCCFix(unittest.TestCase):
    def test_paths_priority(self):
        with tempfile.TemporaryDirectory() as explicit_dir, \
                tempfile.TemporaryDirectory() as env_dir:
            with patch.dict(os.environ, {"SRAF_DATA_DIR": env_dir}):
                self.assertEqual(data_dir(explicit_dir), Path(explicit_dir))
                self.assertEqual(data_dir(), Path(env_dir))
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(data_dir(), ROOT / "data" / "gz")

    def test_no_hardcoded_user_path(self):
        pattern = re.compile(r"/Users/[^/\s\"']+/")
        hits = []
        for path in sorted(TOOLS.glob("*.py")):
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if pattern.search(line):
                    hits.append(f"{path}:{line_no}: {line.strip()}")
        self.assertEqual(hits, [], "tools/*.py 含用户目录硬编码:\n" + "\n".join(hits))

    @unittest.skipUnless(LEDGER_READY, "缺少真实 data/gz 台账文件")
    def test_ambiguous_term_raises(self):
        ledger = Ledger(data_dir=LEDGER_DATA)
        with self.assertRaises(AmbiguousTermError):
            ledger.resolve_units("大")

    @unittest.skipUnless(LEDGER_READY, "缺少真实 data/gz 台账文件")
    def test_exact_term_still_works(self):
        ledger = Ledger(data_dir=LEDGER_DATA)
        self.assertTrue(ledger.resolve_units("赤岗街道"))

    @unittest.skipUnless(LEDGER_READY, "缺少真实 data/gz 台账文件")
    def test_no_single_char_key(self):
        ledger = Ledger(data_dir=LEDGER_DATA)
        self.assertFalse([key for key in ledger.by_street if len(key) == 1])

    @unittest.skipUnless(DEGRADED_READY, "缺少真实 data/gz 降级链路文件")
    def test_degraded_marks_confidence(self):
        import importlib

        demo_server = importlib.import_module("demo_server")
        row = next(
            row for row in json.loads(
                (LEDGER_DATA / "territory_compiled.json").read_text(encoding="utf-8")
            ) if row.get("S")
        )
        sentinel = object()
        old_tc = demo_server.__dict__.get("_TC_MOD", sentinel)
        old_ledger = demo_server.STATE.get("ledger")
        try:
            # 让真实 S 片回放失败，验证 P3 的真实台账降级响应。
            demo_server._TC_MOD = SimpleNamespace(U=[])
            demo_server.STATE["ledger"] = None
            status, result = _post_json(
                demo_server.Handler,
                "/api/generate",
                {"area_id": row["area_id"]},
            )
        finally:
            demo_server.STATE["ledger"] = old_ledger
            if old_tc is sentinel:
                demo_server.__dict__.pop("_TC_MOD", None)
            else:
                demo_server._TC_MOD = old_tc
        self.assertEqual(status, 200, result)
        self.assertIn("confidence", result)
        self.assertNotEqual(result["confidence"], "high")
        self.assertTrue(result.get("degraded_reason"))

    def test_fence_granularity_fallback(self):
        from tests.test_multicomponent import FakeKB, make_world
        import intelligence.adjust as adjust

        old = {
            name: getattr(adjust, name)
            for name in ("_DATA_DIR", "_ROWS", "_TC", "_STREET_DISTRICT")
        }
        try:
            with tempfile.TemporaryDirectory() as empty_data:
                adjust.set_data_dir(Path(empty_data))
                proposal = adjust.parse_and_propose(
                    make_world(), FakeKB(),
                    "把经销商乙的整个区域划给经销商甲",
                )
                self.assertEqual(proposal.impact["area"]["granularity"], "fence")
        finally:
            for name, value in old.items():
                setattr(adjust, name, value)


if __name__ == "__main__":
    unittest.main()
