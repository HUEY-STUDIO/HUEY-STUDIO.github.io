#!/usr/bin/env python3
"""
HEUY.ARCHI 지면 렌더러
------------------------------------------------------------------
  python3 render.py 2026-08-17     # 해당 날짜 지면 + 사이트 갱신
  python3 render.py --all          # data/ 전체를 다시 렌더링

입력  : data/<날짜>.json   (그날의 기사 내용)
디자인: assets/style.css   (모양은 전부 여기)
출력  : issues/<날짜>.html, index.html(최신호), archive.html, issues.json

본문 문자열 안에서는 **강조** 표기를 쓰면 <b>로 변환됩니다.
표준 라이브러리만 사용합니다.
"""

import html
import json
import os
import re
import sys
from datetime import date

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
ISSUES = os.path.join(ROOT, "issues")
WEEK = ["월", "화", "수", "목", "금", "토", "일"]

CATEGORIES = ["톱기사", "제도·규제", "프로젝트", "도시재생",
              "비엔날레", "재난·유산", "국내", "수상", "단신"]


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s or ""), quote=False)


def rich(s):
    """**강조** → <b>강조</b>. 그 외 문자는 이스케이프."""
    out, last = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*", str(s or ""), re.S):
        out.append(esc(s[last:m.start()]))
        out.append("<b>" + esc(m.group(1)) + "</b>")
        last = m.end()
    out.append(esc(s[last:]))
    return "".join(out)


def paras(body, cls=""):
    if isinstance(body, str):
        body = [body]
    c = f' class="{cls}"' if cls else ""
    return "\n".join(f"      <p{c}>{rich(p)}</p>" for p in (body or []))


def thumb(img, label, extra_cls=""):
    """이미지 블록. 로드 실패 시 매체명 플레이스홀더로 대체."""
    label = esc(label or "IMAGE")
    cls = ("thumb " + extra_cls).strip()
    if not img:
        return f'<div class="{cls} noimg" data-label="{label}"></div>'
    return (
        f'<div class="{cls}" data-label="{label}">'
        f'<img src="{esc(img)}" alt="" loading="lazy" '
        f'onerror="this.parentNode.classList.add(\'noimg\')"></div>'
    )


def source(src):
    """{"outlet": "...", "links":[{"text":"...","url":"..."}]} 또는 목록."""
    if not src:
        return ""
    groups = src if isinstance(src, list) else [src]
    parts = []
    for g in groups:
        links = " · ".join(
            f'<a href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l.get("text") or "기사")}</a>'
            for l in g.get("links", [])
        )
        parts.append(f'<span class="o">{esc(g.get("outlet"))}</span> · {links}')
    return '<div class="src">' + " &nbsp;|&nbsp; ".join(parts) + "</div>"


def weekday(day):
    y, m, d = (int(x) for x in day.split("-"))
    return WEEK[date(y, m, d).weekday()]


def shell(title, body, css_prefix=""):
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" as="style" crossorigin
      href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.css">
<link rel="stylesheet" href="{css_prefix}assets/style.css">
</head>
<body>
{body}
</body>
</html>
"""


def nav(root, current):
    def mark(page):
        return ' aria-current="page"' if page == current else ""
    return f"""<div class="site-nav">
  <a class="site-nav__brand" href="{root}index.html">HEUY<span>.</span>ARCHI</a>
  <nav>
    <a href="{root}index.html"{mark("index")}>최신호</a>
    <a href="{root}archive.html"{mark("archive")}>지난호</a>
  </nav>
