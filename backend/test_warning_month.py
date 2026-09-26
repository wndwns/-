"""
工银牧融 - 预警取数口径回归（early_warning）
============================================================================
运行：
    python backend\\test_warning_month.py        （零依赖自跑，不联网）
或：
    python -m pytest backend/test_warning_month.py -q

为什么需要它：
    2026-09-26 发现 `early_warning` 有**三处静默失效**，此前完全没有测试覆盖：

    1. 县坐标表路径写成 backend/public_data/，而文件在项目根 → 坐标表恒空 →
       26 个县全都查同一个坐标（结果恒等，页面看不出错）。
    2. 雪深预报用了 daily=snow_depth —— 该变量在 daily 里不存在 → HTTP 400 →
       每次都静默落到 ERA5 温度代理降级（不报错、不留痕）。
    3. 上面那条即使成功，单位也是反的：API 自报 snow_depth_max 单位是**米**，
       原代码却在 ÷100。

    再叠加 4：旱灾 SPI 用系统当前月当目标月，数据滞后时该月无记录，
    monthly_precip.get(k, 0) 静默按 0 降水算 → 26 个县 SPI 全在 -12 ~ -3，
    集体误报「严重干旱」→ 26/26 县顶成高风险。

    这几处的共同点是：**不抛异常、不报错，只是安静地给出错误结论**。
    所以本文件全部断言「口径本身」而非「某个具体数值」。

不变量：
    W1  latest_climate_month 返回的月份必须真实存在于该县气候数据里
    W2  默认目标月下，SPI-3 窗口的 3 个月在数据里都有记录（缺一月即被当 0 降水）
    W3  26 县默认累计降水不全为 0（即没有整体走「缺失按 0」这条路）
    W4  26 县的干旱等级不能全部相同（区分度必须存在）
    W5  显式传入不同月份会改变结果（证明参数真的生效、不是被忽略）
    W6  _county_coords 非空，且各县坐标互不相同（防第 1 处退化）
    W7  雪深预报请求用的是合法 daily 变量，且米→厘米换算方向正确（防第 2、3 处）
"""

from __future__ import annotations

import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import early_warning as ew  # noqa: E402

WAN = 10000


def _regions() -> list[str]:
    return sorted(ew._county_coords().keys())


def _climate_months(region_id: str) -> set[str]:
    records = ew._load_climate().get(region_id) or []
    return {r["date"][:7] for r in records if r.get("date")}


# ---------------------------------------------------------------------------
# W1 / W2 —— 目标月必须落在数据范围内
# ---------------------------------------------------------------------------
def test_w1_latest_month_exists_in_data() -> None:
    for rid in _regions():
        m = ew.latest_climate_month(rid)
        assert len(m) == 7 and m[4] == "-", f"{rid}: 月份格式不对 {m!r}"
        assert m in _climate_months(rid), f"{rid}: 返回的 {m} 不在该县数据里"


def test_w2_default_window_has_no_missing_month() -> None:
    """SPI-3 的 3 个月窗口必须都有记录，否则缺失月会被静默当作 0 降水。"""
    for rid in _regions():
        target = ew.latest_climate_month(rid)
        y, m = int(target[:4]), int(target[5:7])
        window = []
        for i in range(3):
            cm, cy = m - i, y
            if cm <= 0:
                cm += 12
                cy -= 1
            window.append(f"{cy}-{cm:02d}")
        have = _climate_months(rid)
        missing = [w for w in window if w not in have]
        assert not missing, f"{rid}: 目标月 {target} 的窗口缺 {missing}（会被当 0 降水）"


def test_w2b_compute_spi_default_uses_latest_month() -> None:
    for rid in _regions():
        r = ew.compute_spi(rid)
        assert r["target_month"] == ew.latest_climate_month(rid), \
            f"{rid}: compute_spi 默认月 {r['target_month']} != latest_climate_month"


# ---------------------------------------------------------------------------
# W3 / W4 —— 26 县不能整体退化成同一个结论
# ---------------------------------------------------------------------------
def test_w3_not_all_zero_precip() -> None:
    """整体走「缺失按 0」的典型症状：所有县当月累计降水都是 0。"""
    zeros = [rid for rid in _regions() if not ew.compute_spi(rid).get("current_cum_precip_mm")]
    total = len(_regions())
    assert len(zeros) < total, f"全部 {total} 个县累计降水都是 0，疑似缺失被当 0 处理"


def test_w4_drought_levels_are_discriminated() -> None:
    """26 个县全部落到同一个等级 = 信号失去区分度（2026-09-26 实测全为「严重干旱」）。"""
    levels = {}
    for rid in _regions():
        lv = ew.compute_spi(rid).get("drought_level")
        levels[lv] = levels.get(lv, 0) + 1
    assert len(levels) > 1, f"26 县旱情等级完全相同：{levels}"


# ---------------------------------------------------------------------------
# W5 —— 参数真的生效（防止「默认值写死、参数被忽略」）
# ---------------------------------------------------------------------------
def test_w5_explicit_month_changes_result() -> None:
    """对照月取「去年同月」：既有足够历史样本，又不至于落到「数据不足」分支。"""
    rid = _regions()[0]
    default = ew.compute_spi(rid)
    target = default["target_month"]
    other = f"{int(target[:4]) - 1}-{target[5:7]}"
    assert other in _climate_months(rid), f"对照月 {other} 不在数据里"
    alt = ew.compute_spi(rid, other)
    assert alt["target_month"] == other, "显式传入的月份被忽略了"
    assert "current_cum_precip_mm" in alt, \
        f"对照月走了非正常分支：{alt.get('status') or alt}"
    assert (alt["spi"], alt["current_cum_precip_mm"]) != \
           (default["spi"], default["current_cum_precip_mm"]), \
        "换月份结果不变，参数可能没被真正使用"


