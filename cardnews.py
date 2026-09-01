#!/usr/bin/env python3
"""
HEUY ARCHI MAGAZINE — 카드뉴스 렌더러
------------------------------------------------------------------
  python3 cardnews.py 2026-08-19     # 해당 날짜 data/*.json의 cardnews[] 전체를 렌더
  python3 cardnews.py --all          # data/ 전체를 다시 렌더
  python3 cardnews.py 2026-08-19 --force   # 이미 있어도 다시 렌더

입력  : data/<날짜>.json 의 "cardnews" 배열
출력  : cardnews/<날짜>/<slug>/01.jpg ... 0N.jpg   (1080x1350, 인스타그램 카드뉴스 규격)

JPEG(품질 90)로 저장한다. 같은 카드가 PNG로는 장당 약 1.6MB인데 JPEG q90은 약 230KB로,
육안 차이 없이 86%가 줄어든다. 카드뉴스는 매일 3건×6장씩 쌓여 저장소 용량을 가장 빠르게
먹는 산출물이라 이 차이가 곧 GitHub Pages 1GB 한도까지의 수명을 결정한다. 인스타그램
업로드 호환성 때문에 WebP가 아니라 JPEG를 쓴다.

배경 사진은 두 종류다.

1. "official_photos" — 공공누리 등으로 자유이용이 **사람이 직접 확인된** 정부·공공기관
   이미지. [{"url": "...", "credit": "국가유산청 · 공공누리 제1유형"}] 형태로 item에 넣으면
   앞 슬라이드부터 순서대로 실제 사진을 쓴다. 실제 취재 사진이라 하단에 출처만 표기하고
   별도 disclaimer는 붙지 않는다. **원문 페이지에서 공공누리 마크·라이선스 유형을 직접
   확인하지 않은 이미지는 여기 넣으면 안 된다** — CLAUDE.md 참조.
2. "photo_query"(영문 검색어) — Unsplash에서 그 검색어로 슬라이드 수만큼 서로 다른 사진을
   한 번에 받아와(per_page) official_photos로 못 채운 나머지 슬라이드에 배정한다. 슬라이드
   하나가 item 전체와 다른 소재를 다룬다면 그 슬라이드 객체에 별도 "photo_query"를 넣어
   단독 검색하게 할 수 있다(무료 API 한도를 아끼려면 꼭 필요한 슬라이드에만 쓸 것). Unsplash
   사진은 기사 실제 사진이 아니므로 하단에 "기사 내용과 무관한 이미지입니다"라는 문구가
   자동으로 붙는다.

UNSPLASH_ACCESS_KEY 환경변수가 필요하며, 없거나 검색이 실패하면 브랜드 그래픽 배경으로
자동 폴백한다.

무료(Demo) Unsplash API는 시간당 50회 요청으로 제한된다. item당 검색 1회가 기본이므로
하루 카드뉴스 3건 발행에는 여유가 있지만, --all --force로 대량 재렌더링할 때는 이 한도를
넘지 않도록 아이템 수를 확인할 것.

render.py(웹페이지 생성)와 분리된 스크립트입니다 — render.py는 표준 라이브러리만
쓰는 게 원칙이라, Playwright가 필요한 이미지 렌더링은 여기서 따로 합니다.
PNG를 먼저 만든 다음 render.py를 돌려야 웹페이지에서 이미지가 보입니다.

  python3 cardnews.py <날짜>
  python3 render.py <날짜>
"""

import base64
import json
import os
import sys
import urllib.parse
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "cardnews")

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
W, H = 1080, 1350
EXT = "jpg"        # 저장 포맷. render.py의 카드뉴스 경로와 반드시 같아야 한다.
QUALITY = 90       # JPEG 품질. 90 아래로 내리면 표지 큰 글자 가장자리가 뭉개진다.

INK = "#0B0B0C"
RED = "#9F0F1F"
HOT = "#FF4D1A"
SAND = "#F2D3B1"
PAPER = "#EFE3D2"

