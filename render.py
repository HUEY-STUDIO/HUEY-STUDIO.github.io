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

import hashlib
import html
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
ISSUES = os.path.join(ROOT, "issues")
CATEGORIES_DIR = os.path.join(ROOT, "categories")
WEEKLY_DIR = os.path.join(ROOT, "weekly")
WEEK = ["월", "화", "수", "목", "금", "토", "일"]


def _asset_ver(path):
    """assets/style.css·site.js에 붙일 캐시버스팅 쿼리스트링. 내용이 바뀔 때만 값이
    바뀌므로, 브라우저·GitHub Pages의 CSS 캐시(max-age=600) 때문에 방금 올린 디자인
    수정이 안 보이는 문제를 build마다 자동으로 막는다."""
    try:
        with open(os.path.join(ROOT, path), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:8]
    except FileNotFoundError:
        return "0"


STYLE_VER = _asset_ver("assets/style.css")
SITE_JS_VER = _asset_ver("assets/site.js")

# 공유 카드(og:image)·canonical·RSS·sitemap이 모두 이 주소를 기준으로 절대 URL을 만든다.
SITE_URL = "https://huey-studio.github.io"
SITE_NAME = "HEUY.ARCHI"
SITE_DESC = "매일 아침 발행하는 건축·건설 데일리 브리핑. 국내외 설계·시공·제도·설계공모 소식을 하루 한 장으로."
OG_DEFAULT = "assets/og-default.jpg"

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

# 카드뉴스 이미지 확장자. cardnews.py의 EXT와 반드시 같아야 한다.
CARDNEWS_EXT = "jpg"


# ------------------------------------------------------------------ helpers
def esc(s):
    return html.escape(str(s or ""), quote=False)


def rich(s):
    """**강조** → <b>강조</b>. 그 외 문자는 이스케이프."""
    s = str(s or "")
    out, last = [], 0
    for m in re.finditer(r"\*\*(.+?)\*\*", s, re.S):
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


def abs_url(path):
    """사이트 루트 기준 상대경로를 절대 URL로. og:image·canonical은 절대 URL이어야 한다."""
    return f"{SITE_URL}/{str(path or '').lstrip('/')}"


def clip(s, n=155):
    """meta description용으로 태그를 걷어내고 길이를 자른다."""
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(str(s or "")))).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# 다크모드 토글은 CSS가 오기 전에 실행돼야 첫 페인트에서 흰 화면이 번쩍이지 않는다.
THEME_BOOT = (
    "<script>(function(){try{var t=localStorage.getItem('heuy-theme');"
    "if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}"
    "catch(e){}})();</script>"
)


def shell(title, body, css_prefix="", description=None, canonical=None,
          og_image=None, og_type="website", jsonld=None, og_size=(1200, 630)):
    """모든 페이지의 공통 <head>. 공유 카드(OG)·canonical·구조화 데이터를 여기서 한 번에 붙인다."""
    desc = clip(description or SITE_DESC)
    canon = canonical or abs_url("")
    image = og_image or abs_url(OG_DEFAULT)
    ld = ""
    if jsonld:
        ld = ('\n<script type="application/ld+json">'
              + json.dumps(jsonld, ensure_ascii=False, separators=(",", ":"))
              + "</script>")
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{html.escape(desc, quote=True)}">
<link rel="canonical" href="{html.escape(canon, quote=True)}">
<meta property="og:type" content="{esc(og_type)}">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta property="og:locale" content="ko_KR">
<meta property="og:title" content="{html.escape(str(title), quote=True)}">
<meta property="og:description" content="{html.escape(desc, quote=True)}">
<meta property="og:url" content="{html.escape(canon, quote=True)}">
<meta property="og:image" content="{html.escape(image, quote=True)}">
<meta property="og:image:width" content="{og_size[0]}">
<meta property="og:image:height" content="{og_size[1]}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{html.escape(str(title), quote=True)}">
<meta name="twitter:description" content="{html.escape(desc, quote=True)}">
<meta name="twitter:image" content="{html.escape(image, quote=True)}">
<meta name="theme-color" content="#0B0B0C">
<link rel="alternate" type="application/rss+xml" title="{esc(SITE_NAME)}" href="{css_prefix}feed.xml">
<link rel="icon" type="image/png" sizes="16x16" href="{css_prefix}assets/favicon-16x16.png">
<link rel="icon" type="image/png" sizes="32x32" href="{css_prefix}assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="48x48" href="{css_prefix}assets/favicon-48x48.png">
<link rel="icon" type="image/png" sizes="192x192" href="{css_prefix}assets/favicon-192x192.png">
<link rel="apple-touch-icon" sizes="180x180" href="{css_prefix}assets/apple-touch-icon.png">
<link rel="stylesheet" as="style" crossorigin
      href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard-dynamic-subset.css">
<link rel="stylesheet" href="{css_prefix}assets/style.css?v={STYLE_VER}">{ld}
{THEME_BOOT}
</head>
<body>
{body}
<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2" defer></script>
<script src="{css_prefix}assets/site.js?v={SITE_JS_VER}" defer></script>
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
    <a href="{root}weekly.html"{mark("weekly")}>주간</a>
    <a href="{root}stats.html"{mark("stats")}>통계</a>
    <a href="{root}search.html"{mark("search")}>검색</a>
  </nav>
  <button type="button" class="theme-toggle" id="themeToggle"
          aria-label="밝은 화면과 어두운 화면 전환" title="화면 전환"></button>
