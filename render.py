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
CATEGORIES_DIR = os.path.join(ROOT, "categories")
WEEK = ["월", "화", "수", "목", "금", "토", "일"]

# 상단 탭. "main"은 홈(index.html), 나머지는 categories/<slug>.html 아카이브.
# "korea"는 topic이 아니라 korea[] 섹션 소속 여부로 채워진다.
TOPIC_TABS = [
    ("main", "메인"),
    ("regulation", "제도규제"),
    ("projects", "프로젝트"),
    ("urban-regen", "도시재생"),
    ("disaster-heritage", "재난유산"),
    ("korea", "국내"),
    ("competitions", "설계공모"),
    ("awards", "수상"),
]
SECTION_KEYS = ["intl_feature", "intl_grid", "korea", "briefs"]


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


def first_url(src):
    """source에서 첫 링크 URL을 찾는다. {"outlet":..,"links":[...]} 또는 그 목록."""
    if not src:
        return None
    groups = src if isinstance(src, list) else [src]
    for g in groups:
        for l in (g.get("links") or []):
            if l.get("url"):
                return l["url"]
    return None


def link_title(title, src):
    """헤드라인을 원문 출처 링크로 감싼다. 출처가 없으면 텍스트만 반환."""
    text = rich(title)
    url = first_url(src)
    if not url:
        return text
    return f'<a class="hl" href="{esc(url)}" target="_blank" rel="noopener">{text}</a>'


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
<link rel="icon" type="image/png" sizes="16x16" href="{css_prefix}assets/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="32x32" href="{css_prefix}assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="48x48" href="{css_prefix}assets/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="{css_prefix}assets/favicon-192x192.png">
<link rel="apple-touch-icon" sizes="180x180" href="{css_prefix}assets/apple-touch-icon.png">
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


def cat_href(root, slug):
    return f"{root}index.html" if slug == "main" else f"{root}categories/{slug}.html"


def render_catbar(root, current):
    cells = "".join(
        f'<a class="hi" href="{cat_href(root, slug)}">{esc(label)}</a>'
        if slug == current else
        f'<a href="{cat_href(root, slug)}">{esc(label)}</a>'
        for slug, label in TOPIC_TABS
    )
    return f'<div class="catbar">{cells}</div>'


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


