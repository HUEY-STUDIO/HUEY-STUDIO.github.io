#!/usr/bin/env python3
"""
HEUY ARCHI MAGAZINE — 카드뉴스 렌더러
------------------------------------------------------------------
  python3 cardnews.py 2026-08-19     # 해당 날짜 data/*.json의 cardnews[] 전체를 PNG로 렌더
  python3 cardnews.py --all          # data/ 전체를 다시 렌더
  python3 cardnews.py 2026-08-19 --force   # 이미 있어도 다시 렌더

입력  : data/<날짜>.json 의 "cardnews" 배열
출력  : cardnews/<날짜>/<slug>/01.png ... 0N.png   (1080x1350, 인스타그램 카드뉴스 규격)

render.py(웹페이지 생성)와 분리된 스크립트입니다 — render.py는 표준 라이브러리만
쓰는 게 원칙이라, Playwright가 필요한 이미지 렌더링은 여기서 따로 합니다.
PNG를 먼저 만든 다음 render.py를 돌려야 웹페이지에서 이미지가 보입니다.

  python3 cardnews.py <날짜>
  python3 render.py <날짜>
"""

import json
import os
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "cardnews")

CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
W, H = 1080, 1350

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

# ------------------------------------------------------------------ 배경 3종
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


def esc(s):
    import html as _html
    return _html.escape(str(s or ""))


def stage_bg_style(item):
    """item에 "photo"(Unsplash 이미지 URL)가 있으면 실사 배경, 없으면 기존 브랜드 그래픽."""
    photo = item.get("photo")
    if photo:
        url = str(photo).replace("'", "%27")
        return f"background-color:{INK};background-image:url('{url}');" \
               "background-size:cover;background-position:center;"
    return BACKGROUNDS[item.get("bg", 1) % len(BACKGROUNDS)]


def credit_html(item):
    credit = item.get("photo_credit")
    if not (item.get("photo") and credit):
        return ""
    return f'<div class="credit">Photo: {esc(credit)} / Unsplash</div>'


def cover_slide_html(item, day, total):
    bg = stage_bg_style(item)
    slide = (item.get("slides") or [{}])[0]
    heading = esc(slide.get("heading") or item.get("title") or "").replace("\n", "<br>")
    sub = esc(slide.get("body") or "")
    tag = esc(item.get("tag") or "MAGAZINE")
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    credit = credit_html(item)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden;font-family:{FONT_FAMILY}}}
  .stage{{position:relative;width:100%;height:100%;{bg}}}
  .vign{{position:absolute;inset:0;{VIGNETTE}}}
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
    display:flex;justify-content:space-between;align-items:center;
    font-size:15px;color:rgba(255,255,255,.6);font-weight:700;letter-spacing:.06em;
  }}
  .credit{{
    position:absolute;right:24px;bottom:16px;
    font-size:12px;color:rgba(255,255,255,.55);font-weight:600;letter-spacing:.02em;
  }}
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
    {credit}
  </div>
</body></html>"""


def content_slide_html(item, slide, idx, total):
    bg = stage_bg_style(item)
    heading = esc(slide.get("heading") or "")
    body = esc(slide.get("body") or "").replace("\n", "<br><br>")
    heading_html = f'<div class="head">{heading}</div>' if heading else ""
    credit = credit_html(item)
    return f"""<!doctype html><html><head><meta charset="utf-8">{FONT_LINK}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden;font-family:{FONT_FAMILY}}}
  .stage{{position:relative;width:100%;height:100%;{bg}}}
  .vign{{position:absolute;inset:0;{VIGNETTE}}}
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
  .credit{{
    position:absolute;right:24px;bottom:16px;
    font-size:12px;color:rgba(255,255,255,.55);font-weight:600;letter-spacing:.02em;
  }}
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
    {credit}
  </div>
</body></html>"""


def render_item(browser, day, item):
    slug = item["slug"]
    slides = item.get("slides") or []
    out_dir = os.path.join(OUT, day, slug)
    os.makedirs(out_dir, exist_ok=True)
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    try:
        for i, slide in enumerate(slides):
            html = cover_slide_html(item, day, len(slides)) if i == 0 else \
                content_slide_html(item, slide, i, len(slides))
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            path = os.path.join(out_dir, f"{i + 1:02d}.png")
            page.screenshot(path=path)
            print(f"    {day}/{slug}/{i + 1:02d}.png")
    finally:
        page.close()


def load(day):
    with open(os.path.join(DATA, f"{day}.json"), encoding="utf-8") as f:
        return json.load(f)


def run(days, force):
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        try:
            for day in days:
                d = load(day)
                items = d.get("cardnews") or []
                if not items:
                    continue
                for item in items:
                    slug = item["slug"]
                    out_dir = os.path.join(OUT, day, slug)
                    n = len(item.get("slides") or [])
                    already = os.path.isdir(out_dir) and len(
                        [f for f in os.listdir(out_dir) if f.endswith(".png")]
                    ) == n
                    if already and not force:
                        print(f"  {day}/{slug} — 이미 렌더됨, 건너뜀 (--force로 재생성)")
                        continue
                    print(f"  {day}/{slug} 렌더 중 ({n}장)")
                    render_item(browser, day, item)
        finally:
            browser.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
    if not args:
        sys.exit("사용법: python3 cardnews.py <YYYY-MM-DD> | --all [--force]")
    if args[0] == "--all":
        days = sorted(f[:-5] for f in os.listdir(DATA) if f.endswith(".json"))
    else:
        days = args
    run(days, force)