</div>
<script>
(function () {{
  var btn = document.getElementById('themeToggle');
  if (!btn) return;
  var root = document.documentElement;
  function current() {{
    var set = root.getAttribute('data-theme');
    if (set) return set;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }}
  function paint() {{ btn.textContent = current() === 'dark' ? '☀' : '☾'; }}
  btn.addEventListener('click', function () {{
    var next = current() === 'dark' ? 'light' : 'dark';
    root.setAttribute('data-theme', next);
    try {{ localStorage.setItem('heuy-theme', next); }} catch (e) {{}}
    paint();
  }});
  paint();
}})();
</script>"""


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


def issue_og_image(day):
    """그날 공유 카드. cardnews.py가 구워둔 og.jpg가 있으면 그걸, 없으면 사이트 기본 카드."""
    if os.path.exists(os.path.join(ROOT, "cardnews", day, f"og.{CARDNEWS_EXT}")):
        return abs_url(f"cardnews/{day}/og.{CARDNEWS_EXT}")
    return abs_url(OG_DEFAULT)


def issue_description(d):
    top = d.get("top") or {}
    c = d.get("counts", {})
    lede = clip(rich(top.get("lede")), 100)
    tail = f' 외 {c["total"] - 1}건' if isinstance(c.get("total"), int) and c["total"] > 1 else ""
    return f"{lede}{tail} — 건축·건설 데일리 브리핑 HEUY.ARCHI"


def issue_jsonld(d, day, canonical, image, description):
    top = d.get("top") or {}
    return {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": clip(rich(top.get("lede")), 110),
        "description": description,
        "datePublished": f"{day}T08:00:00+09:00",
        "dateModified": f"{day}T08:00:00+09:00",
        "image": [image],
        "author": {"@type": "Person", "name": d.get("editor", "HUEY")},
        "publisher": {
            "@type": "Organization",
            "name": SITE_NAME,
            "logo": {"@type": "ImageObject", "url": abs_url("assets/favicon-192x192.png")},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": canonical},
        "inLanguage": "ko-KR",
    }


def render_issue_nav(root, prev_day, next_day):
    """지면 하단의 이전호/다음호 이동. 아카이브 목록을 거치지 않고 날짜를 넘길 수 있게."""
    if not prev_day and not next_day:
        return ""
    def cell(day, kind, label):
        if not day:
            return '<span class="io-cell is-empty"></span>'
        y, m, dd = day.split("-")
        return (f'<a class="io-cell io-{kind}" href="{root}issues/{day}.html">'
                f'<span class="io-label">{label}</span>'
                f'<span class="io-date">{y}.{m}.{dd} <em>{weekday(day)}</em></span></a>')
    return f"""  <nav class="issue-nav">
    {cell(prev_day, "prev", "‹ 이전호")}
    <a class="io-cell io-all" href="{root}archive.html"><span class="io-label">지난호 전체</span></a>
    {cell(next_day, "next", "다음호 ›")}
  </nav>"""


def render_account_panel():
    """홈페이지 전용 로그인/계정 패널. 상단바가 아니라 티저 스트립 옆 오른쪽 레이아웃으로 붙는다."""
    return """    <aside class="account-panel" id="accountPanel">
      <div id="apLoggedOut">
        <div class="ap-avatar">?</div>
        <p class="ap-lead">로그인하고<br>피드백에 댓글을 남겨보세요</p>
        <form id="authForm">
          <input type="email" id="authEmail" placeholder="you@email.com" required autocomplete="email">
          <button type="submit">매직링크 받기</button>
        </form>
        <p class="ap-note" id="authNote">비밀번호 없이 메일로 받은 링크로 로그인합니다.</p>
      </div>
      <div id="apLoggedIn" class="hidden">
        <div class="ap-row">
          <button type="button" class="ap-avatar ap-avatar-btn" id="apAvatar" title="프로필 사진 바꾸기">
            <img id="apAvatarImg" class="hidden" alt="">
            <span id="apAvatarLetter">·</span>
          </button>
          <input type="file" id="apAvatarFile" accept="image/*" class="hidden">
          <div class="ap-who">
            <div class="ap-name"><span id="apName"></span><button type="button" id="apEditNick" class="ap-edit" title="닉네임 변경">✎</button></div>
            <div class="ap-email" id="apEmail"></div>
          </div>
        </div>
        <form id="nickForm" class="ap-nickform hidden">
          <input type="text" id="nickInput" maxlength="20" placeholder="새 닉네임">
          <div class="ap-nickbtns">
            <button type="submit">저장</button>
            <button type="button" id="nickCancel">취소</button>
          </div>
        </form>
        <p class="ap-note" id="apAvatarNote"></p>
        <button type="button" id="authLogout" class="ap-logout">로그아웃</button>
      </div>
    </aside>"""


def render_mini_space():
    """홈페이지 전용: 계정 패널 바로 아래 붙는 미니 스페이스. 방향키로 픽셀 캐릭터를 움직인다.
    로그인 여부와 무관하게 누구나 가지고 놀 수 있는 장식용 위젯 — 위치는 저장하지 않는다."""
    return """    <div class="mini-space" id="miniSpace">
      <div class="ms-head"><span id="msTitle">MY SPACE</span></div>
      <div class="ms-room" id="msRoom" tabindex="0" aria-label="방향키로 캐릭터를 움직여보세요">
        <div class="ms-platform">
          <div class="ms-floor"></div>
          <div class="ms-deco ms-deco--table"></div>
          <div class="ms-deco ms-deco--plant"><span></span></div>
          <div class="ms-char" id="msChar"><div class="ms-char-body"></div></div>
        </div>
      </div>
      <p class="ms-hint">클릭한 뒤 방향키로 자유롭게 움직여보세요(대각선도 가능)</p>
    </div>"""


def render_feedback_room():
    """홈페이지 전용 실시간 피드백/댓글 채팅방. assets/site.js(Supabase)가 이 안을 채운다."""
    return """  <div class="feedback-room" id="feedbackRoom">
    <div class="fr-head">
      <span class="fr-title">피드백 &amp; 댓글</span>
      <span class="fr-sub">실시간으로 남깁니다 — 누구나 볼 수 있어요</span>
    </div>
    <div class="fr-messages" id="frMessages">
      <p class="fr-empty">불러오는 중…</p>
    </div>
    <form class="fr-form" id="frForm">
      <textarea id="frInput" maxlength="500" disabled placeholder="로그인하면 댓글을 남길 수 있어요"></textarea>
      <button type="submit" id="frSubmit" disabled>남기기</button>
    </form>
    <p class="fr-hint" id="frHint">댓글을 남기려면 <button type="button" class="fr-login-link" id="frLoginLink">로그인</button>하세요.</p>
  </div>"""


def render_home_side():
    """홈페이지 전용: 로그인/계정 패널 + 실시간 피드백 채팅방을 오른쪽 세로 사이드바로 묶는다.
    본문 옆에 붙어 스크롤을 따라오다 본문 끝에서 멈춘다(position:sticky)."""
    return (f'  <aside class="home-side">\n'
            f'{render_account_panel()}\n'
            f'{render_mini_space()}\n'
            f'{render_feedback_room()}\n'
            f'  </aside>')


def render_issue(d, root, current, prev_day=None, next_day=None, canonical=None, home=False):
    comps, feature, grid, korea, feature_idx, grid_idx, korea_idx = split_competitions(d)
    day = d["date"]
    main = "\n".join(x for x in [
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
        render_issue_nav(root, prev_day, next_day),
        render_foot(d),
    ] if x)
    if home:
        sheet_inner = (f'  <div class="home-layout" id="homeLayout">\n'
                       f'    <div class="home-main">\n{main}\n    </div>\n'
                       f'    <div class="home-resizer" id="homeResizer" role="separator" '
                       f'aria-orientation="vertical" aria-label="사이드바 너비 조절" tabindex="0"></div>\n'
                       f'{render_home_side()}\n'
                       f'  </div>')
        sheet_open = '<div class="sheet sheet--home">'
    else:
        sheet_inner = main
        sheet_open = '<div class="sheet">'
    body = "\n".join(x for x in [
        nav(root, current),
        sheet_open,
        sheet_inner,
        "</div>",
    ] if x)
    title = f'HEUY.ARCHI — Daily Architecture Briefing · {day.replace("-", ".")}'
    canon = canonical or abs_url(f"issues/{day}.html")
    image = issue_og_image(day)
    desc = issue_description(d)
    return shell(title, body, css_prefix=root, description=desc, canonical=canon,
                 og_image=image, og_type="article",
                 jsonld=issue_jsonld(d, day, canon, image, desc))


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
        cover = f"{root}cardnews/{day}/{slug}/01.{CARDNEWS_EXT}"
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
        f'      <div class="cn-slide"><img src="{esc(root)}cardnews/{esc(day)}/{esc(slug)}/{i + 1:02d}.{CARDNEWS_EXT}" alt="" loading="lazy"></div>'
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
  <div class="cn-carousel-wrap">
    <div class="cn-carousel" id="cnCarousel">
{slides_html}
    </div>
    <button type="button" class="cn-arrow cn-arrow-prev" id="cnPrev" aria-label="이전 슬라이드">‹</button>
    <button type="button" class="cn-arrow cn-arrow-next" id="cnNext" aria-label="다음 슬라이드">›</button>
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
  var prevBtn = document.getElementById('cnPrev');
  var nextBtn = document.getElementById('cnNext');
  var slides = car.querySelectorAll('.cn-slide');
  var n = slides.length;
  slides.forEach(function (_, i) {{
    var dot = document.createElement('span');
    dot.className = 'cn-dot' + (i === 0 ? ' on' : '');
    dot.addEventListener('click', function () {{
      car.scrollTo({{ left: i * car.clientWidth, behavior: 'smooth' }});
    }});
    dotsWrap.appendChild(dot);
  }});
  var dotEls = dotsWrap.querySelectorAll('.cn-dot');

  function currentIndex() {{
    return Math.round(car.scrollLeft / car.clientWidth);
  }}
  function update() {{
    var idx = currentIndex();
    dotEls.forEach(function (el, i) {{ el.classList.toggle('on', i === idx); }});
    prevBtn.classList.toggle('is-hidden', idx <= 0);
    nextBtn.classList.toggle('is-hidden', idx >= n - 1);
  }}
  car.addEventListener('scroll', update, {{ passive: true }});

  prevBtn.addEventListener('click', function () {{
    car.scrollTo({{ left: Math.max(0, currentIndex() - 1) * car.clientWidth, behavior: 'smooth' }});
  }});
  nextBtn.addEventListener('click', function () {{
    car.scrollTo({{ left: Math.min(n - 1, currentIndex() + 1) * car.clientWidth, behavior: 'smooth' }});
  }});

  // 마우스 드래그로 슬라이드 넘기기 (트랙패드/터치 없이도 넘어가도록)
  var dragging = false, moved = false, startX = 0, startScroll = 0;
  car.addEventListener('mousedown', function (e) {{
    dragging = true; moved = false;
    startX = e.pageX; startScroll = car.scrollLeft;
    car.classList.add('is-dragging');
  }});
  window.addEventListener('mousemove', function (e) {{
    if (!dragging) return;
    var dx = e.pageX - startX;
    if (Math.abs(dx) > 4) moved = true;
    car.scrollLeft = startScroll - dx;
  }});
  window.addEventListener('mouseup', function () {{
    if (!dragging) return;
    dragging = false;
    car.classList.remove('is-dragging');
    car.scrollTo({{ left: currentIndex() * car.clientWidth, behavior: 'smooth' }});
  }});
  car.addEventListener('click', function (e) {{
    if (moved) {{ e.preventDefault(); e.stopPropagation(); }}
  }}, true);

  update();
}})();
</script>"""
    cover_slide = (item.get("slides") or [{}])[0]
    desc = clip(cover_slide.get("body") or orig_title or SITE_DESC)
    return shell(f'{item.get("title")} — HUEY ARCHI MAGAZINE', body, css_prefix=root,
                 description=desc,
                 canonical=abs_url(f"cardnews/{day}/{slug}.html"),
                 og_image=abs_url(f"cardnews/{day}/{slug}/01.{CARDNEWS_EXT}"),
                 og_size=(1080, 1350), og_type="article")


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
    return shell("지난호 — HEUY.ARCHI", body,
                 description=f"HEUY.ARCHI 지난호 {len(items)}개. 매일 아침 발행하는 건축·건설 데일리 브리핑의 전체 발행 이력.",
                 canonical=abs_url("archive.html"))