def render_masthead(d, root):
    day = d["date"]
    y, m, dd = day.split("-")
    c = d.get("counts", {})
    return f"""  <header class="masthead">
    <h1 class="logo">HEUY<span class="d">.</span>ARCHI</h1>
    <div class="logo-rule"></div>
    <div class="tagline">DAILY ARCHITECTURE BRIEFING</div>
    <div class="rule-thick"></div>
    {render_catbar(root, "main")}
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
    top_url = first_url(t.get("source"))
    if top_url:
        lede = f'<a class="hl" href="{esc(top_url)}" target="_blank" rel="noopener">{lede}</a>'

    cap = f'      <figcaption>{rich(t.get("caption"))}</figcaption>' if t.get("caption") else ""
    main = f"""  <div class="topblock">
    <div class="topmain" id="art-top">
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
    <aside class="topside" id="art-side">
      <div class="sidehead">{esc(s.get("label", "실무 직결 · 제도/규제"))}</div>
      {thumb(s.get("image"), s.get("image_label"))}
      <h3>{link_title(s.get("title"), s.get("source"))}</h3>
{paras(s.get("body"))}
{facts}
{paras(s.get("body_after"))}
      {source(s.get("source"))}
    </aside>
  </div>"""
    return main + side


def render_sechead(ko, en):
    return f'  <div class="sechead"><h2>{esc(ko)}</h2><span class="en">{esc(en)}</span><span class="line"></span></div>'


def render_feature(a, aid=None):
    """헤드라인 아래 이미지 좌 / 본문 우."""
    idattr = f' id="{esc(aid)}"' if aid else ""
    return f"""    <article{idattr}>
      <div class="kicker">{esc(a.get("kicker"))}</div>
      <h3>{link_title(a.get("title"), a.get("source"))}</h3>
      <div class="feature">
        {thumb(a.get("image"), a.get("image_label"))}
        <div>
{paras(a.get("body"))}
        </div>
      </div>
      {source(a.get("source"))}
    </article>"""


def render_card(a, aid=None, kr=False):
    """이미지 위 / 본문 아래. 이미지가 없으면 좌측 보더 텍스트 카드."""
    has_img = bool(a.get("image"))
    cls = "kr-side" if (not has_img and kr) else ""
    classattr = f' class="{cls}"' if cls else ""
    idattr = f' id="{esc(aid)}"' if aid else ""
    img = f"      {thumb(a.get('image'), a.get('image_label'))}\n" if has_img else ""
    return f"""    <article{classattr}{idattr}>
{img}      <div class="kicker{' kr' if kr else ''}">{esc(a.get("kicker"))}</div>
      <h3>{link_title(a.get("title"), a.get("source"))}</h3>
{paras(a.get("body"))}
      {source(a.get("source"))}
    </article>"""


def render_row(articles, cols, fn, section=None, indices=None):
    if not articles:
        return ""
    idxs = indices if indices is not None else range(len(articles))
    inner = "\n".join(
        fn(a, aid=f"art-{section}-{i}") if section else fn(a)
        for a, i in zip(articles, idxs)
    )
    return f'  <div class="row c{cols}">\n{inner}\n  </div>'


def split_competitions(d):
    """topic="설계공모" 기사를 해외/국내 배열에서 분리한다.
    (분리는 메인/발행일 페이지 렌더링 시점에만 적용 — 카테고리 아카이브는
    원본 배열을 그대로 스캔하므로 국내·설계공모 탭 양쪽에 정상적으로 실린다.)
    각 항목의 원본 section/index를 aid로 함께 들고 다녀 앵커 id가 필터링·이동 후에도 유지되게 한다."""
    feature_items = list(enumerate(d.get("intl_feature") or []))
    grid_items = list(enumerate(d.get("intl_grid") or []))
    korea_items = list(enumerate(d.get("korea") or []))

    comps = [(a, False, f"art-intl_feature-{i}") for i, a in feature_items if a.get("topic") == "설계공모"] + \
            [(a, False, f"art-intl_grid-{i}") for i, a in grid_items if a.get("topic") == "설계공모"] + \
            [(a, True, f"art-korea-{i}") for i, a in korea_items if a.get("topic") == "설계공모"]

    feature = [a for i, a in feature_items if a.get("topic") != "설계공모"]
    feature_idx = [i for i, a in feature_items if a.get("topic") != "설계공모"]
    grid = [a for i, a in grid_items if a.get("topic") != "설계공모"]
    grid_idx = [i for i, a in grid_items if a.get("topic") != "설계공모"]
    korea = [a for i, a in korea_items if a.get("topic") != "설계공모"]
    korea_idx = [i for i, a in korea_items if a.get("topic") != "설계공모"]

    return comps, feature, grid, korea, feature_idx, grid_idx, korea_idx


def render_competitions_section(triples):
    if not triples:
        return ""
    inner = "\n".join(render_card(a, aid=aid, kr=is_kr) for a, is_kr, aid in triples)
    return render_sechead("설계공모", "COMPETITIONS") + f'\n  <div class="row c3">\n{inner}\n  </div>'


def render_briefs(items):
    if not items:
        return ""
    cells = "\n".join(
        f"""    <div class="brief" id="art-briefs-{i}">
      <h4>{link_title(b.get("title"), b.get("source"))}</h4>
      <p>{rich(b.get("body"))}</p>
      {source(b.get("source"))}
    </div>"""
        for i, b in enumerate(items)
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
    comps, feature, grid, korea, feature_idx, grid_idx, korea_idx = split_competitions(d)
    body = "\n".join(x for x in [
        nav(root, current),
        '<div class="sheet">',
        render_brandbar(d),
        render_teasers(d.get("teasers", [])),
        render_masthead(d, root),
        render_cardnews_strip(d, root),
        render_top(d),
        render_sechead("해외", "INTERNATIONAL"),
        render_row(feature, 2, render_feature, section="intl_feature", indices=feature_idx),
        render_row(grid, 4, render_card, section="intl_grid", indices=grid_idx),
        render_sechead("국내", "KOREA"),
        render_row(korea, 3, lambda a, aid=None: render_card(a, aid=aid, kr=True), section="korea", indices=korea_idx),
        render_competitions_section(comps),
        render_sechead("단신", "IN BRIEF"),
        render_briefs(d.get("briefs", [])),
        render_foot(d),
        "</div>",
    ] if x)
    title = f'HEUY.ARCHI — Daily Architecture Briefing · {d["date"].replace("-", ".")}'
    return shell(title, body, css_prefix=root)


def resolve_ref(d, ref):
    """카드뉴스 ref({"section":..,"index":..})가 가리키는 원본 기사를 찾는다."""
    section = (ref or {}).get("section")
    if section in ("top", "side"):
        return d.get(section) or {}
    idx = (ref or {}).get("index")
    arr = d.get(section) or []
    if idx is not None and 0 <= idx < len(arr):
        return arr[idx]
    return {}


def ref_anchor(ref):
    section = (ref or {}).get("section")
    if section in ("top", "side"):
        return f"art-{section}"
    return f"art-{section}-{(ref or {}).get('index')}"


def render_cardnews_strip(d, root):
    """TOP STORY 위에 얹는 카드뉴스 3개 스트립. cardnews 필드가 없으면 아무것도 렌더링하지 않는다."""
    items = d.get("cardnews") or []
    if not items:
        return ""
    day = d["date"]
    cells = []
    for it in items:
        slug = it["slug"]
        cover = f"{root}cardnews/{day}/{slug}/01.png"
        href = f"{root}cardnews/{day}/{slug}.html"
        cells.append(f"""      <a class="cn-tile" href="{esc(href)}">
        <div class="cn-thumb"><img src="{esc(cover)}" alt="" loading="lazy"></div>
        <div class="cn-tag">{esc(it.get("tag") or "MAGAZINE")}</div>
        <h4>{esc(it.get("title"))}</h4>
      </a>""")
    inner = "\n".join(cells)
    return f"""  <div class="cardnews-strip">
    <div class="cn-strip-head"><span class="cn-brand">HUEY ARCHI MAGAZINE</span><span class="cn-sub">오늘의 카드뉴스</span></div>
    <div class="cn-row">
{inner}
    </div>
  </div>"""


def render_cardnews_detail(d, item, root):
    day = d["date"]
    slug = item["slug"]
    ref = item.get("ref") or {}
    article = resolve_ref(d, ref)
    aid = ref_anchor(ref)

    n = len(item.get("slides") or [])
    slides_html = "\n".join(
        f'      <div class="cn-slide"><img src="{esc(root)}cardnews/{esc(day)}/{esc(slug)}/{i + 1:02d}.png" alt="" loading="lazy"></div>'
        for i in range(n)
    )

    orig_title = article.get("title") or article.get("lede") or item.get("title") or ""
    heuy_link = f"{root}issues/{day}.html#{aid}"

    body = f"""{nav(root, "")}
