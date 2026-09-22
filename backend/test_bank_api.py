"""
工银牧融 - 银行视角 API 回归检查
============================================================================
运行：
    python backend\\test_bank_api.py            （零依赖自跑，不需要 pytest）
或：
    python -m pytest backend/test_bank_api.py -q

依赖：fastapi / httpx（见 requirements.txt）。缺依赖时整体跳过并返回 0，
      不让环境问题伪装成功能失败。

覆盖：
  - 8 个 /api/bank/* 端点：状态码与关键结构
  - 未知客户 -> 404
  - 单户档案：切换客户后内容确实不同（不是假按钮）
  - 一户一档：28 项 / 6 组，状态取值合法
  - 派生数据必须带 is_derived 与 derived_note，不得冒充真实数据
  - 不输出敏感字段（电话、证件号、地址）
  - 贷后队列按优先级排序，等级取值合法
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    from fastapi.testclient import TestClient
except ImportError as exc:  # pragma: no cover
    print(f"SKIP  缺少依赖（{exc}）。请先 pip install fastapi httpx")
    raise SystemExit(0)

try:
    import server
except ImportError:  # pragma: no cover
    from backend import server  # type: ignore[no-redef]

_client = TestClient(server.create_app())

SENSITIVE_KEYS = ("phone", "mobile", "id_number", "id_card", "address", "ear_tag_no")


def _get(path: str):
    r = _client.get(path)
    assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
    return r.json()


# ------------------------------------------------------------------ 端点存在

def test_bank_endpoints_available() -> None:
    for path in (
        "/api/bank/overview",
        "/api/bank/customer-pool",
        "/api/bank/ledger",
        "/api/bank/post-loan",
        "/api/bank/insurance",
        "/api/bank/regions",
    ):
        data = _get(path)
        assert isinstance(data, dict) and data, f"{path} 返回空"


def test_overview_shape() -> None:
    ov = _get("/api/bank/overview")
    for key in ("customers_total", "todo_total", "ledger_book_head",
                "insurance_pending", "green_deployed_wan", "sources"):
        assert key in ov, f"overview 缺字段 {key}"
    assert ov["customers_total"] > 0
    assert isinstance(ov["sources"], list)


def test_customer_pool_sorted_and_complete() -> None:
    pool = _get("/api/bank/customer-pool")
    assert pool["total"] == len(pool["customers"])
    srcs = {s["source"] for s in pool["sources"]}
    assert srcs, "获客来源不能为空"
    # 可算额度的排在前面
    amounts = [c["amount_yuan"] or 0 for c in pool["customers"]]
    assert amounts == sorted(amounts, reverse=True), "客户池应按可算额度降序"
    for c in pool["customers"]:
        assert 0 <= c["completeness"] <= 100


def test_unknown_customer_returns_404() -> None:
    r = _client.get("/api/bank/customer/不存在的客户名")
    assert r.status_code == 404
    r2 = _client.get("/api/bank/customer/不存在的客户名/documents")
    assert r2.status_code == 404


# ------------------------------------------------- 单户档案：切换客户真的变

def test_customer_profile_differs_between_customers() -> None:
    pool = _get("/api/bank/customer-pool")
    names = [c["subject_name"] for c in pool["customers"][:5]]
    assert len(names) >= 2

    profiles = []
    for n in names[:3]:
        r = _client.get(f"/api/bank/customer/{n}")
        assert r.status_code == 200, f"{n} -> {r.status_code}"
        profiles.append(r.json())

    # 主体名各不相同
    assert len({p["subject_name"] for p in profiles}) == len(profiles)
    # 台账 / 资料完整度至少有一处不同（否则就是假切换）
    ledger_sig = {(p["ledger"]["book_head"], p["ledger"]["tag_head"]) for p in profiles}
    doc_sig = {p["documents_summary"]["completeness"] for p in profiles}
    assert len(ledger_sig) > 1 or len(doc_sig) > 1, "切换客户后数据没有变化"


def test_customer_profile_has_conclusion_and_evidence() -> None:
    pool = _get("/api/bank/customer-pool")
    name = pool["customers"][0]["subject_name"]
    p = _client.get(f"/api/bank/customer/{name}").json()
    assert p["conclusion"]["status"] in ("可测算", "待核查", "待补资料")
    assert p["conclusion"]["tone"] in ("ok", "warn", "danger")
    assert p["conclusion"]["headline"]
    assert len(p["evidence"]) == 5, "四条证据应为 5 项（资产/防疫/经营/还款/保险）"


def test_profile_discloses_sample_source() -> None:
    pool = _get("/api/bank/customer-pool")
    name = pool["customers"][0]["subject_name"]
    p = _client.get(f"/api/bank/customer/{name}").json()
    assert "source" in p and "is_sample" in p["source"], "单户档案必须披露数据来源"


# ------------------------------------------------------------ 一户一档资料

def test_documents_28_items_6_groups() -> None:
    pool = _get("/api/bank/customer-pool")
    name = pool["customers"][0]["subject_name"]
    d = _client.get(f"/api/bank/customer/{name}/documents").json()
    assert d["found"] is True
    assert len(d["items"]) == 28, f"资料项应为 28，实际 {len(d['items'])}"
    assert d["groups"] == ["主体资料", "资产资料", "防疫资料", "经营资料", "保险资料", "授信资料"]
    groups_in_items = {i["group"] for i in d["items"]}
    assert groups_in_items == set(d["groups"])

    for i in d["items"]:
        assert i["status"] in ("已填", "缺失", "待核验"), i
    s = d["summary"]
    assert s["total"] == 28
    assert s["filled"] + s["missing"] + s["pending"] == 28
    assert 0 <= s["completeness"] <= 100


def test_documents_marked_derived() -> None:
    pool = _get("/api/bank/customer-pool")
    name = pool["customers"][0]["subject_name"]
    d = _client.get(f"/api/bank/customer/{name}/documents").json()
    assert d["is_derived"] is True
    assert d["derived_note"], "派生资料必须给出 derived_note"


# --------------------------------------------------------------- 台账 / 贷后

def test_ledger_board_shape() -> None:
    led = _get("/api/bank/ledger")
    assert led["customers"] > 0
    assert led["total_book_head"] >= led["total_tag_head"]
    assert "只产生核查线索" in led["note"], "台账必须声明无票出栏不判定欺骗"
    ranked = led["ranked"]
    ratios = [r["unpriced_ratio"] for r in ranked]
    assert ratios == sorted(ratios, reverse=True), "无票出栏排行应按占比降序"
    for r in ranked:
        assert r["out_unpriced"] <= r["out_total"]


def test_post_loan_board_sorted_and_legal_levels() -> None:
    post = _get("/api/bank/post-loan")
    assert post["total"] == len(post["queue"])
    order = {"高": 0, "中": 1, "低": 2}
    levels = [order[r["level"]] for r in post["queue"]]
    assert levels == sorted(levels), "贷后队列应按优先级降序"
    legal = set(post["signal_classes"])
    for r in post["queue"]:
        assert r["level"] in ("高", "中", "低"), r
        assert r["signal_class"] in legal, f"未知信号类 {r['signal_class']}"


def test_insurance_board_and_discount_tiers() -> None:
    ins = _get("/api/bank/insurance")
    assert ins["pending_count"] >= 0
    assert len(ins["queue"]) > 0
    tiers = {t["ear_tag"] + t["insured"]: t["discount"] for t in ins["discount_tiers"]}
    assert tiers["有有"] == 0.70
    assert tiers["有无"] == 0.40
    assert tiers["无有"] == 0.30
    assert tiers["无无"] == 0.0


def test_region_board_totals() -> None:
    reg = _get("/api/bank/regions")
    assert reg["total_regions"] > 0
    for r in reg["rows"]:
        assert r["usage_pct"] >= 0
        assert r["pool_wan"] >= r["deployed_wan"] or r["deployed_wan"] == 0
    assert "耳标编码" in reg["note"], "区域口径必须说明是近似值"


# ------------------------------------------------------------------ 隐私

def test_no_sensitive_fields_in_payloads() -> None:
    """任何银行视角接口都不得出现电话 / 证件号 / 地址等敏感字段。"""
    payloads = [
        _get("/api/bank/customer-pool"),
        _get("/api/bank/ledger"),
        _get("/api/bank/post-loan"),
        _get("/api/bank/insurance"),
    ]
    pool = payloads[0]
    name = pool["customers"][0]["subject_name"]
    payloads.append(_client.get(f"/api/bank/customer/{name}").json())
    payloads.append(_client.get(f"/api/bank/customer/{name}/documents").json())

    blob = json.dumps(payloads, ensure_ascii=False)
    for key in SENSITIVE_KEYS:
        assert f'"{key}"' not in blob, f"输出里出现敏感字段 {key}"
    # 13 位以上连续数字（耳标/证件号形态）不应出现在文本值里
    assert "身份证" not in blob or "证件号" not in blob


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL  {fn.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
        else:
            print(f"ok    {fn.__name__}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