</div>"""


# ------------------------------------------------------------------ sections
def render_teasers(items):
    cells = "\n".join(
        f"""    <div class="teaser">
      <h4>{rich(t.get("title"))}</h4>
      <p>{rich(t.get("desc"))}</p>
      <div class="meta">{esc(t.get("label"))}</div>
    </div>"""
        for t in items[:4]
    )
    return f'  <div class="topstrip">\n{cells}\n  </div>'


def render_masthead(d):
    day = d["date"]
    y, m, dd = day.split("-")
    c = d.get("counts", {})
    cats = "".join(
        f'<span class="hi">{esc(x)}</span>' if i == 0 else f"<span>{esc(x)}</span>"
        for i, x in enumerate(d.get("categories") or CATEGORIES)
    )
    return f"""  <header class="masthead">
    <h1 class="logo">HEUY<span class="d">.</span>ARCHI</h1>
    <div class="logo-rule"></div>
    <div class="tagline">DAILY ARCHITECTURE BRIEFING</div>
    <div class="rule-thick"></div>
    <div class="catbar">{cats}</div>
    <div class="infobar">
      <span>제1면 · 종합</span>
      <span><b>{int(y)}년 {int(m)}월 {int(dd)}일</b> {weekday(day)}요일</span>
      <span>편집·제작 <b>{esc(d.get("editor", "HUEY"))}</b></span>
      <span>오늘의 기사 <b>{c.get("total", "-")}</b>건 · 해외 <b>{c.get("intl", "-")}</b> / 국내 <b>{c.get("kr", "-")}</b></span>
    </div>
  </header>"""


def render_top(d):
    t, s = d.get("top") or {}, d.get("side") or {}

    lede = rich(t.get("lede"))
    if t.get("lede_em"):
        em = rich(t["lede_em"])
        lede = lede.replace(em, f'<span class="em">{em}</span>', 1)

    cap = f'      <figcaption>{rich(t.get("caption"))}</figcaption>' if t.get("caption") else ""
    main = f"""  <div class="topblock">
    <div class="topmain">
      <div class="kicker">{esc(t.get("kicker"))}</div>
      <p class="toplede">{lede}</p>
      <figure class="topfig">
        {thumb(t.get("image"), t.get("image_label"))}
{cap}
      </figure>
      <div class="topcols">
{paras(t.get("body"))}
      </div>
      {source(t.get("source"))}
    </div>"""

    if not s:
        return main + "\n  </div>"

    facts = ""
    if s.get("facts"):
        li = "\n".join(f"        <li>{rich(f)}</li>" for f in s["facts"])
        facts = f'      <ul class="facts">\n{li}\n      </ul>'

    side = f"""
    <aside class="topside">
      <div class="sidehead">{esc(s.get("label", "실무 직결 · 제도/규제"))}</div>
      {thumb(s.get("image"), s.get("image_label"))}
      <h3>{rich(s.get("title"))}</h3>
{paras(s.get("body"))}
{facts}
{paras(s.get("body_after"))}
      {source(s.get("source"))}
    </aside>
  </div>"""
    return main + side


def render_sechead(ko, en):
    return f'  <div class="sechead"><h2>{esc(ko)}</h2><span class="en">{esc(en)}</span><span class="line"></span></div>'


def render_feature(a):
    """헤드라인 아래 이미지 좌 / 본문 우."""
    return f"""    <article>
      <div class="kicker">{esc(a.get("kicker"))}</div>
      <h3>{rich(a.get("title"))}</h3>
      <div class="feature">
        {thumb(a.get("image"), a.get("image_label"))}
        <div>
{paras(a.get("body"))}
        </div>
      </div>
      {source(a.get("source"))}
    </article>"""


def render_card(a, kr=False):
    """이미지 위 / 본문 아래. 이미지가 없으면 좌측 보더 텍스트 카드."""
    has_img = bool(a.get("image"))
    cls = "" if has_img else ' class="kr-side"' if kr else ""
    img = f"      {thumb(a.get('image'), a.get('image_label'))}\n" if has_img else ""
    return f"""    <article{cls}>
{img}      <div class="kicker{' kr' if kr else ''}">{esc(a.get("kicker"))}</div>
      <h3>{rich(a.get("title"))}</h3>
{paras(a.get("body"))}
      {source(a.get("source"))}
    </article>"""


def render_row(articles, cols, fn):
    if not articles:
        return ""
    inner = "\n".join(fn(a) for a in articles)
    return f'  <div class="row c{cols}">\n{inner}\n  </div>'


def render_briefs(items):
    if not items:
        return ""
    cells = "\n".join(
        f"""    <div class="brief">
      <h4>{rich(b.get("title"))}</h4>
      <p>{rich(b.get("body"))}</p>
      {source(b.get("source"))}
    </div>"""
        for b in items
    )
    return f'  <div class="briefs">\n{cells}\n  </div>'


def render_foot(d):
    y, m, dd = d["date"].split("-")
    outlets = " · ".join(d.get("outlets", []))
    return f"""  <div class="paper-foot">
    <div class="cn">HEUY<span class="d">.</span>ARCHI</div>
    DAILY ARCHITECTURE BRIEFING &nbsp;|&nbsp; 편집·제작 {esc(d.get("editor", "HUEY"))} &nbsp;|&nbsp; {int(y)}년 {int(m)}월 {int(dd)}일 발행<br>
    출처: {esc(outlets)}<br>
    각 매체 보도를 기반으로 편집했습니다. 이미지 저작권은 각 매체·제공자에 있으며, 인용 시 원문 확인을 권장합니다.
  </div>"""


def render_issue(d, root, current):
    body = "\n".join(x for x in [
        nav(root, current),
        '<div class="sheet">',
        render_brandbar(d),
        render_teasers(d.get("teasers", [])),
        render_masthead(d),
        render_top(d),
        render_sechead("해외", "INTERNATIONAL"),
        render_row(d.get("intl_feature", []), 2, render_feature),
        render_row(d.get("intl_grid", []), 4, render_card),
        render_sechead("국내", "KOREA"),
        render_row(d.get("korea", []), 3, lambda a: render_card(a, kr=True)),
        render_sechead("단신", "IN BRIEF"),
        render_briefs(d.get("briefs", [])),
        render_foot(d),
        "</div>",
    ] if x)
    title = f'HEUY.ARCHI — Daily Architecture Briefing · {d["date"].replace("-", ".")}'
    return shell(title, body, css_prefix=root)


def render_brandbar(d):
    y, m, dd = d["date"].split("-")
    return f"""  <div class="brandbar">
    <div>HEUY<span class="dot">.</span>ARCHI</div>
    <span>DAILY ARCHITECTURE BRIEFING</span>
    <span>{esc(d.get("vol", "VOL.01"))}</span>
    <span>{y} . {m} . {dd}</span>
  </div>"""


# ------------------------------------------------------------------ archive
def render_archive(items):
    rows = []
    for it in items:
        y, m, dd = it["date"].split("-")
        rows.append(f"""      <li class="ar-row">
        <a href="issues/{it["date"]}.html">
          <span class="ar-date">{y}.{m}.{dd}<em>{weekday(it["date"])}</em></span>
          <span class="ar-title">{esc(it["lede"])}</span>
          <span class="ar-go">지면 보기 →</span>
        </a>
      </li>""")
    body = f"""{nav("", "archive")}