<div class="cn-wrap">
  <div class="cn-detail-head">
    <span class="cn-brand">HUEY ARCHI MAGAZINE</span>
    <span class="cn-editor">Editor {esc(d.get("editor", "HUEY"))}</span>
  </div>
  <h1 class="cn-detail-title">{esc(item.get("title"))}</h1>
  <div class="cn-carousel" id="cnCarousel">
{slides_html}
  </div>
  <div class="cn-dots" id="cnDots"></div>
  <div class="cn-infobar">
    <div class="cn-info-row">
      <span class="cn-info-label">원문 출처</span>
      {source(article.get("source"))}
    </div>
    <div class="cn-info-row">
      <span class="cn-info-label">HUEY.ARCHI 기사</span>
      <a href="{esc(heuy_link)}">{esc(orig_title)} →</a>
    </div>
  </div>
</div>
<script>
(function () {{
  var car = document.getElementById('cnCarousel');
  var dotsWrap = document.getElementById('cnDots');
  var slides = car.querySelectorAll('.cn-slide');
  slides.forEach(function (_, i) {{
    var dot = document.createElement('span');
    dot.className = 'cn-dot' + (i === 0 ? ' on' : '');
    dotsWrap.appendChild(dot);
  }});
  var dotEls = dotsWrap.querySelectorAll('.cn-dot');
  car.addEventListener('scroll', function () {{
    var idx = Math.round(car.scrollLeft / car.clientWidth);
    dotEls.forEach(function (el, i) {{ el.classList.toggle('on', i === idx); }});
  }}, {{ passive: true }});
}})();
</script>"""
    return shell(f'{item.get("title")} — HUEY ARCHI MAGAZINE', body, css_prefix=root)


def build_cardnews_pages(d):
    day = d["date"]
    items = d.get("cardnews") or []
    if not items:
        return 0
    out_dir = os.path.join(ROOT, "cardnews", day)
    os.makedirs(out_dir, exist_ok=True)
    for it in items:
        with open(os.path.join(out_dir, f'{it["slug"]}.html'), "w", encoding="utf-8") as f:
            f.write(render_cardnews_detail(d, it, "../../"))
    return len(items)


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
    {render_catbar("", "main")}
    <div class="sub">ARCHIVE · 지난호 {len(items)}개</div>
  </header>
  <ul class="ar-list">
{chr(10).join(rows)}
  </ul>
  <div class="ar-foot">편집·제작 HUEY · 매일 오전 9시 발행</div>
</div>"""
    return shell("지난호 — HEUY.ARCHI", body)


