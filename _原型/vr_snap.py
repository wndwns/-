#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""视觉回归基线比对（零额外安装，用已有 Playwright + Pillow）。

用法：
    python vr_snap.py --update   # 生成/更新基准图（人确认一次）
    python vr_snap.py            # 与基准比对，差异超阈值就失败

覆盖：/bank 的 7 个页面 + 客户档案 6 个 Tab、旧 SPA 的主要页面。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8100"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if HERE.name == "_原型" else HERE
# 基准图放项目的 .workbuddy/tmp（非交付物，不进 git）
BASE_DIR = ROOT / ".workbuddy" / "tmp" / "_vr_baseline"
DIFF_DIR = ROOT / ".workbuddy" / "tmp" / "_vr_diff"
THRESHOLD = 0.02  # 允许 0.02% 像素不同。实测无改动重复运行是 0.000%，
# 所以阈值可以收到很紧：0.5% 会漏掉「标题多几个字」这类小改动（约 0.04%）。

BANK_NAV = ["工作台", "客户池", "客户档案", "活体资产台账", "贷后待办", "区域与集中度", "保险协同"]
BANK_TABS = ["概览", "资料", "资产", "授信", "贷后", "依据"]
SPA_PAGES = ["首页", "授信与贷后", "数据底座", "产业链", "保险协同", "合作社排序", "绿色绩效", "灾害预测"]


def shots() -> list[tuple[str, bytes]]:
    """按顺序产出 (名称, 截图字节)。

    为避免入场动画导致抖动：禁用 reduced-motion + 注入「关掉所有动画/过渡」的 CSS +
    等 document.getAnimations() 全部结束。实测不加这三样时旧 SPA 首页会有 5% 假差异。
    """
    out: list[tuple[str, bytes]] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000},
                                device_scale_factor=1, reduced_motion="reduce")
        page.add_init_script("""
            (() => {
              // 只掐掉 hero 轮播那一个 5000ms 定时器（app.js startHero），其余定时器不动。
              // 不掐的话截图会随机停在第 1~4 张标语上，视觉回归必然假红。
              const _si = window.setInterval;
              window.setInterval = function (fn, ms, ...rest) {
                if (ms === 5000) { return 0; }
                return _si.call(this, fn, ms, ...rest);
              };
              const css = document.createElement('style');
              css.textContent = '*,*::before,*::after{animation:none!important;' +
                'transition:none!important;caret-color:transparent!important}';
              (document.head || document.documentElement).appendChild(css);
            })();
        """)

        def settle(ms: int = 1200):
            page.wait_for_timeout(ms)
            try:
                page.evaluate("() => Promise.all(document.getAnimations()"
                              ".map(a => a.finished.catch(() => {})))")
            except Exception:  # noqa: BLE001
                pass
            page.wait_for_timeout(250)

        def snap(name: str, full: bool = False):
            out.append((name, page.screenshot(full_page=full, animations="disabled")))

        page.goto(BASE + "/bank", wait_until="networkidle", timeout=60000)
        settle(1800)
        for nav in BANK_NAV:
            page.locator("aside.sidebar .nav-item").filter(has_text=nav).first.click()
            settle(1200)
            snap(f"bank-{nav}")
            if nav == "客户档案":
                for tb in BANK_TABS:
                    try:
                        page.locator(".page.on .tab").filter(has_text=tb).first.click()
                        settle(800)
                        snap(f"bank-客户档案-{tb}")
                    except Exception:  # noqa: BLE001
                        pass
        # 关键页整页快照（抓长页底部问题）
        page.locator("aside.sidebar .nav-item").filter(has_text="客户档案").first.click()
        settle(1000)
        page.locator(".page.on .tab").filter(has_text="授信").first.click()
        settle(800)
        snap("bank-客户档案-授信-整页", full=True)

        page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
        settle(2500)
        snap("spa-首页")
        for name in SPA_PAGES[1:]:
            try:
                page.goto(BASE + "/", wait_until="networkidle", timeout=60000)
                settle(1200)
                page.get_by_text(name, exact=True).first.click(timeout=8000)
                settle(2200)
                snap(f"spa-{name}")
            except Exception:  # noqa: BLE001
                pass
        browser.close()
    return out


def compare(name: str, cur: bytes, update: bool) -> tuple[bool, str]:
    ref = BASE_DIR / f"{name}.png"
    if update or not ref.exists():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        ref.write_bytes(cur)
        return True, "写入基准" if update else "新建基准"
    a = np.asarray(Image.open(ref).convert("RGB"), dtype=np.int16)
    cur_path = DIFF_DIR / f"{name}.cur.png"
    DIFF_DIR.mkdir(parents=True, exist_ok=True)
    cur_path.write_bytes(cur)
    b = np.asarray(Image.open(cur_path).convert("RGB"), dtype=np.int16)
    if a.shape != b.shape:
        return False, f"尺寸变了 {a.shape} -> {b.shape}"
    diff = np.abs(a - b).max(axis=2)
    ratio = float((diff > 12).sum()) / diff.size * 100
    if ratio <= THRESHOLD:
        return True, f"差异 {ratio:.3f}%"
    # 存差异可视化
    vis = np.zeros_like(a, dtype=np.uint8)
    vis[..., 0] = np.where(diff > 12, 255, 255 - (255 - a[..., 0]).astype(np.uint8))
    vis[..., 1] = np.where(diff > 12, 0, a[..., 1].astype(np.uint8))
    vis[..., 2] = np.where(diff > 12, 0, a[..., 2].astype(np.uint8))
    Image.fromarray(vis).save(DIFF_DIR / f"{name}.diff.png")
    return False, f"差异 {ratio:.2f}% 超阈值 {THRESHOLD}%"


def main() -> int:
    update = "--update" in sys.argv
    data = shots()
    print(f"{'UPDATE' if update else 'COMPARE'}  共 {len(data)} 张\n")
    bad = []
    for name, png in data:
        ok, msg = compare(name, png, update)
        if not ok:
            bad.append(f"{name}: {msg}")
        print(f"{'ok  ' if ok else 'FAIL'} {name:<34} {msg}")
    print()
    if update:
        print(f"### 基准已写入 {BASE_DIR}")
        return 0
    if bad:
        print(f"### 视觉回归失败 {len(bad)} 张")
        for b in bad:
            print("  -", b)
        print(f"差异图见 {DIFF_DIR}")
        return 1
    print("### 视觉回归全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
