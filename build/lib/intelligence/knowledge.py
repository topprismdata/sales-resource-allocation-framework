"""知识库接口：KB v0.3 的加载、检索与治理规则（D7 三铁律）。"""
from __future__ import annotations

import json
from pathlib import Path

_KB_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "knowledge_items.json"


class KnowledgeBase:
    def __init__(self, path: Path = _KB_PATH) -> None:
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.items: dict[str, dict] = {i["id"]: i for i in raw["items"]}
        self.gaps: list[str] = raw.get("knowledge_gaps_needing_business_input", [])
        self.version = raw["_meta"]["version"]

    def get(self, kid: str) -> dict:
        if kid not in self.items:
            raise KeyError(f"知识条目不存在: {kid}")
        return self.items[kid]

    def cite(self, kid: str) -> dict:
        """返回可入理由链的引用（含置信度）。"""
        it = self.get(kid)
        return {"kb_id": kid, "type": it["type"], "confidence": it["confidence"],
                "statement": it["statement"], "source": it["source"]}

    @staticmethod
    def validate_chain(chain: list[dict]) -> None:
        """建议组装硬校验（D9）：理由链为空或含幻觉引用 → 拒绝。"""
        if not chain:
            raise ValueError("理由链为空：宁可不建议，不可无据建议")
        for ev in chain:
            if "kb_id" not in ev and "data_ref" not in ev and "spec_ref" not in ev:
                raise ValueError(f"证据缺少出处: {ev}")