# ------------------------------------------------------------------ 주간 요약호
def iso_week(day):
    y, m, dd = (int(x) for x in day.split("-"))
    iso = date(y, m, dd).isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_span(days):
    """그 주에 실제로 발행된 날짜들의 처음~끝을 'M월 D일 – M월 D일'로."""
    a, b = min(days), max(days)
    ay, am, ad = (int(x) for x in a.split("-"))
    by, bm, bd = (int(x) for x in b.split("-"))
    if a == b:
        return f"{am}월 {ad}일"
    return f"{am}월 {ad}일 – {bm}월 {bd}일"


def render_weekly_page(wk, days, prev_wk, next_wk):
    """한 주의 하이라이트. 일자별 톱기사 + 그 주 제도·규제 + 그 주 설계공모."""
    days = sorted(days)
    tops, sides, comps = [], [], []
    n_art = n_kr = n_intl = 0
    for day in days:
        d = load(day)
        d["date"] = day
        c = d.get("counts", {})
        n_art += c.get("total") or 0
        n_kr += c.get("kr") or 0
        n_intl += c.get("intl") or 0
        if d.get("top"):
            tops.append((day, d["top"]))
        if d.get("side"):
            sides.append((day, d["side"]))
        for key in SECTION_KEYS:
            for i, a in enumerate(d.get(key) or []):
                if a.get("topic") == "설계공모":
                    comps.append((day, a, f"art-{key}-{i}"))

    def row(day, a, anchor, title_key="title"):
        y, m, dd = day.split("-")
        t = a.get(title_key) or a.get("lede") or a.get("title")
        return f"""      <li class="wk-row">
        <a href="../issues/{day}.html#{anchor}">
          <span class="wk-date">{m}.{dd}<em>{weekday(day)}</em></span>
          <span class="wk-main">
            <span class="wk-kicker">{esc(a.get("kicker") or a.get("label") or a.get("topic") or "")}</span>
            <span class="wk-title">{rich(t)}</span>
          </span>
        </a>
      </li>"""

    def block(ko, en, rows_html):
        if not rows_html:
            return ""
        return (f'  <div class="sechead"><h2>{esc(ko)}</h2><span class="en">{esc(en)}</span>'
                f'<span class="line"></span></div>\n  <ol class="wk-list">\n{rows_html}\n  </ol>')

    top_rows = "\n".join(row(day, a, "art-top", "lede") for day, a in tops)
    side_rows = "\n".join(row(day, a, "art-side") for day, a in sides)
    comp_rows = "\n".join(row(day, a, anc) for day, a, anc in comps)

    def wknav(w, label):
        if not w:
            return '<span class="io-cell is-empty"></span>'
        return f'<a class="io-cell" href="{w}.html"><span class="io-label">{label}</span><span class="io-date">{w}</span></a>'

    body = f"""{nav("../", "weekly")}
<div class="sheet">
  <div class="brandbar">
    <div>HEUY<span class="dot">.</span>ARCHI</div>
    <span>WEEKLY DIGEST</span>
    <span>{esc(wk)}</span>
    <span>{esc(week_span(days))}</span>
  </div>
  <header class="masthead">
    <h1 class="logo">HEUY<span class="d">.</span>ARCHI</h1>
    <div class="logo-rule"></div>
    <div class="tagline">WEEKLY DIGEST · 주간 요약</div>
    <div class="rule-thick"></div>
    {render_catbar("../", "")}
    <div class="infobar">
      <span>{esc(wk)} · {esc(week_span(days))}</span>
      <span>발행 <b>{len(days)}</b>호</span>
      <span>기사 <b>{n_art}</b>건 · 해외 <b>{n_intl}</b> / 국내 <b>{n_kr}</b></span>
      <span>설계공모 <b>{len(comps)}</b>건</span>
    </div>
  </header>
{block("이번 주 톱기사", "TOP STORIES", top_rows)}
{block("이번 주 제도·규제", "REGULATION", side_rows)}
{block("이번 주 설계공모", "COMPETITIONS", comp_rows)}
  <nav class="issue-nav">
    {wknav(prev_wk, "‹ 지난 주")}
    <a class="io-cell io-all" href="../weekly.html"><span class="io-label">주간 전체</span></a>
    {wknav(next_wk, "다음 주 ›")}
  </nav>
  <div class="paper-foot">
    <div class="cn">HEUY<span class="d">.</span>ARCHI</div>
    WEEKLY DIGEST &nbsp;|&nbsp; {esc(wk)} &nbsp;|&nbsp; 그 주 발행분에서 자동으로 추린 요약입니다.
  </div>
</div>"""
    return shell(f"{wk} 주간 요약 — HEUY.ARCHI", body, css_prefix="../",
                 description=f"{week_span(days)} 한 주간의 건축·건설 하이라이트. 발행 {len(days)}호, 기사 {n_art}건, 설계공모 {len(comps)}건.",
                 canonical=abs_url(f"weekly/{wk}.html"))


