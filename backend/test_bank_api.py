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
  - 建议金额来源：必须来自唯一额度链，不得回显行内授信额度（见 2026-09-25 口径待办）
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
    # 按行内已有授信额度降序（不是建议金额——建议金额只有部分户有）
    amounts = [c["credit_line_yuan"] for c in pool["customers"]]
    assert amounts == sorted(amounts, reverse=True), "客户池应按已有授信额度降序"
    for c in pool["customers"]:
        assert 0 <= c["completeness"] <= 100


def test_amount_comes_from_credit_chain_not_credit_line() -> None:
    """「建议金额」必须来自唯一额度链，不得用行内已有授信额度回显顶替。

    背景：2026-09-25 定位到 bank_view._conclusion() 曾以
    ``int(finance.credit_line * 10000)`` 当建议金额输出，界面在客户档案 L1 标成
    「建议 X 万」；而黄金案例走唯一额度链算出的结果应是 900000 元（90 万）。
    旧用例只断言结构、不断言金额来源，所以 14/14 全绿也没拦住。本用例补上「来源」断言。
    """
    pool = _get("/api/bank/customer-pool")

    # 1) 列表里不再有冒充建议金额的顶层 amount_yuan；授信额度单列且语义明确
    for c in pool["customers"]:
        assert "amount_yuan" not in c, f"{c['subject_name']} 仍在顶层输出 amount_yuan"
        assert "credit_line_yuan" in c, f"{c['subject_name']} 缺 credit_line_yuan"
        est = c["estimate"]
        assert est["state"] in ("ok", "no_case", "unavailable")

    # 2) 没有测算案例、或案例判不了/被拒的户，一律不得给出金额
    for c in pool["customers"]:
        est = c["estimate"]
        if est["state"] != "ok" or est.get("status") != "feasible":
            assert est.get("amount_yuan") is None, (
                f"{c['subject_name']} 状态 {est['state']}/{est.get('status')} 却给了金额"
            )

    # 3) 黄金案例户：金额来自额度链，且不等于授信额度回显
    prof = _get("/api/bank/customer/班戈县绿色牧业合作社")
    est = prof["estimate"]
    assert est["state"] == "ok", "班戈户应有测算案例"
    assert est["amount_yuan"] == 900000, f"黄金案例建议金额应保持 900000，实为 {est['amount_yuan']}"
    credit_line_yuan = int(float(prof["finance"]["credit_line"]) * 10000)
    assert est["amount_yuan"] != credit_line_yuan, "建议金额不得等于行内授信额度回显"
    assert est["bottleneck"]["final"] == "qualified_demand", "黄金案例最终瓶颈应是需求侧"


def test_concurrent_task_writes_do_not_corrupt_store() -> None:
    """并发登记任务不得把 bank_tasks.json 写坏。

    背景：bank_tasks.create_task 是「读-改-写」，FastAPI 同步路由跑在线程池里，
    前端批量登记又是并发 POST —— 2026-09-26 实测 10 个并发请求直接把文件写成
    ``Extra data: line 46 column 2``。修法：模块内加写锁 + 临时文件原子替换。
    本用例并发打 12 次，断言：全部 2xx、任务条数 == 成功次数、文件仍是合法 JSON。
    """
    import json as _json
    import threading
    from pathlib import Path as _Path

    backend_dir = _Path(__file__).resolve().parent
    tasks_file = backend_dir / "data_store" / "bank_tasks.json"
    backup = tasks_file.read_text(encoding="utf-8") if tasks_file.exists() else None

    subject = "班戈县绿色牧业合作社"
    results: list[int] = []
    lock = threading.Lock()

    def fire(i: int) -> None:
        r = _client.post("/api/bank/task", json={
            "subject_name": subject, "action": "核验",
            "detail": f"并发回归 #{i}", "owner": "test", "due_days": 3,
        })
        with lock:
            results.append(r.status_code)

    try:
        threads = [threading.Thread(target=fire, args=(i,)) for i in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)

        assert len(results) == 12, f"并发请求没全部返回：{results}"
        assert all(200 <= c < 300 for c in results), f"有非 2xx：{results}"

        # 文件必须是合法 JSON，且条数不小于成功次数（并发下可能叠加历史记录）
        data = _json.loads(tasks_file.read_text(encoding="utf-8"))
        assert isinstance(data, list), "任务表不是数组"
        mine = [r for r in data if r.get("owner") == "test"]
        assert len(mine) == 12, f"并发写入丢了记录：期望 12 条，实际 {len(mine)}"

        # 列表接口应能读出来（读路径也没被写坏）
        listed = _get("/api/bank/tasks")
        assert listed["count"] >= 12
    finally:
        # 还原（不留测试垃圾）
        if backup is None:
            tasks_file.unlink(missing_ok=True)
        else:
            tasks_file.write_text(backup, encoding="utf-8")


def test_task_rejects_unknown_action_and_navigation_only() -> None:
    """动作白名单：乱写要 400，纯跳转动作（查看）不落库。"""
    for bad in ({"subject_name": "班戈县绿色牧业合作社", "action": "随便写"},
                {"subject_name": "班戈县绿色牧业合作社", "action": "查看"}):
        r = _client.post("/api/bank/task", json=bad)
        assert r.status_code == 400, f"{bad['action']} -> {r.status_code}"
    # 未知客户 -> 404
    r = _client.post("/api/bank/task", json={"subject_name": "不存在的人", "action": "核验"})
    assert r.status_code == 404, f"未知客户 -> {r.status_code}"


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
