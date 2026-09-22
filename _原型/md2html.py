#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极简 Markdown → 单文件 HTML 转换器（零依赖）

用途：把项目里的 md 方案文档转成排版好的 HTML（侧边目录 + 卡片 + 表格样式）。

设计取舍：
  - 不用第三方 markdown 库（本机没装，也不想为此装包），自己写最小解析。
  - 只支持本项目文档实际用到的语法：H1-H4 / 表格 / 代码围栏 / 引用块 / 有序无序列表 /
    **粗体** / `行内代码` / 水平线。
  - 引用块里若含 ⚠️ 或「已更正 / 降级 / 修订」等词，渲染成醒目的警示卡。

用法：
  python md2html.py 输入.md 输出.html "文档标题" "副标题"
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 行内元素
# --------------------------------------------------------------------------

def inline(text: str) -> str:
    """处理行内标记。先转义，再替换标记，避免把标签转义掉。"""
    out = html.escape(text, quote=False)
    # 行内代码（先处理，避免其中的 ** 被误判）
    code_slots: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        code_slots.append(m.group(1))
        return f"\x00{len(code_slots) - 1}\x00"

    out = re.sub(r"`([^`]+)`", _stash, out)
    # 粗体
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    # 斜体（单星号，且不与粗体冲突）
    out = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", out)
    # 还原行内代码
    for i, code in enumerate(code_slots):
        out = out.replace(f"\x00{i}\x00", f"<code>{code}</code>")
    return out


def slug(text: str, used: dict[str, int]) -> str:
    """从标题文字生成唯一锚点。"""
    base = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-").lower() or "sec"
    n = used.get(base, 0)
    used[base] = n + 1
    return base if n == 0 else f"{base}-{n}"


WARN_WORDS = ("⚠️", "已更正", "更正", "降级", "修订", "本条已在")


def is_warning(text: str) -> bool:
    return any(w in text for w in WARN_WORDS)


# --------------------------------------------------------------------------
# 块级解析
# --------------------------------------------------------------------------