FONT_LINK = (
    '<link rel="stylesheet" as="style" crossorigin '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/'
    'dist/web/static/pretendard-dynamic-subset.css">'
)
FONT_FAMILY = "'Pretendard Variable', Pretendard, 'Apple SD Gothic Neo', sans-serif"

# ------------------------------------------------------------------ 배경 사진
# 1순위는 item의 "official_photos"(공공누리 등 확인된 정부·공공기관 이미지, 실사진 그대로).
# 그걸로 못 채운 슬라이드는 "photo_query"로 Unsplash를 검색해 채운다 — 이 경우 기사와
# 무관한 연출컷이라는 문구가 자동으로 붙는다. 키 없음/검색 실패면 브랜드 그래픽으로 폴백한다.
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")


_photo_cache = {}  # query -> list[photo] | None  (같은 실행 안에서 중복 검색 방지)
_official_cache = {}  # url -> photo | None


def _download_bytes(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        img_bytes = resp.read()
        content_type = resp.headers.get_content_type() or "image/jpeg"
    return f"data:{content_type};base64,{base64.b64encode(img_bytes).decode()}"


def _download_photo(r):
    data_uri = _download_bytes(r["urls"]["regular"])
    return {"data_uri": data_uri, "credit_name": r["user"]["name"], "kind": "unsplash"}


def download_official(entry):
    """공공누리 등 자유이용이 확인된 정부기관·공공기관 이미지를 그대로 받아온다.
    entry: {"url": "...", "credit": "국가유산청 · 공공누리 제1유형"}
    반드시 원문 페이지에서 공공누리 마크·라이선스 유형을 사람이 직접 확인한 뒤에만 써야 한다.
    """
    url = entry.get("url")
    if not url:
        return None
    if url in _official_cache:
        return _official_cache[url]
    photo = None
    try:
        data_uri = _download_bytes(url)
        photo = {"data_uri": data_uri, "credit_name": entry.get("credit") or "", "kind": "official"}
    except Exception as e:
        print(f"    [official] 다운로드 실패({url!r}): {e}", file=sys.stderr)
    _official_cache[url] = photo
    return photo


def search_unsplash(query, count=1):
    """query로 최대 count장의 서로 다른 사진을 받아온다. 결과는 관련도순(1순위가 먼저)."""
    # Playwright의 크로미움은 이 환경의 HTTPS 프록시(커스텀 CA)를 신뢰하지 않아
    # 원격 url()을 직접 불러오지 못한다. 그래서 여기서 파이썬으로 사진을 미리
    # 내려받아 base64 data URI로 만들고, HTML에는 그 데이터를 그대로 박아 넣는다.
    if not UNSPLASH_KEY or not query:
        return []
    cache_key = (query, count)
    if cache_key in _photo_cache:
        return _photo_cache[cache_key]
    params = urllib.parse.urlencode({
        "query": query, "orientation": "portrait", "per_page": max(1, count),
        "client_id": UNSPLASH_KEY,
    })
    search_url = f"https://api.unsplash.com/search/photos?{params}"
    photos = []
    try:
        with urllib.request.urlopen(search_url, timeout=15) as resp:
            data = json.load(resp)
        for r in (data.get("results") or [])[:count]:
            try:
                photos.append(_download_photo(r))
            except Exception as e:
                print(f"    [unsplash] 사진 다운로드 실패({query!r}): {e}", file=sys.stderr)
    except Exception as e:
        print(f"    [unsplash] 검색 실패({query!r}): {e}", file=sys.stderr)
    _photo_cache[cache_key] = photos
    return photos


def credit_block(photo):
    """사진 출처 표시. Unsplash 사진에는 '기사와 무관한 이미지'라는 문구를 함께 남긴다."""
    if not photo:
        return ""
    if photo.get("kind") == "official":
        return f'<div class="foot"><div class="credit">ⓒ {esc(photo["credit_name"])}</div></div>'
    return (
        '<div class="foot">'
        f'<div class="credit">ⓒ {esc(photo["credit_name"])} / Unsplash</div>'
        '<div class="disclaimer">기사 내용과 무관한 이미지입니다</div>'
        '</div>'
    )


def photo_bg(photo):
    return f"""background-color:{INK};
    background-image:
      linear-gradient(160deg, rgba(159,15,31,.22) 0%, rgba(11,11,12,0) 45%),
      url('{photo["data_uri"]}');
    background-size:cover;background-position:center;"""


# ------------------------------------------------------------------ 배경 3종 (폴백)
# 사진 대신 브랜드 톤(블랙 · 딥레드 · 포인트레드)으로 만든 추상 건축 그래픽.
# 매체 사진을 쓰지 않아 저작권 문제 없이 카드뉴스 전용으로 반복 사용한다.
BACKGROUNDS = [
    # 1. 블루프린트 그리드
    f"""background-color:{INK};
    background-image:
      repeating-linear-gradient(0deg, rgba(255,77,26,.07) 0 1px, transparent 1px 64px),
      repeating-linear-gradient(90deg, rgba(255,77,26,.07) 0 1px, transparent 1px 64px),
      radial-gradient(120% 90% at 15% 8%, rgba(159,15,31,.55), transparent 60%),
      radial-gradient(90% 70% at 100% 100%, rgba(255,77,26,.18), transparent 55%);""",
    # 2. 딥레드 대각 그라디언트 + 가는 대각선
    f"""background-color:{RED};
    background-image:
      repeating-linear-gradient(135deg, rgba(255,255,255,.045) 0 2px, transparent 2px 26px),
      linear-gradient(160deg, {RED} 0%, {INK} 78%);""",
    # 3. 굵은 기하학 스트로크 (HA 마크 모티프의 추상화)
    f"""background-color:{INK};
    background-image:
      linear-gradient(100deg, transparent 42%, rgba(255,77,26,.85) 42% 46%, transparent 46%),
      linear-gradient(100deg, transparent 58%, rgba(242,211,177,.14) 58% 63%, transparent 63%),
      radial-gradient(85% 65% at 85% 15%, rgba(159,15,31,.65), transparent 60%);""",
]

VIGNETTE = (
    "background-image:linear-gradient(180deg, rgba(11,11,12,0) 38%, rgba(11,11,12,.55) 62%, "
    "rgba(11,11,12,.96) 100%);"
)
# 사진 배경은 위쪽이 밝을 수 있어(하늘 등) 상단 브랜드바 가독성을 위해 위도 함께 어둡게 깐다.
PHOTO_VIGNETTE = (
    "background-image:linear-gradient(180deg, rgba(11,11,12,.6) 0%, rgba(11,11,12,0) 20%, "
    "rgba(11,11,12,0) 38%, rgba(11,11,12,.55) 62%, rgba(11,11,12,.96) 100%);"
)


def esc(s):
    import html as _html
    return _html.escape(str(s or ""))


def cover_slide_html(item, day, total, photo=None):
    bg = photo_bg(photo) if photo else BACKGROUNDS[item.get("bg", 1) % len(BACKGROUNDS)]
    vign = PHOTO_VIGNETTE if photo else VIGNETTE
    slide = (item.get("slides") or [{}])[0]
    heading = esc(slide.get("heading") or item.get("title") or "").replace("\n", "<br>")
    sub = esc(slide.get("body") or "")
    tag = esc(item.get("tag") or "MAGAZINE")
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    credit_html = credit_block(photo)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden;font-family:{FONT_FAMILY}}}
  .stage{{position:relative;width:100%;height:100%;{bg}}}
  .vign{{position:absolute;inset:0;{vign}}}
  .eyebrow{{
    position:absolute;top:64px;left:64px;right:64px;
    display:flex;justify-content:space-between;align-items:center;
  }}
  .eyebrow .brand{{color:#fff;font-weight:900;font-size:23px;letter-spacing:.05em}}
  .eyebrow .brand b{{color:{HOT}}}
  .eyebrow .tag{{
    color:#fff;font-weight:800;font-size:16px;letter-spacing:.22em;
    border:1.5px solid rgba(255,255,255,.55);padding:7px 16px;border-radius:999px;
  }}
  .bottom{{position:absolute;left:64px;right:64px;bottom:72px;color:#fff}}
  .bottom h1{{
    font-size:66px;font-weight:900;line-height:1.24;letter-spacing:-.02em;
    text-shadow:0 2px 18px rgba(0,0,0,.35);
  }}
  .bottom .sub{{margin-top:22px;font-size:26px;font-weight:600;line-height:1.55;color:rgba(255,255,255,.86);
    max-width:880px;}}
  .rule{{width:64px;height:5px;background:{HOT};margin-bottom:26px}}
  .foot{{
    position:absolute;left:64px;right:64px;bottom:34px;
    font-size:15px;color:rgba(255,255,255,.6);font-weight:700;letter-spacing:.06em;
  }}
  .foot .disclaimer{{margin-top:4px;font-size:12px;font-weight:600;color:rgba(255,255,255,.4);letter-spacing:.02em}}
</style></head><body>
  <div class="stage">
    <div class="vign"></div>
    <div class="eyebrow">
      <div class="brand">HUEY <b>ARCHI</b> MAGAZINE</div>
      <div class="tag">{tag}</div>
    </div>
    <div class="bottom">
      <div class="rule"></div>
      <h1>{heading}</h1>
      {sub_html}
    </div>
    {credit_html}
  </div>
</body></html>"""


def content_slide_html(item, slide, idx, total, photo=None):
    bg = photo_bg(photo) if photo else BACKGROUNDS[item.get("bg", 1) % len(BACKGROUNDS)]
    vign = PHOTO_VIGNETTE if photo else VIGNETTE
    heading = esc(slide.get("heading") or "")
    body = esc(slide.get("body") or "").replace("\n", "<br><br>")
    heading_html = f'<div class="head">{heading}</div>' if heading else ""
    credit_html = credit_block(photo)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden;font-family:{FONT_FAMILY}}}
  .stage{{position:relative;width:100%;height:100%;{bg}}}
  .vign{{position:absolute;inset:0;{vign}}}
  .top{{
    position:absolute;top:56px;left:64px;right:64px;
    display:flex;justify-content:space-between;align-items:center;
  }}
  .top .brand{{color:rgba(255,255,255,.82);font-weight:800;font-size:16px;letter-spacing:.14em}}
  .top .brand b{{color:{HOT}}}
  .top .page{{color:rgba(255,255,255,.6);font-weight:700;font-size:16px;letter-spacing:.08em}}
  .bottom{{position:absolute;left:64px;right:64px;bottom:76px;color:#fff}}
  .rule{{width:52px;height:5px;background:{HOT};margin-bottom:22px}}
  .head{{font-size:30px;font-weight:800;letter-spacing:.02em;color:{HOT};margin-bottom:16px}}
  .body{{font-size:34px;font-weight:700;line-height:1.56;letter-spacing:-.015em;
    text-shadow:0 2px 16px rgba(0,0,0,.3);}}
  .foot{{position:absolute;left:64px;right:64px;bottom:34px;font-size:13px;font-weight:700;
    letter-spacing:.04em;color:rgba(255,255,255,.55)}}
  .foot .disclaimer{{margin-top:4px;font-size:11px;font-weight:600;color:rgba(255,255,255,.38);letter-spacing:.02em}}
</style></head><body>
  <div class="stage">
    <div class="vign"></div>
    <div class="top">
      <div class="brand">HUEY <b>ARCHI</b> MAGAZINE</div>
      <div class="page">{idx + 1:02d} / {total:02d}</div>
    </div>
    <div class="bottom">
      <div class="rule"></div>
      {heading_html}
      <div class="body">{body}</div>
    </div>
    {credit_html}
  </div>
</body></html>"""


# ------------------------------------------------------------------ 공유 카드(OG)
# 카카오톡·슬랙·트위터에 링크를 붙였을 때 뜨는 1200x630 이미지.
# render.py는 표준 라이브러리 전용이라 이미지를 만들 수 없어서, Playwright를 이미 쓰는
# 여기서 하루 한 장씩 굽고 render.py는 그 경로만 <meta property="og:image">에 적는다.
OG_W, OG_H = 1200, 630


def og_card_html(headline=None, day=None, counts=None, vol=None):
    y = m = dd = ""
    if day:
        y, m, dd = day.split("-")
    datestr = f"{y}.{m}.{dd}" if day else ""
    c = counts or {}
    stat = ""
    if c:
        stat = (f'오늘의 기사 <b>{esc(c.get("total", "-"))}</b>건'
                f' · 해외 <b>{esc(c.get("intl", "-"))}</b>'
                f' / 국내 <b>{esc(c.get("kr", "-"))}</b>')
    head_html = (f'<div class="head">{esc(headline)}</div>' if headline
                 else f'<div class="head tagline-lg">건축·건설<br>데일리 브리핑</div>')
    meta_bits = " &nbsp;·&nbsp; ".join(x for x in [esc(vol) if vol else "", datestr, stat] if x)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{OG_W}px;height:{OG_H}px;overflow:hidden;font-family:{FONT_FAMILY}}}
  .stage{{position:relative;width:100%;height:100%;{BACKGROUNDS[0]}}}
  .inner{{position:absolute;inset:0;padding:56px 64px;display:flex;flex-direction:column;
          justify-content:space-between}}
  .logo{{color:#fff;font-weight:900;font-size:40px;letter-spacing:-.02em;line-height:1}}
  .logo i{{color:{HOT};font-style:normal}}
  .tag{{color:rgba(255,255,255,.62);font-size:15px;font-weight:700;letter-spacing:.28em;
        margin-top:12px}}
  .head{{color:#fff;font-weight:900;font-size:52px;line-height:1.24;letter-spacing:-.03em;
         display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;
         word-break:keep-all;overflow-wrap:break-word;
         text-shadow:0 2px 24px rgba(0,0,0,.45)}}
  .tagline-lg{{font-size:66px;line-height:1.16}}
  .rule{{width:78px;height:6px;background:{HOT};margin-bottom:26px}}
  .foot{{color:rgba(255,255,255,.78);font-size:19px;font-weight:600;letter-spacing:.01em}}
  .foot b{{color:#fff;font-weight:900}}
</style></head><body>
  <div class="stage"><div class="inner">
    <div>
      <div class="logo">HEUY<i>.</i>ARCHI</div>
      <div class="tag">DAILY ARCHITECTURE BRIEFING</div>
    </div>
    <div>
      <div class="rule"></div>
      {head_html}
    </div>
    <div class="foot">{meta_bits}</div>
  </div></div>
</body></html>"""


def shoot(browser, html_str, path, w, h):
    page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
    try:
        page.set_content(html_str, wait_until="load")
        page.evaluate("document.fonts.ready")
        page.screenshot(path=path, type="jpeg", quality=QUALITY)
    finally:
        page.close()


def render_og_image(browser, day, d):
    """cardnews/<날짜>/og.jpg — 그날 지면의 공유 카드. 카드뉴스가 없는 날도 만든다."""
    top = d.get("top") or {}
    headline = (top.get("lede") or "").replace("\n", " ").strip()
    out_dir = os.path.join(OUT, day)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"og.{EXT}")
    shoot(browser, og_card_html(headline, day, d.get("counts"), d.get("vol")), path, OG_W, OG_H)
    print(f"    {day}/og.{EXT} (공유 카드)")


def render_og_default(browser):
    """assets/og-default.jpg — 아카이브·카테고리 등 특정 지면이 없는 페이지의 공유 카드."""
    path = os.path.join(ROOT, "assets", f"og-default.{EXT}")
    shoot(browser, og_card_html(), path, OG_W, OG_H)
    print(f"  assets/og-default.{EXT} (사이트 기본 공유 카드)")


def photos_for_item(item, slides):
    """슬라이드마다 쓸 서로 다른 사진 목록을 만든다.

    우선순위:
      1. item의 "official_photos"(공공누리 등 확인된 정부·공공기관 이미지) — 앞 슬라이드부터 채운다.
         표지(0번)에 실제 취재 사진이 들어가는 가장 좋은 경우다.
      2. 슬라이드 자신에게 photo_query가 있으면 그 슬라이드만 Unsplash에서 단독 검색.
      3. 나머지는 item의 photo_query 하나로 슬라이드 수만큼 한 번에 검색한 Unsplash 결과
         (API 호출 1회)에서 순서대로 채운다.
    official_photos로 채워지지 않은 슬라이드는 전부 Unsplash(기사와 무관한 연출컷)이므로
    렌더링 시 그 사실을 알리는 문구가 자동으로 붙는다.
    """
    n = len(slides)
    photos = [None] * n
    for i, entry in enumerate(item.get("official_photos") or []):
        if i >= n:
            break
        photos[i] = download_official(entry)

    empty_idx = [i for i in range(n) if photos[i] is None]
    for i in empty_idx:
        slide_query = slides[i].get("photo_query")
        if slide_query:
            hits = search_unsplash(slide_query, count=1)
            if hits:
                photos[i] = hits[0]

    still_empty = [i for i in range(n) if photos[i] is None]
    if still_empty:
        base_query = item.get("photo_query")
        pool = search_unsplash(base_query, count=n) if base_query else []
        pool_i = 0
        for i in still_empty:
            if pool_i < len(pool):
                photos[i] = pool[pool_i]
                pool_i += 1

    # 그래도 못 채운 자리는 확보된 사진들을 순환 배정해 최소한 브랜드 그래픽보다는 낫게 한다.
    have = [p for p in photos if p]
    if have and any(p is None for p in photos):
        j = 0
        for i in range(n):
            if photos[i] is None:
                photos[i] = have[j % len(have)]
                j += 1
    return photos


def render_item(browser, day, item):
    slug = item["slug"]
    slides = item.get("slides") or []
    out_dir = os.path.join(OUT, day, slug)
    os.makedirs(out_dir, exist_ok=True)
    photos = photos_for_item(item, slides)
    n_found = len([p for p in photos if p])
    if item.get("photo_query"):
        print(f"    [unsplash] {n_found}/{len(slides)}장 확보 (기본 검색어 {item['photo_query']!r})")
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    try:
        for i, slide in enumerate(slides):
            photo = photos[i]
            html = cover_slide_html(item, day, len(slides), photo) if i == 0 else \
                content_slide_html(item, slide, i, len(slides), photo)
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            path = os.path.join(out_dir, f"{i + 1:02d}.{EXT}")
            page.screenshot(path=path, type="jpeg", quality=QUALITY)
            print(f"    {day}/{slug}/{i + 1:02d}.{EXT}" + ("" if photo else " (브랜드 그래픽 폴백)"))
    finally:
        page.close()


def load(day):
    with open(os.path.join(DATA, f"{day}.json"), encoding="utf-8") as f:
        return json.load(f)


def run(days, force, og_default=False):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            if og_default:
                render_og_default(browser)
            for day in days:
                d = load(day)

                # 공유 카드는 카드뉴스 유무와 무관하게 모든 발행일에 만든다.
                og_path = os.path.join(OUT, day, f"og.{EXT}")
                if force or not os.path.exists(og_path):
                    render_og_image(browser, day, d)

                items = d.get("cardnews") or []
                if not items:
                    continue
                for item in items:
                    slug = item["slug"]
                    out_dir = os.path.join(OUT, day, slug)
                    n = len(item.get("slides") or [])
                    already = os.path.isdir(out_dir) and len(
                        [f for f in os.listdir(out_dir) if f.endswith("." + EXT)]
                    ) == n
                    if already and not force:
                        print(f"  {day}/{slug} — 이미 렌더됨, 건너뜀 (--force로 재생성)")
                        continue
                    print(f"  {day}/{slug} 렌더 중 ({n}장)")
                    render_item(browser, day, item)
        finally:
            browser.close()


if __name__ == "__main__":
    flags = {"--force", "--og-default"}
    args = [a for a in sys.argv[1:] if a not in flags]
    force = "--force" in sys.argv[1:]
    og_default = "--og-default" in sys.argv[1:]
    if not args and not og_default:
        sys.exit("사용법: python3 cardnews.py <YYYY-MM-DD> | --all [--force] [--og-default]")
    if args and args[0] == "--all":
        days = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    else:
        days = args
    run(days, force, og_default)