# ---------------------------------------------------------------------------
# W6 —— 坐标表（防静默退化成单点）
# ---------------------------------------------------------------------------
def test_w6_county_coords_present_and_distinct() -> None:
    coords = ew._county_coords()
    assert coords, "坐标表为空 —— 所有县会退回同一默认坐标"
    distinct = {(round(v["lat"], 3), round(v["lon"], 3)) for v in coords.values()}
    assert len(distinct) > 1, f"{len(coords)} 个县只有 {len(distinct)} 组坐标，疑似共用同一点"


# ---------------------------------------------------------------------------
# W7 —— 雪深预报的变量名与单位（离线拦截 HTTP 层）
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def read(self) -> bytes:
        return self._payload


def test_w7_snow_request_uses_valid_variables_and_unit() -> None:
    """钉住两件事：daily 变量名合法（否则 400 静默降级）、米→厘米是 ×100。"""
    payload = [
        {"daily": {"time": ["2026-09-27", "2026-09-28"],
                   "snow_depth_max": [0.333, 0.0],
                   "snowfall_sum": [1.5, 0.0]}},
        {"daily": {"time": ["2026-09-27", "2026-09-28"],
                   "snow_depth_max": [0.0, 0.05],
                   "snowfall_sum": [0.0, 2.0]}},
    ]
    captured: dict[str, str] = {}

    class _FakeOpener:
        def open(self, req, timeout=None):  # noqa: ANN001, ANN201
            captured["url"] = req.full_url
            return _FakeResponse(json.dumps(payload).encode("utf-8"))

    orig = urllib.request.build_opener
    urllib.request.build_opener = lambda *a, **k: _FakeOpener()  # type: ignore[assignment]
    try:
        got = ew._fetch_snow_forecast(["naqu-bange", "linzhi-bayi"])
    finally:
        urllib.request.build_opener = orig  # type: ignore[assignment]

    url = captured.get("url", "")
    assert "daily=snow_depth_max" in url, f"请求变量名不对：{url}"
    assert "daily=snow_depth," not in url and not url.endswith("daily=snow_depth"), \
        f"又用回了 daily 里不存在的 snow_depth：{url}"

    rows = got.get("naqu-bange") or []
    assert rows, "两个县都没解析出结果"
    assert rows[0]["snow_depth_cm"] == 33.3, \
        f"米→厘米换算方向可疑：0.333 米 得到 {rows[0]['snow_depth_cm']}"
    assert rows[0]["snowfall_cm"] == 1.5, "降雪本身单位就是厘米，不该再换算"


# ---------------------------------------------------------------------------
# W8 / W9 —— 目标月必须与当前日历月对齐（避开冬季分母退化）
# ---------------------------------------------------------------------------
def test_w8_default_month_aligns_with_current_calendar_month() -> None:
    """直接钉住设计决定：取「与当前月相同的最近一年」，不是「数据里最后一个月」。

    改成取最后一个月会踩冬季数值退化 —— 见 W9 的实测数字。
    """
    cur_month = date.today().strftime("%m")
    for rid in _regions():
        have = _climate_months(rid)
        same = sorted(m for m in have if m[5:7] == cur_month)
        if not same:
            continue  # 该县数据里没有当前日历月，退回「最新月」是允许的
        assert ew.latest_climate_month(rid) == same[-1], (
            f"{rid}: 期望 {same[-1]}（与当前月 {cur_month} 相同的最近一年），"
            f"实际 {ew.latest_climate_month(rid)}"
        )


def test_w9_spi_magnitude_within_interpretable_range() -> None:
    """SPI 超过 5 个标准差 = 历史标准差退化，结论不可解读。

    实测（2026-09-26）：
      - 目标月 2025-09 -> |SPI| 最大 2.05，历史标准差最小 32.4mm，全部可解读
      - 目标月 2025-12 -> 谢通门 std=2.5mm / 均值 4.6mm（分母趋零）-> SPI = +14.82
        「严重洪涝」；红原 SPI = -4.07
    高原冬季降水趋近 0，标准差随之塌陷，Z-score 版本会放大成无意义量级。
    """
    offenders = []
    for rid in _regions():
        x = ew.compute_spi(rid)
        std = x.get("historical_std_mm")
        spi = x.get("spi")
        assert std is not None and std > 0, f"{rid}: 历史标准差异常 {std}"
        assert spi is not None, f"{rid}: 目标月 {x.get('target_month')} 未算出 SPI"
        if abs(spi) > 5:
            offenders.append((rid, std, x.get("historical_mean_mm"), spi))
    assert not offenders, f"SPI 超出可解读区间（疑似标准差退化）：{offenders}"


def _run_standalone() -> int:
    checks = [
        test_w1_latest_month_exists_in_data,
        test_w2_default_window_has_no_missing_month,
        test_w2b_compute_spi_default_uses_latest_month,
        test_w3_not_all_zero_precip,
        test_w4_drought_levels_are_discriminated,
        test_w5_explicit_month_changes_result,
        test_w6_county_coords_present_and_distinct,
        test_w7_snow_request_uses_valid_variables_and_unit,
        test_w8_default_month_aligns_with_current_calendar_month,
        test_w9_spi_magnitude_within_interpretable_range,
    ]
    failed = 0
    for fn in checks:
        try:
            fn()
            print(f"ok    {fn.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}\n      {str(exc)[:500]}")
    print()
    if failed:
        print(f"{len(checks) - failed}/{len(checks)} passed（{failed} 条不变量被推翻）")
        return 1
    print(f"{len(checks)}/{len(checks)} 条口径不变量全部成立")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