# ------------------------------------------------------------------ categories
def collect_articles():
    """data/*.json 전체를 훑어 (date, section, topic, article) 튜플로 평탄화."""
    out = []
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json"):
            continue
        day = fn[:-5]
        d = load(day)
        top = d.get("top")
        if top:
            out.append((day, "top", top.get("topic") or "프로젝트", top))
        side = d.get("side")
        if side:
            out.append((day, "side", side.get("topic") or "제도규제", side))
        for key in SECTION_KEYS:
            for a in d.get(key) or []:
                out.append((day, key, a.get("topic") or "프로젝트", a))
    return out


def render_category_page(slug, label, entries):
    rows = []
    for day, section, topic, a in entries:
        y, m, dd = day.split("-")
        body = a.get("body")
        if isinstance(body, list):
            body = body[0] if body else ""
        rows.append(f"""      <li class="cat-row">
        {thumb(a.get("image"), a.get("image_label"), "cat-thumb")}
        <div class="cat-main">
          <span class="cat-date">{y}.{m}.{dd}</span>
          <div class="kicker{' kr' if section == 'korea' else ''}">{esc(a.get("kicker") or topic)}</div>
          <h3>{link_title(a.get("title") or a.get("lede"), a.get("source"))}</h3>
          <p>{rich(body)}</p>
          {source(a.get("source"))}
        </div>
      </li>""")
    empty = '      <li class="cat-empty">아직 등록된 기사가 없습니다.</li>'
    body = f"""{nav("../", "")}
<div class="ar-wrap">
  <header class="ar-head">
    <h1>HEUY<span>.</span>ARCHI</h1>
    <div class="tag">DAILY ARCHITECTURE BRIEFING</div>
    {render_catbar("../", slug)}
    <div class="sub">{esc(label)} · 전체 {len(entries)}건</div>
  </header>
  <ul class="cat-list">
{chr(10).join(rows) if rows else empty}
  </ul>
  <div class="ar-foot">편집·제작 HUEY · 매일 오전 8시 발행</div>
</div>"""
    return shell(f"{label} — HEUY.ARCHI", body, css_prefix="../")


def build_categories():
    os.makedirs(CATEGORIES_DIR, exist_ok=True)
    all_articles = sorted(collect_articles(), key=lambda x: x[0], reverse=True)
    for slug, label in TOPIC_TABS:
        if slug == "main":
            continue
        if slug == "korea":
            entries = [e for e in all_articles if e[1] == "korea"]
        else:
            entries = [e for e in all_articles if e[2] == label]
        with open(os.path.join(CATEGORIES_DIR, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(render_category_page(slug, label, entries))
        print(f"  categories/{slug}.html → {len(entries)}건")


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
        n_cn = build_cardnews_pages(d)
        lede = re.sub(r"<[^>]+>", "", rich((d.get("top") or {}).get("lede", "")))
        index = [i for i in index if i["date"] != day]
        index.append({"date": day, "lede": html.unescape(lede).strip()})
        print(f"  issues/{day}.html" + (f"  (+ 카드뉴스 {n_cn}건)" if n_cn else ""))

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

    build_categories()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("사용법: python3 render.py <YYYY-MM-DD> | --all")
    if args[0] == "--all":
        days = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    else:
        days = args
    build(days)