def render_weekly_index(weeks):
    rows = []
    for wk, days in weeks:
        rows.append(f"""      <li class="ar-row">
        <a href="weekly/{wk}.html">
          <span class="ar-date">{esc(wk)}</span>
          <span class="ar-title">{esc(week_span(days))} · 발행 {len(days)}호</span>
          <span class="ar-go">주간 요약 →</span>
        </a>
      </li>""")
    body = f"""{nav("", "weekly")}
<div class="ar-wrap">
  <header class="ar-head">
    <h1>HEUY<span>.</span>ARCHI</h1>
    <div class="tag">DAILY ARCHITECTURE BRIEFING</div>
    {render_catbar("", "")}
    <div class="sub">WEEKLY · 주간 요약 {len(weeks)}주</div>
  </header>
  <ul class="ar-list">
{chr(10).join(rows)}
  </ul>
  <div class="ar-foot">주간 요약은 그 주 발행분에서 자동으로 추립니다.</div>
</div>"""
    return shell("주간 요약 — HEUY.ARCHI", body,
                 description=f"HEUY.ARCHI 주간 요약 {len(weeks)}주. 한 주의 톱기사·제도규제·설계공모를 한 페이지로.",
                 canonical=abs_url("weekly.html"))


def build_weekly(index):
    os.makedirs(WEEKLY_DIR, exist_ok=True)
    buckets = {}
    for it in index:
        buckets.setdefault(iso_week(it["date"]), []).append(it["date"])
    keys = sorted(buckets, reverse=True)
    for i, wk in enumerate(keys):
        # keys는 최신순이라 다음 인덱스가 '지난 주'다.
        prev_wk = keys[i + 1] if i + 1 < len(keys) else None
        next_wk = keys[i - 1] if i > 0 else None
        with open(os.path.join(WEEKLY_DIR, f"{wk}.html"), "w", encoding="utf-8") as f:
            f.write(render_weekly_page(wk, buckets[wk], prev_wk, next_wk))
    with open(os.path.join(ROOT, "weekly.html"), "w", encoding="utf-8") as f:
        f.write(render_weekly_index([(k, buckets[k]) for k in keys]))
    print(f"  weekly/         → {len(keys)}주 (+ weekly.html)")
    return keys


# ------------------------------------------------------------------ 통계
# 차트는 전부 '크기 비교' 한 종류라 계열이 하나뿐이다. 그래서 범주별로 색을 돌리지 않고
# 브랜드 딥레드 한 색만 쓴다 — 항목 이름은 축에 이미 적혀 있으므로 색이 신원을 나를 필요가
# 없고, 색맹 안전성 문제도 애초에 생기지 않는다. 값은 막대 끝에 직접 표기한다.
def bar_rows(rows, unit="건", limit=None):
    rows = [r for r in rows if r[1]]
    if limit:
        rows = rows[:limit]
    if not rows:
        return '    <p class="st-empty">아직 데이터가 없습니다.</p>'
    top = max(v for _l, v in rows) or 1
    items = "\n".join(
        f'      <li class="st-bar"><span class="st-bl">{esc(l)}</span>'
        f'<span class="st-btrack"><span class="st-bfill" style="width:{v / top * 100:.1f}%"></span></span>'
        f'<span class="st-bv">{v}<i>{esc(unit)}</i></span></li>'
        for l, v in rows
    )
    return f'    <ol class="st-bars">\n{items}\n    </ol>'


def column_rows(rows, unit="건"):
    """일자별 추이. 값이 적은 날도 바닥에 붙어 보이도록 최소 높이를 준다."""
    if not rows:
        return '    <p class="st-empty">아직 데이터가 없습니다.</p>'
    top = max(v for _l, v in rows) or 1
    items = "\n".join(
        f'      <li class="st-col" title="{esc(l)} · {v}{esc(unit)}">'
        f'<span class="st-cfill" style="height:{max(v / top * 100, 4):.1f}%"></span>'
        f'<span class="st-cv">{v}</span>'
        f'<span class="st-cl">{esc(l[5:].replace("-", "."))}</span></li>'
        for l, v in rows
    )
    return f'    <ol class="st-cols">\n{items}\n    </ol>'