def convert(md: str, title: str, subtitle: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = md.splitlines()
    body: list[str] = []
    toc: list[tuple[int, str, str]] = []
    used: dict[str, int] = {}

    i = 0
    n = len(lines)
    first_h1_seen = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # --- 代码围栏 ---
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            block: list[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1  # 跳过结束围栏
            code = html.escape("\n".join(block))
            cls = f' class="lang-{lang}"' if lang else ""
            body.append(f"<pre><code{cls}>{code}</code></pre>")
            continue

        # --- 水平线 ---
        if stripped in ("---", "***", "___"):
            body.append('<div class="hr"></div>')
            i += 1
            continue

        # --- 标题 ---
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                if not first_h1_seen:
                    # 文档首个 H1 由页面标题区承担，跳过
                    first_h1_seen = True
                    i += 1
                    continue
                # 后续 H1 当作 H2 用（本文件里 H1 是「第 N 章」级别）
                level = 2
            anchor = slug(text, used)
            plain = re.sub(r"[*`]", "", text)
            toc.append((level, anchor, plain))
            tag = f"h{level}"
            cls = ' class="anchored"' if level >= 3 else ""
            body.append(f'<{tag} id="{anchor}"{cls}>{inline(text)}</{tag}>')
            i += 1
            continue

        # --- 表格 ---
        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            head_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows: list[list[str]] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{inline(c)}</th>" for c in head_cells)
            tbody = "".join(
                "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows
            )
            body.append(f'<div class="tw"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue

        # --- 引用块（连续行合并） ---
        if stripped.startswith(">"):
            buf: list[str] = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            text = "\n".join(buf).strip()
            if text:
                cls = "callout warn" if is_warning(text) else "callout"
                paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
                inner = "".join(f"<p>{inline(p)}</p>" for p in paras)
                body.append(f'<div class="{cls}">{inner}</div>')
            continue

        # --- 列表 ---
        if re.match(r"^\s*([-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            items: list[str] = []
            while i < n and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                content = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i])
                # 续行（缩进且有内容）
                i += 1
                while i < n and lines[i].startswith(("  ", "\t")) and lines[i].strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    content += " " + lines[i].strip()
                    i += 1
                items.append(f"<li>{inline(content.strip())}</li>")
            tag = "ol" if ordered else "ul"
            body.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue

        # --- 空行 ---
        if not stripped:
            i += 1
            continue

        # --- 段落（合并连续非空行） ---
        buf = [stripped]
        i += 1
        while i < n and lines[i].strip() and not re.match(
            r"^(#{1,4}\s|\||```|>|\s*([-*]|\d+\.)\s|---$|===)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        body.append(f"<p>{inline(' '.join(buf))}</p>")

    return "\n".join(body), toc


# --------------------------------------------------------------------------
# 页面模板
# --------------------------------------------------------------------------

TPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  :root{{
    --red:#C7000B; --red-bg:#FFF5F4; --red-soft:#FFE8E5;
    --ink:#1A1D21; --ink2:#4A5158; --ink3:#8A9099;
    --line:#E6E8EB; --line2:#F0F2F4; --bg:#F7F8FA; --card:#FFFFFF;
    --ok:#12885A; --ok-bg:#EAF7F1; --warn:#B76B12; --warn-bg:#FDF4E7;
  }}
  body{{font-family:"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
    background:var(--bg);color:var(--ink);font-size:14.5px;line-height:1.78;
    -webkit-font-smoothing:antialiased;}}
  .wrap{{display:flex;max-width:1400px;margin:0 auto;}}

  aside{{width:268px;flex:0 0 268px;position:sticky;top:0;height:100vh;
    padding:28px 16px 28px 24px;overflow-y:auto;}}
  aside .logo{{font-size:15px;font-weight:700;margin-bottom:4px;}}
  aside .logo span{{color:var(--red);}}
  aside .tagline{{font-size:11px;color:var(--ink3);margin-bottom:18px;}}
  aside .bt{{font-size:11px;color:var(--ink3);letter-spacing:1.5px;margin:16px 0 6px;}}
  aside a{{display:block;padding:5px 10px;font-size:13px;color:var(--ink2);
    text-decoration:none;border-radius:6px;border-left:2px solid transparent;
    line-height:1.5;}}
  aside a:hover{{background:#EFF1F4;color:var(--ink);}}
  aside a.lv2{{font-weight:600;color:var(--ink);margin-top:4px;}}
  aside a.lv3{{padding-left:22px;font-size:12.5px;}}
  aside a.lv4{{padding-left:34px;font-size:12px;color:var(--ink3);}}

  main{{flex:1;min-width:0;padding:34px 52px 100px;}}

  .head{{margin-bottom:32px;padding-bottom:24px;border-bottom:1px solid var(--line);}}
  .head h1{{font-size:29px;font-weight:700;letter-spacing:-.5px;line-height:1.32;}}
  .head h1 span{{color:var(--red);}}
  .head .sub{{font-size:14.5px;color:var(--ink2);margin-top:8px;}}

  h2{{font-size:20px;font-weight:700;margin:46px 0 16px;padding-top:6px;
    scroll-margin-top:20px;border-top:1px solid var(--line);padding-top:22px;}}
  h2:first-of-type{{border-top:0;padding-top:0;margin-top:30px;}}
  h3{{font-size:16.5px;font-weight:600;margin:30px 0 10px;scroll-margin-top:20px;}}
  h4{{font-size:14.5px;font-weight:600;margin:20px 0 8px;color:var(--ink2);scroll-margin-top:20px;}}

  p{{margin-bottom:12px;}}
  strong{{font-weight:600;}}
  code{{font-family:Consolas,Monaco,monospace;font-size:.9em;background:#F2F4F6;
    padding:1.5px 5px;border-radius:4px;color:#A8332B;}}
  pre{{background:#F8F9FB;border:1px solid var(--line);border-radius:8px;
    padding:14px 18px;margin:14px 0;overflow-x:auto;}}
  pre code{{background:none;padding:0;color:var(--ink2);font-size:12.8px;line-height:1.7;}}

  ul,ol{{margin:12px 0 14px;padding-left:24px;}}
  li{{margin-bottom:6px;}}

  .tw{{overflow-x:auto;margin:14px 0;border:1px solid var(--line);border-radius:10px;background:var(--card);}}
  table{{width:100%;border-collapse:separate;border-spacing:0;font-size:13.5px;}}
  th{{text-align:left;padding:10px 14px;background:#F4F6F8;color:var(--ink2);
    font-weight:600;font-size:12.5px;white-space:nowrap;border-bottom:1px solid var(--line);}}
  td{{padding:11px 14px;border-bottom:1px solid var(--line2);vertical-align:top;}}
  tr:last-child td{{border-bottom:0;}}
  tbody tr:hover td{{background:#FBFCFD;}}

  .callout{{background:var(--red-bg);border-left:4px solid var(--red);border-radius:0 8px 8px 0;
    padding:14px 20px;margin:16px 0;font-size:14px;}}
  .callout p{{margin:0 0 8px;}}
  .callout p:last-child{{margin-bottom:0;}}
  .callout.warn{{background:var(--warn-bg);border-left-color:var(--warn);}}

  .hr{{height:1px;background:var(--line);margin:38px 0;}}

  @media print{{
    body{{background:#fff;font-size:10.5pt;}}
    aside{{display:none;}}
    .wrap{{display:block;max-width:none;}}
    main{{padding:0;}}
    h2,h3,h4{{break-after:avoid;}}
    .tw,.callout,pre{{break-inside:avoid;}}
    @page{{margin:16mm 14mm;}}
  }}
  @media (max-width:980px){{
    aside{{display:none;}}
    main{{padding:22px 18px 60px;}}
    .head h1{{font-size:23px;}}
  }}
</style>
</head>
<body>
<div class="wrap">
<aside>
  <div class="logo">工银<span>牧融</span></div>
  <div class="tagline">{tagline}</div>
  <div class="bt">目录</div>
  {toc}
</aside>
<main>
  <div class="head">
    <h1>{title_html}</h1>
    <div class="sub">{subtitle}</div>
  </div>
  {body}
</main>
</div>
</body>
</html>
"""


def build_toc(toc: list[tuple[int, str, str]]) -> str:
    parts = []
    for level, anchor, text in toc:
        if level > 4:
            continue
        parts.append(f'<a class="lv{level}" href="#{anchor}">{html.escape(text)}</a>')
    return "\n  ".join(parts)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    title = sys.argv[3] if len(sys.argv) > 3 else src.stem
    subtitle = sys.argv[4] if len(sys.argv) > 4 else ""

    md = src.read_text(encoding="utf-8")
    body, toc = convert(md, title, subtitle)

    # 标题里把项目名高亮
    title_html = html.escape(title)
    if "工银牧融" in title_html:
        title_html = title_html.replace("工银牧融", '工银<span>牧融</span>')

    out = TPL.format(
        title=html.escape(title),
        title_html=title_html,
        subtitle=html.escape(subtitle),
        tagline=html.escape(subtitle[:20]) if subtitle else "",
        toc=build_toc(toc),
        body=body,
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8", newline="\n")
    print(f"OK  {src.name}  ->  {dst}")
    print(f"    标题层级 {len(toc)} 个 · 输出 {len(out):,} 字符")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