<div class="ar-wrap">
  <header class="ar-head">
    <h1>HEUY<span>.</span>ARCHI</h1>
    <div class="tag">DAILY ARCHITECTURE BRIEFING</div>
    <div class="sub">ARCHIVE · 지난호 {len(items)}개</div>
  </header>
  <ul class="ar-list">
{chr(10).join(rows)}
  </ul>
  <div class="ar-foot">편집·제작 HUEY · 매일 오전 9시 발행</div>
</div>"""
    return shell("지난호 — HEUY.ARCHI", body)


# ------------------------------------------------------------------ main
def load(day):
    with open(os.path.join(DATA, f"{day}.json"), encoding="utf-8") as f:
        return json.load(f)


def build(days):
    os.makedirs(ISSUES, exist_ok=True)
    index = []
    idx_path = os.path.join(ROOT, "issues.json")
    if os.path.exists(idx_path):
        index = json.load(open(idx_path, encoding="utf-8"))

    for day in days:
        d = load(day)
        d["date"] = day
        with open(os.path.join(ISSUES, f"{day}.html"), "w", encoding="utf-8") as f:
            f.write(render_issue(d, "../", "index"))
        lede = re.sub(r"<[^>]+>", "", rich((d.get("top") or {}).get("lede", "")))
        index = [i for i in index if i["date"] != day]
        index.append({"date": day, "lede": html.unescape(lede).strip()})
        print(f"  issues/{day}.html")

    index.sort(key=lambda i: i["date"], reverse=True)

    latest = load(index[0]["date"])
    latest["date"] = index[0]["date"]
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_issue(latest, "", "index"))
    with open(os.path.join(ROOT, "archive.html"), "w", encoding="utf-8") as f:
        f.write(render_archive(index))
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"  index.html      → 최신호 {index[0]['date']}")
    print(f"  archive.html    → {len(index)}개")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("사용법: python3 render.py <YYYY-MM-DD> | --all")
    if args[0] == "--all":
        days = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    else:
        days = args
    build(days)