def build_stats(index):
    articles = collect_articles()
    topics, outlets, per_day, sections = {}, {}, {}, {}
    for day, section, topic, a, _anc in articles:
        topics[topic] = topics.get(topic, 0) + 1
        per_day[day] = per_day.get(day, 0) + 1
        sections[section] = sections.get(section, 0) + 1
        src = a.get("source")
        for g in (src if isinstance(src, list) else [src]) if src else []:
            o = (g or {}).get("outlet")
            if o:
                outlets[o] = outlets.get(o, 0) + 1

    n_total = len(articles)
    n_kr = sections.get("korea", 0)
    n_comp = topics.get("설계공모", 0)
    kr_pct = round(n_kr / n_total * 100) if n_total else 0

    topic_rows = sorted(topics.items(), key=lambda kv: kv[1], reverse=True)
    outlet_rows = sorted(outlets.items(), key=lambda kv: kv[1], reverse=True)
    day_rows = sorted(per_day.items())[-30:]
    sec_labels = {"top": "톱기사", "side": "제도규제 박스", "intl_feature": "해외 피처",
                  "intl_grid": "해외 그리드", "korea": "국내", "briefs": "단신"}
    sec_rows = sorted(((sec_labels.get(k, k), v) for k, v in sections.items()),
                      key=lambda kv: kv[1], reverse=True)

    def card(ko, en, inner, note=""):
        note_html = f'<p class="st-note">{esc(note)}</p>' if note else ""
        return f"""  <section class="st-card">
    <div class="sechead"><h2>{esc(ko)}</h2><span class="en">{esc(en)}</span><span class="line"></span></div>
{note_html}
{inner}
  </section>"""

    body = f"""{nav("", "stats")}
<div class="sheet">
  <div class="brandbar">
    <div>HEUY<span class="dot">.</span>ARCHI</div>
    <span>ARCHIVE STATISTICS</span>
    <span>발행 {len(index)}호</span>
    <span>기사 {n_total}건</span>
  </div>
  <header class="masthead">
    <h1 class="logo">HEUY<span class="d">.</span>ARCHI</h1>
    <div class="logo-rule"></div>
    <div class="tagline">ARCHIVE STATISTICS · 지면 통계</div>
    <div class="rule-thick"></div>
    {render_catbar("", "")}
  </header>
  <div class="st-tiles">
    <div class="st-tile"><span class="st-tv">{len(index)}</span><span class="st-tl">발행 호수</span></div>
    <div class="st-tile"><span class="st-tv">{n_total}</span><span class="st-tl">누적 기사</span></div>
    <div class="st-tile"><span class="st-tv">{kr_pct}<i>%</i></span><span class="st-tl">국내 기사 비중</span></div>
    <div class="st-tile"><span class="st-tv">{n_comp}</span><span class="st-tl">설계공모</span></div>
  </div>
{card("분야별 기사 수", "BY TOPIC", bar_rows(topic_rows))}
{card("지면 구성", "BY SECTION", bar_rows(sec_rows))}
{card("일자별 기사 수", "DAILY VOLUME", column_rows(day_rows), "최근 30호")}
{card("많이 인용한 매체", "BY OUTLET", bar_rows(outlet_rows, limit=15), "상위 15개 매체")}
  <div class="paper-foot">
    <div class="cn">HEUY<span class="d">.</span>ARCHI</div>
    ARCHIVE STATISTICS &nbsp;|&nbsp; data/*.json 전체를 매 빌드마다 다시 집계합니다.
  </div>
</div>"""
    with open(os.path.join(ROOT, "stats.html"), "w", encoding="utf-8") as f:
        f.write(shell("지면 통계 — HEUY.ARCHI", body,
                      description=f"HEUY.ARCHI 누적 {len(index)}호 {n_total}건의 분야별·매체별 분포와 발행 추이.",
                      canonical=abs_url("stats.html")))
    print(f"  stats.html      → {n_total}건 집계")


# ------------------------------------------------------------------ 검색
def outlet_names(src):
    if not src:
        return ""
    groups = src if isinstance(src, list) else [src]
    return " ".join(str(g.get("outlet") or "") for g in groups).strip()


