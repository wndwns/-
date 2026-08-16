"""事件相似度模块的最小回归检查（无框架断言）。

运行: python backend/test_event_similarity.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from models import event_similarity_topk  # noqa: E402


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    result = event_similarity_topk(top_k=10)
    _assert(result.get("ok") is True, "应返回 ok=True")
    stats = result["stats"]
    _assert(stats["n_events_used"] > 0, "应使用至少 1 条来源支持事件")
    _assert(stats["n_samples"] > 0, "应存在县月样本")

    cands = result["candidates"]
    _assert(len(cands) == 10, f"应返回 Top10，实际 {len(cands)}")

    event_keys = set()
    labels_path = Path(__file__).resolve().parent / "data_store" / "real_labels_1500.json"
    import json
    with open(labels_path, "r", encoding="utf-8") as f:
        for rl in json.load(f):
            if rl.get("source_url"):
                event_keys.add((rl.get("region_id", ""), rl.get("month", "")))

    for c in cands:
        _assert(c.get("month"), "候选必须有月份")
        _assert(c.get("region_id"), "候选必须有 region_id")
        _assert(0.0 <= c["distance"], "距离必须非负")
        _assert(0.0 < c["similarity"] <= 1.0, "相似度必须在 (0,1]")
        _assert(bool(c["nearest_event"].get("source_url")), "最近事件必须带 source_url")
        _assert((c["region_id"], c["month"]) not in event_keys, "来源事件月份本身不得出现在候选中")

    # 结果应确定可复现
    result2 = event_similarity_topk(top_k=10)
    keys = [(c["region_id"], c["month"]) for c in cands]
    _assert(keys == [(c["region_id"], c["month"]) for c in result2["candidates"]], "结果应可复现")

    # 县域过滤应生效
    rid = cands[0]["region_id"]
    filtered = event_similarity_topk(top_k=5, region_id=rid)
    _assert(all(c["region_id"] == rid for c in filtered["candidates"]), "region_id 过滤应生效")
    _assert(len(filtered["candidates"]) <= 5, "top_k 应生效")

    print("event_similarity: OK")


if __name__ == "__main__":
    main()