def build_search_index():
    """search-index.json — search.html이 첫 검색 때 한 번만 내려받는다(지연 로드).

    지면 페이지에 붙이지 않고 별도 파일로 두는 이유: 발행일이 쌓일수록 색인이 커지는데,
    검색을 안 쓰는 독자에게까지 그 무게를 지울 이유가 없다."""
    rows = []
    for day, section, topic, a, anchor in collect_articles():
        body = a.get("body")
        if isinstance(body, list):
            body = " ".join(body)
        rows.append({
            "d": day,
            "t": clip(rich(a.get("title") or a.get("lede")), 160),
            "k": clip(rich(a.get("kicker")), 60),
            "b": clip(rich(body), 120),
            "p": topic,
            "s": section,
            "o": outlet_names(a.get("source")),
            "a": anchor,
            "u": first_url(a.get("source")) or "",
        })
    rows.sort(key=lambda r: r["d"], reverse=True)
    path = os.path.join(ROOT, "search-index.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    print(f"  search-index.json → {len(rows)}건 ({os.path.getsize(path) / 1024:.0f} KB)")
    return len(rows)


def render_search_page(n_articles):
    chips = "".join(
        f'<button type="button" class="sc-chip" data-topic="{esc(label)}">{esc(label)}</button>'
        for slug, label in TOPIC_TABS if slug not in ("main", "korea")
    )
    body = f"""{nav("", "search")}
<div class="ar-wrap">
  <header class="ar-head">
    <h1>HEUY<span>.</span>ARCHI</h1>
    <div class="tag">DAILY ARCHITECTURE BRIEFING</div>
    {render_catbar("", "")}
    <div class="sub">SEARCH · 전체 {n_articles}건에서 찾기</div>
  </header>
  <div class="sc-box">
    <input type="search" id="scInput" class="sc-input" autocomplete="off"
           placeholder="키워드로 지난 지면 전체를 검색합니다 — 예: 성수동, 리모델링, 목조" autofocus>
    <div class="sc-chips">
      <button type="button" class="sc-chip on" data-topic="">전체</button>{chips}
    </div>
    <div class="sc-status" id="scStatus">검색어를 입력하세요.</div>
  </div>
  <ul class="sc-list" id="scList"></ul>
</div>
<script>
(function () {{
  var input = document.getElementById('scInput');
  var list = document.getElementById('scList');
  var status = document.getElementById('scStatus');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.sc-chip'));
  var data = null, loading = false, topic = '', timer = null;

  function esc(s) {{
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {{
      return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }}[c];
    }});
  }}
  function mark(text, q) {{
    var out = esc(text);
    if (!q) return out;
    var i = out.toLowerCase().indexOf(q.toLowerCase());
    if (i < 0) return out;
    return out.slice(0, i) + '<mark>' + out.slice(i, i + q.length) + '</mark>' + out.slice(i + q.length);
  }}

  function load() {{
    if (data || loading) return Promise.resolve();
    loading = true;
    status.textContent = '색인을 불러오는 중…';
    return fetch('search-index.json').then(function (r) {{ return r.json(); }})
      .then(function (j) {{ data = j; loading = false; }})
      .catch(function () {{ loading = false; status.textContent = '색인을 불러오지 못했습니다.'; }});
  }}

  function score(row, q) {{
    var s = 0;
    if (row.t.toLowerCase().indexOf(q) >= 0) s += 6;
    if ((row.k || '').toLowerCase().indexOf(q) >= 0) s += 3;
    if ((row.b || '').toLowerCase().indexOf(q) >= 0) s += 2;
    if ((row.o || '').toLowerCase().indexOf(q) >= 0) s += 1;
    if ((row.p || '').toLowerCase().indexOf(q) >= 0) s += 1;
    return s;
  }}

  function run() {{
    var raw = input.value.trim();
    if (!raw) {{
      list.innerHTML = '';
      status.textContent = topic ? ('‘' + topic + '’ 분야 — 검색어를 입력하세요.') : '검색어를 입력하세요.';
      return;
    }}
    load().then(function () {{
      if (!data) return;
      var q = raw.toLowerCase();
      var hits = [];
      for (var i = 0; i < data.length; i++) {{
        var row = data[i];
        if (topic && row.p !== topic) continue;
        var s = score(row, q);
        if (s > 0) hits.push([s, row]);
      }}
      hits.sort(function (a, b) {{ return b[0] - a[0] || (a[1].d < b[1].d ? 1 : -1); }});
      status.textContent = hits.length
        ? ('‘' + raw + '’ — ' + hits.length + '건' + (topic ? ' · ' + topic : ''))
        : ('‘' + raw + '’ — 결과가 없습니다.');
      list.innerHTML = hits.slice(0, 120).map(function (h) {{
        var r = h[1], ymd = r.d.split('-');
        return '<li class="sc-row">'
          + '<a href="issues/' + r.d + '.html#' + r.a + '">'
          + '<span class="sc-date">' + ymd[0] + '.' + ymd[1] + '.' + ymd[2] + '</span>'
          + '<span class="sc-main">'
          + '<span class="sc-kicker">' + esc(r.p) + (r.o ? ' · ' + esc(r.o) : '') + '</span>'
          + '<span class="sc-title">' + mark(r.t, raw) + '</span>'
          + '<span class="sc-body">' + mark(r.b, raw) + '</span>'
          + '</span></a></li>';
      }}).join('');
    }});
  }}

  input.addEventListener('input', function () {{
    clearTimeout(timer);
    timer = setTimeout(run, 120);
  }});
  chips.forEach(function (c) {{
    c.addEventListener('click', function () {{
      chips.forEach(function (x) {{ x.classList.remove('on'); }});
      c.classList.add('on');
      topic = c.getAttribute('data-topic') || '';
      run();
    }});
  }});

  var pre = new URLSearchParams(location.search).get('q');
  if (pre) {{ input.value = pre; run(); }}
}})();
</script>"""
    return shell("검색 — HEUY.ARCHI", body,
                 description=f"HEUY.ARCHI 지난 지면 전체 {n_articles}건을 키워드로 검색합니다.",
                 canonical=abs_url("search.html"),
                 jsonld={
                     "@context": "https://schema.org",
                     "@type": "WebSite",
                     "name": SITE_NAME,
                     "url": abs_url(""),
                     "potentialAction": {
                         "@type": "SearchAction",
                         "target": {"@type": "EntryPoint",
                                    "urlTemplate": abs_url("search.html?q={search_term_string}")},
                         "query-input": "required name=search_term_string",
                     },
                 })


# ------------------------------------------------------------------ 피드 · 사이트맵
def rfc822(day, hour=8):
    """RSS pubDate용 RFC-822 시각. 발행 시각은 KST 오전 8시로 본다."""
    y, m, dd = (int(x) for x in day.split("-"))
    kst = timezone(timedelta(hours=9))
    return format_datetime(datetime(y, m, dd, hour, 0, 0, tzinfo=kst))


def issue_headlines(d):
    """그 호에 실린 모든 헤드라인을 (섹션 라벨, 제목, URL)로 훑는다. RSS 본문·검색 색인 공용."""
    out = []
    top = d.get("top")
    if top:
        out.append(("TOP", clip(rich(top.get("lede")), 200), first_url(top.get("source"))))
    side = d.get("side")
    if side:
        out.append(("제도·규제", clip(rich(side.get("title")), 200), first_url(side.get("source"))))
    labels = {"intl_feature": "해외", "intl_grid": "해외", "korea": "국내", "briefs": "단신"}
    for key in SECTION_KEYS:
        for a in d.get(key) or []:
            label = "설계공모" if a.get("topic") == "설계공모" else labels[key]
            out.append((label, clip(rich(a.get("title")), 200), first_url(a.get("source"))))
    return out


def build_feed(index):
    """feed.xml — 호 단위 RSS. 한 항목이 그날 지면 하나이고 본문에 전체 헤드라인이 담긴다."""
    items = []
    for it in index[:30]:
        day = it["date"]
        d = load(day)
        d["date"] = day
        url = abs_url(f"issues/{day}.html")
        lines = "".join(
            f"<li><b>{esc(sec)}</b> · {esc(title)}</li>" for sec, title, _u in issue_headlines(d)
        )
        c = d.get("counts", {})
        html_body = (
            f"<p>{esc(issue_description(d))}</p>"
            f"<p>오늘의 기사 {c.get('total', '-')}건 · 해외 {c.get('intl', '-')} / 국내 {c.get('kr', '-')}</p>"
            f"<ul>{lines}</ul>"
        )
        items.append(f"""  <item>
    <title>{esc(it["lede"])}</title>
    <link>{url}</link>
    <guid isPermaLink="true">{url}</guid>
    <pubDate>{rfc822(day)}</pubDate>
    <description><![CDATA[{html_body}]]></description>
  </item>""")
    now = format_datetime(datetime.now(timezone(timedelta(hours=9))))
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{esc(SITE_NAME)} — DAILY ARCHITECTURE BRIEFING</title>
  <link>{abs_url("")}</link>
  <description>{esc(SITE_DESC)}</description>
  <language>ko</language>
  <lastBuildDate>{now}</lastBuildDate>
  <atom:link href="{abs_url("feed.xml")}" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
</channel>
</rss>
"""
    with open(os.path.join(ROOT, "feed.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"  feed.xml        → {len(items)}개 항목")


def build_sitemap(index, weeks):
    urls = [("", "daily", "1.0"), ("archive.html", "daily", "0.7"),
            ("search.html", "weekly", "0.5"), ("stats.html", "weekly", "0.5")]
    for slug, _label in TOPIC_TABS:
        if slug != "main":
            urls.append((f"categories/{slug}.html", "daily", "0.6"))
    for wk in weeks:
        urls.append((f"weekly/{wk}.html", "weekly", "0.6"))
    for it in index:
        day = it["date"]
        urls.append((f"issues/{day}.html", "monthly", "0.8"))
        d = load(day)
        for cn in d.get("cardnews") or []:
            urls.append((f"cardnews/{day}/{cn['slug']}.html", "monthly", "0.6"))
    today = index[0]["date"] if index else date.today().isoformat()
    entries = "\n".join(
        f"  <url><loc>{abs_url(p)}</loc><lastmod>{today}</lastmod>"
        f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for p, cf, pr in urls
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{entries}\n</urlset>\n")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(xml)
    with open(os.path.join(ROOT, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {abs_url('sitemap.xml')}\n")
    print(f"  sitemap.xml     → {len(urls)}개 URL (+ robots.txt)")


# ------------------------------------------------------------------ categories
def collect_articles():
    """data/*.json 전체를 훑어 (date, section, topic, article, anchor) 튜플로 평탄화."""
    out = []
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json"):
            continue
        day = fn[:-5]
        d = load(day)
        top = d.get("top")
        if top:
            out.append((day, "top", top.get("topic") or "프로젝트", top, "art-top"))
        side = d.get("side")
        if side:
            out.append((day, "side", side.get("topic") or "제도규제", side, "art-side"))
        for key in SECTION_KEYS:
            for i, a in enumerate(d.get(key) or []):
                out.append((day, key, a.get("topic") or "프로젝트", a, f"art-{key}-{i}"))
    return out


def render_category_page(slug, label, entries):
    rows = []
    for day, section, topic, a, _anchor in entries:
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
    return shell(f"{label} — HEUY.ARCHI", body, css_prefix="../",
                 description=f"HEUY.ARCHI '{label}' 분야 기사 전체 {len(entries)}건. 발행일 전체를 통틀어 모은 아카이브.",
                 canonical=abs_url(f"categories/{slug}.html"))


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


# ------------------------------------------------------------------ 검증
# 발행 사고는 대부분 조용히 일어난다. topic에 가운뎃점 하나가 들어가면 그 기사는 어느
# 카테고리 탭에도 안 실리고, 며칠 전 기사를 다시 실어도 아무도 알려주지 않는다.
# 여기서 빌드 전에 전부 잡는다.
VALID_TOPICS = {"제도규제", "프로젝트", "도시재생", "재난유산", "설계공모", "수상"}

# 중복 판정 문턱.
#
# URL만 보면 오탐이 난다 — 국내 건설매체의 종합기사('이주의 분양' 류) 하나에서 여러
# 꼭지를 뽑아 쓰는 건 정상이기 때문이다. 반대로 제목만 보면 놓친다 — 같은 사안을 다른
# 날 다시 쓰면서 헤드라인을 새로 쓰면 글자 유사도가 0.4까지 떨어진다(실제로 자하 하디드
# 바쿠 엑스포시티 건이 이틀 연속 톱기사로 나간 사고가 그랬다).
#
# 그래서 '한 호 안에서 2개 이상 항목이 인용한 URL'을 종합기사로 보고 예외 처리한 뒤,
# 나머지 URL이 날짜를 건너 겹치면 제목과 무관하게 중복으로 판정한다.
DUP_TITLE_RATIO = 0.78   # 출처가 달라도 제목이 이만큼 닮았으면 같은 사안이다
NEAR_TITLE_RATIO = 0.66  # 애매한 구간 — 사람이 한 번 봐야 한다
ROUNDUP_MIN = 2          # 한 호 안에서 이만큼 쓰인 URL은 종합기사로 본다


def norm_title(s):
    """제목 비교용 정규화. 매체마다 표현이 조금씩 달라도 같은 사안을 잡아내려는 목적."""
    t = re.sub(r"<[^>]+>", "", html.unescape(str(s or "")))
    return re.sub(r"[^0-9a-z가-힣]+", "", t.lower())


TRACKING_PARAM = re.compile(r"^(utm_|fbclid|gclid|igshid|spm|ref$|from$)", re.I)


def norm_url(u):
    """추적 파라미터·트레일링 슬래시 차이는 지우되 쿼리스트링 자체는 남긴다.

    국내 매체 상당수가 ?idxno= 로 기사를 구분해서(articleView.html?idxno=290675),
    쿼리를 통째로 버리면 그 매체의 모든 기사가 한 URL로 뭉개진다."""
    u = re.sub(r"#.*$", "", str(u or "").strip().lower())
    u = re.sub(r"^https?://(www\.)?", "", u)
    base, _sep, qs = u.partition("?")
    base = base.rstrip("/")
    if qs:
        keep = sorted(p for p in qs.split("&")
                      if p and not TRACKING_PARAM.match(p.split("=")[0]))
        if keep:
            return base + "?" + "&".join(keep)
    return base


def iter_articles(d):
    """(라벨, 기사) — 한 호 안의 모든 기사."""
    if d.get("top"):
        yield "top", d["top"]
    if d.get("side"):
        yield "side", d["side"]
    for key in SECTION_KEYS:
        for i, a in enumerate(d.get(key) or []):
            yield f"{key}[{i}]", a


def check(days, verbose=True):
    """지면 데이터를 검증하고 (오류, 경고) 목록을 돌려준다."""
    from difflib import SequenceMatcher

    errors, warns = [], []
    target = set(days)

    # 전체 아카이브를 먼저 훑어 URL·제목 원장을 만든다. 중복 검사는 '최근 3일'이 아니라
    # 반드시 전체를 상대로 해야 한다 — 같은 피드를 매일 훑기 때문에 3일로는 못 잡는다.
    ledger = []
    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json"):
            continue
        day = fn[:-5]
        d = load(day)
        for label, a in iter_articles(d):
            title = a.get("title") or a.get("lede") or ""
            src = a.get("source")
            urls = []
            for g in (src if isinstance(src, list) else [src]) if src else []:
                for l in (g or {}).get("links") or []:
                    if l.get("url"):
                        urls.append(norm_url(l["url"]))
            ledger.append({"day": day, "label": label, "title": title,
                           "norm": norm_title(title), "urls": urls})

    # 한 호 안에서 여러 항목이 같이 인용한 URL = 종합기사. 날짜를 건너 겹쳐도 중복이 아니다.
    per_day_use = {}
    for r in ledger:
        for u in set(r["urls"]):
            per_day_use[(r["day"], u)] = per_day_use.get((r["day"], u), 0) + 1
    roundup_urls = {u for (_day, u), n in per_day_use.items() if n >= ROUNDUP_MIN}

    for day in sorted(target):
        try:
            d = load(day)
        except FileNotFoundError:
            errors.append(f"{day}: data/{day}.json 이 없습니다")
            continue
        d["date"] = day
        mine = [r for r in ledger if r["day"] == day]
        others = [r for r in ledger if r["day"] != day]

        # 1) topic 값 — 렌더러가 탭 라벨과 완전일치로 집계하므로 오타 하나가 곧 누락이다
        for label, a in iter_articles(d):
            t = a.get("topic")
            if not t:
                errors.append(f"{day} {label}: topic 이 없습니다")
            elif t not in VALID_TOPICS:
                errors.append(
                    f"{day} {label}: topic '{t}' 은 허용값이 아닙니다 "
                    f"(허용: {' / '.join(sorted(VALID_TOPICS))})")
        side = d.get("side")
        if side and side.get("topic") != "제도규제":
            warns.append(f"{day} side: topic 이 '제도규제' 가 아닙니다 ({side.get('topic')})")

        # 2) counts 와 실제 기사 수
        c = d.get("counts") or {}
        actual = sum(1 for _ in iter_articles(d))
        if c.get("total") is not None and c["total"] != actual:
            errors.append(f"{day}: counts.total {c['total']} ≠ 실제 기사 {actual}건")
        kr_actual = len(d.get("korea") or [])
        if c.get("kr") is not None and c["kr"] != kr_actual:
            warns.append(f"{day}: counts.kr {c['kr']} ≠ korea[] {kr_actual}건")

        # 3) 분량 목표
        n_teasers = len(d.get("teasers") or [])
        if n_teasers != 4:
            warns.append(f"{day}: teasers 가 {n_teasers}개입니다 (4개 필요)")
        n_comp = sum(1 for _l, a in iter_articles(d) if a.get("topic") == "설계공모")
        if n_comp < 2:
            warns.append(f"{day}: 설계공모가 {n_comp}건입니다 (최소 2건)")
        if kr_actual < 3:
            warns.append(f"{day}: korea[] 가 {kr_actual}건입니다 (3~5건 권장)")

        # 4) 카드뉴스 ref 가 실존 기사를 가리키는지 + PNG/JPG 실물 개수
        for cn in d.get("cardnews") or []:
            slug = cn.get("slug") or "?"
            ref = cn.get("ref") or {}
            if not resolve_ref(d, ref):
                errors.append(f"{day} cardnews/{slug}: ref {ref} 가 가리키는 기사가 없습니다")
            n_slides = len(cn.get("slides") or [])
            out_dir = os.path.join(ROOT, "cardnews", day, slug)
            n_img = len([f for f in os.listdir(out_dir)
                         if f.endswith("." + CARDNEWS_EXT)]) if os.path.isdir(out_dir) else 0
            if n_img != n_slides:
                warns.append(f"{day} cardnews/{slug}: 슬라이드 {n_slides}장인데 "
                             f"이미지가 {n_img}장입니다 (cardnews.py 실행 필요)")

        # 5) 같은 호 안의 중복
        seen = {}
        for r in mine:
            for u in r["urls"]:
                if u in seen:
                    warns.append(f"{day}: 같은 호 안에서 URL 중복 — {r['label']} 과 {seen[u]}")
                seen[u] = r["label"]

        # 6) 과거 호와의 중복 — 이게 이 검사의 핵심이다.
        #    같은 URL을 쓴다고 곧 중복은 아니다. 종합기사 하나에서 여러 꼭지를 뽑는 건
        #    정상이므로, URL이 겹치면 제목까지 닮았을 때만 중복으로 판정한다.
        for r in mine:
            own = set(r["urls"]) - roundup_urls   # 종합기사 URL은 겹쳐도 중복 근거가 못 된다
            verdict = None      # (등급, 상대, 사유)
            roundup_hit = None  # 종합기사 URL만 겹치는 상대
            for o in others:
                ratio = 0.0
                if len(r["norm"]) >= 8 and len(o["norm"]) >= 8:
                    ratio = SequenceMatcher(None, r["norm"], o["norm"]).ratio()
                if own & set(o["urls"]):
                    verdict = ("오류", o, f"같은 원문 URL (제목 {ratio * 100:.0f}% 일치)")
                    break
                if ratio >= DUP_TITLE_RATIO:
                    verdict = ("오류", o, f"제목 {ratio * 100:.0f}% 일치")
                    break
                if ratio >= NEAR_TITLE_RATIO and verdict is None:
                    verdict = ("경고", o, f"제목 {ratio * 100:.0f}% 유사")
                if roundup_hit is None and (set(r["urls"]) & set(o["urls"])):
                    roundup_hit = o
            if verdict:
                grade, o, why = verdict
                msg = (f"{day} {r['label']}: {o['day']} {o['label']} 과 중복 — {why} "
                       f"· “{clip(r['title'], 38)}” / “{clip(o['title'], 38)}”")
                (errors if grade == "오류" else warns).append(msg)
            elif roundup_hit is not None:
                warns.append(
                    f"{day} {r['label']}: {roundup_hit['day']} {roundup_hit['label']} 과 "
                    f"출처가 같지만 종합기사로 보입니다 — 다른 꼭지면 정상 "
                    f"· “{clip(r['title'], 38)}”")

    if verbose:
        for e in errors:
            print(f"  [오류] {e}")
        for w in warns:
            print(f"  [경고] {w}")
        if not errors and not warns:
            print("  이상 없음")
    return errors, warns


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
        n_cn = build_cardnews_pages(d)
        lede = re.sub(r"<[^>]+>", "", rich((d.get("top") or {}).get("lede", "")))
        index = [i for i in index if i["date"] != day]
        index.append({"date": day, "lede": html.unescape(lede).strip()})
        print(f"  issues/{day}.html" + (f"  (+ 카드뉴스 {n_cn}건)" if n_cn else ""))

    index.sort(key=lambda i: i["date"], reverse=True)

    # 이전호/다음호 링크는 전체 발행 이력을 알아야 하므로 index 정렬 뒤에 다시 쓴다.
    # (index는 최신순이라 다음 항목이 '이전호'다.)
    all_days = [i["date"] for i in index]
    pos = {day: i for i, day in enumerate(all_days)}
    for day in days:
        d = load(day)
        d["date"] = day
        i = pos[day]
        prev_day = all_days[i + 1] if i + 1 < len(all_days) else None
        next_day = all_days[i - 1] if i > 0 else None
        with open(os.path.join(ISSUES, f"{day}.html"), "w", encoding="utf-8") as f:
            f.write(render_issue(d, "../", "index", prev_day, next_day))

    latest_day = index[0]["date"]
    latest = load(latest_day)
    latest["date"] = latest_day
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(render_issue(latest, "", "index",
                             prev_day=all_days[1] if len(all_days) > 1 else None,
                             next_day=None, canonical=abs_url(""), home=True))
    with open(os.path.join(ROOT, "archive.html"), "w", encoding="utf-8") as f:
        f.write(render_archive(index))
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"  index.html      → 최신호 {latest_day}")
    print(f"  archive.html    → {len(index)}개")

    build_categories()
    weeks = build_weekly(index)
    build_stats(index)
    n_idx = build_search_index()
    with open(os.path.join(ROOT, "search.html"), "w", encoding="utf-8") as f:
        f.write(render_search_page(n_idx))
    print("  search.html     → 검색 페이지")
    build_feed(index)
    build_sitemap(index, weeks)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        sys.exit("사용법: python3 render.py <YYYY-MM-DD> | --all | --check [<날짜>...]")

    all_days = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))

    if args[0] == "--check":
        targets = args[1:] or all_days
        print(f"검증 — {len(targets)}개 발행일 (전체 아카이브 {len(all_days)}호 대비)")
        errs, _warns = check(targets)
        sys.exit(1 if errs else 0)

    days = all_days if args[0] == "--all" else args

    # 빌드 전 자동 검증. 오류가 있어도 빌드는 계속하되(부분 수정 중일 수 있으므로)
    # 반드시 눈에 띄게 남긴다.
    print("검증")
    errs, warns = check(days)
    if errs:
        print(f"  ※ 오류 {len(errs)}건 — 고친 뒤 다시 빌드하세요 "
              f"(python3 render.py --check 로 재확인)")
    print("빌드")
    build(days)
