# HEUY.ARCHI — 저장소 지침

건축·건축설계 데일리 브리핑 **「HEUY.ARCHI — DAILY ARCHITECTURE BRIEFING」**을
매일 아침 발행하는 GitHub Pages 사이트입니다. 편집·제작: HUEY.

공개 주소: <https://huey-studio.github.io/>

---

## 구조

```
data/<YYYY-MM-DD>.json   ← 그날의 기사 내용     (매일 새로 추가하는 유일한 파일 — cardnews 포함)
assets/style.css         ← 디자인               (모양을 바꾸려면 여기)
render.py                ← 마크업 생성기        (구조를 바꾸려면 여기, 표준 라이브러리만 사용)
cardnews.py              ← 카드뉴스 PNG 렌더러  (Playwright, render.py보다 먼저 실행)
─────────────────────────── 아래는 전부 자동 생성물, 직접 수정 금지 ───────
index.html               ← 최신호 (= "메인" 탭)
archive.html             ← 지난호 목록
issues/<YYYY-MM-DD>.html ← 날짜별 보관본
categories/<slug>.html   ← 카테고리 탭 아카이브 (전체 발행일 통틀어 topic별로 모음)
cardnews/<날짜>/<slug>/  ← 카드뉴스 PNG (1080×1350, cardnews.py 산출물)
cardnews/<날짜>/<slug>.html ← 카드뉴스 상세 페이지 (render.py 산출물)
issues.json              ← 발행 이력
```

**내용 / 디자인 / 구조가 분리되어 있습니다.**
디자인 수정은 `assets/style.css` 한 파일로 끝나고, 과거 지면에도 소급 적용됩니다
(`python3 render.py --all`).

빌드:

```bash
python3 cardnews.py 2026-08-17   # 그날 cardnews[]를 PNG로 렌더 (render.py보다 먼저)
python3 render.py 2026-08-17     # 특정 날짜
python3 render.py --all          # 전체 재생성 (CSS·구조 수정 후)
```

`render.py`는 표준 라이브러리만 사용합니다(의존성 설치 불필요). `cardnews.py`만 Playwright가
필요합니다(`pip install playwright`) — 카드뉴스가 없는 날은 건너뛰어도 됩니다.

---

## 매일 발행 작업

### 1단계 · 리서치

- 오늘 날짜는 한국 시간 기준. `TZ=Asia/Seoul date +%F`로 확인한다.
- WebSearch / WebFetch로 **최근 1~3일** 뉴스를 우선 수집한다.
- **건축설계뿐 아니라 건설업 전반**(시공·정책·산업 동향·건자재·인프라)도 취재 범위에
  포함한다. 설계 이야기만 있는 지면이 되지 않도록 한다.
- 해외: Dezeen, ArchDaily, designboom, Architectural Record, The Architect's Newspaper,
  Archinect, The Architectural Review + 건설업 전반은 ENR(Engineering News-Record),
  Construction Dive.
- **국내 비중을 적극적으로 키운다.** 국토교통부·조달청 보도자료, 대한건축사협회(kira.or.kr),
  한국건축가협회(kia.or.kr), 대한건축학회, 건축공간연구원(auri.re.kr), 서울시 도시공간본부,
  국내 건축전문지 + 건설업 전반은 대한건설협회(cak.or.kr), 건설경제, 국토일보.
- **설계공모(topic="설계공모") 전용 출처.** 국내 비중을 우선적으로 채운다:
  - 국내: **서울시 설계공모 홈페이지**(project.seoul.go.kr), **나라장터**(조달청) 건축 설계공모
    공고 — 매일 우선 확인
  - 해외 공모 플랫폼: Bustler, Buildner, ArchDaily Competitions, Young Architects
    Competitions(YAC), eVolo Magazine
  - 국제기구·유럽: UIA(국제건축가연맹) Competitions, TED(Tenders Electronic Daily, EU 조달
    시스템), Competitions.archi
  - 일본: 建築（Kenchiku）공모전 섹션, JETRO 정부조달 정보(영문/일문)
- 분량 목표
  - `top` 1건 (그날 가장 큰 뉴스)
  - `side` 1건 — **설계 실무에 영향을 주는 제도·규제·기술 이슈를 반드시 배치**
  - `intl_feature` 2건, `intl_grid` 4건, **`korea` 3~5건**, `briefs` 6~9건
  - **설계공모 최소 2건** (국내 우선 확보 — 가능하면 국내 2건 이상 + 해외 1건 이상).
    `korea`/`intl_feature`/`intl_grid` 중 알맞은 배열에 넣고 `topic: "설계공모"`만 붙이면
    된다 — 렌더링 시 자동으로 별도 섹션에 모인다 (아래 참조)
  - `teasers` 4건 (단신·수상 등에서 뽑아 상단 스트립에 배치)
  - 국내 기사가 목표치에 못 미치면 국내 매체를 추가로 검색해서라도 채운다

### 2단계 · 이미지 URL 확보

각 주요 기사 페이지를 WebFetch하면서 프롬프트에
**"이 기사의 이미지 URL을 모두 나열해줘"** 를 넣어 대표 이미지를 얻는다.

- Dezeen: `https://static.dezeen.com/.../*_hero-852x479.jpg` 형태가 적합
- ArchDaily: `https://images.adsttc.com/.../large_jpg/...` 형태가 적합

이미지를 못 구하면 해당 기사의 `image`를 비워둔다.
`render.py`가 매체명 플레이스홀더로 대체하고, `korea` 항목은 자동으로 텍스트 카드가 된다.

> **URL은 절대 지어내지 않는다.** 실제 검색·페치 결과에서 확인된 것만 쓴다.
> 확인되지 않은 기사는 지면에서 뺀다.

### 3단계 · JSON 작성

`data/<오늘날짜>.json`을 만든다. 스키마는 아래 참조.
가장 최근 날짜 파일을 복사해서 내용만 바꾸는 방식이 가장 안전하다.

- `vol`은 직전 호에서 1 증가 (`VOL.01  NO.001` → `NO.002`)
- `counts`는 실제 기사 수와 맞춘다
- 본문 안에서 **핵심 수치·고유명사**는 `**강조**` 표기 → `<b>`로 변환된다
- 문장은 한국어. 기사 요약은 카드당 2~3문장, 톱기사는 4문단 내외
- **모든 기사(top, side, intl_feature[], intl_grid[], korea[], briefs[])에 `topic` 필드를
  반드시 채운다.** 아래 "카테고리 탭" 절 참조. `topic`은 화면에 안 보이는 분류용 필드이며,
  카드에 보이는 `kicker`(자유 텍스트)와는 별개다

### 4단계 · 빌드 & 배포

```bash
python3 render.py <오늘날짜>
git add -A
git commit -m "<오늘날짜> 발행"
git push
```

GitHub Pages가 1~2분 뒤 반영한다.

### 5단계 · 검증

- `index.html`에 오늘 날짜가 들어갔는지
- `archive.html` 항목 수가 하나 늘었는지
- 외부 이미지 URL이 실제로 200을 반환하는지 (`curl -sIL -o /dev/null -w "%{http_code}"`)

---

## 카테고리 탭

지면 상단 `catbar`는 실제 내비게이션이다. 8개 탭:

| 탭 라벨 | 슬러그 | 성격 |
|---|---|---|
| 메인 | (index.html) | 오늘자 지면 — TOP STORY·해외·국내·설계공모·단신 순서 |
| 제도규제 | `regulation` | topic="제도규제" 전체 발행일 아카이브 |
| 프로젝트 | `projects` | topic="프로젝트" |
| 도시재생 | `urban-regen` | topic="도시재생" |
| 재난유산 | `disaster-heritage` | topic="재난유산" |
| 국내 | `korea` | `korea[]` 섹션 소속 기사 전체 (topic 무관, origin 기준) |
| 설계공모 | `competitions` | topic="설계공모" |
| 수상 | `awards` | topic="수상" |

**메인을 제외한 7개 탭은 `render.py`가 `data/*.json` 전체를 다시 스캔해 매 빌드마다
자동 재생성**한다(`categories/<slug>.html`). 손으로 만들 필요 없다 — `data/<날짜>.json`에
기사와 `topic`만 정확히 넣으면 알아서 해당 탭에 실린다.

**메인 페이지에서도 `topic: "설계공모"`인 기사는 자동으로 분리된다.** `korea`/`intl_feature`/
`intl_grid` 어디에 넣었든, 렌더링 시 `render.py`가 그 안에서 골라내 "국내" 섹션 뒤 별도
"설계공모" 섹션으로 옮겨 보여준다(중복 노출 없음 — 원래 섹션에는 안 나온다). 그러니 그냥
알맞은 배열에 넣고 `topic`만 정확히 채우면 된다. 카테고리 아카이브(`categories/korea.html`
등)는 이 분리와 무관하게 원본 배열 그대로 집계하므로, `korea[]`에 넣은 설계공모 기사는
"국내" 탭과 "설계공모" 탭 양쪽에 정상적으로 실린다.

`topic` 값 6개와 판정 규칙:

- `"제도규제"` — 법·정책·규제·소송 등. side 박스는 항상 이 값
- `"프로젝트"` — 준공·설계 발표·전시·서평 등 나머지 전부. **애매하면 이 값으로 폴백**
- `"도시재생"` — 도시재생·리버프론트·공공공간 재편
- `"재난유산"` — 재해 피해/복구, 문화유산 등재·보존
- `"설계공모"` — 공모 시행/접수 공고 (수상자 미발표 상태)
- `"수상"` — 수상자·선정 결과 발표

"국내" 탭은 별도 필드 없이 `korea[]` 배열 소속 여부로만 결정된다. `korea[]`에 넣은 기사도
`topic`은 정상적으로 채워야 하며, 그러면 국내 탭과 해당 topic 탭 양쪽에 동시에 실린다.

---

## data JSON 스키마

```jsonc
{
  "vol": "VOL.01  NO.001",
  "editor": "HUEY",
  "counts": { "total": 19, "intl": 15, "kr": 4 },
  "outlets": ["Dezeen", "ArchDaily", "..."],        // 푸터 출처 목록

  "teasers": [                                       // 상단 4칸, 정확히 4개
    { "title": "...", "desc": "한 줄", "label": "AWARDS" }
  ],

  "top": {                                           // 톱기사
    "kicker": "TOP STORY · 산업건축",
    "lede": "큰 제목 문장",
    "lede_em": "이 부분만 빨갛게",                    // lede 안에 그대로 포함된 부분 문자열
    "image": "https://...", "image_label": "DEZEEN",
    "caption": "사진 설명 ⓒ 저작권자",
    "body": ["문단1", "문단2", "문단3", "문단4"],      // 2단 조판, 첫 글자 드롭캡
    "source": { "outlet": "Dezeen", "links": [{ "text": "...", "url": "..." }] },
    "topic": "프로젝트"                                // 필수. 헤드라인 클릭 시 source 첫 링크로 이동
  },

  "side": {                                          // 우측 제도·규제 박스
    "label": "실무 직결 · 제도/규제",
    "image": "...", "image_label": "...",
    "title": "...",
    "body": ["팩트 박스 위 문단"],
    "facts": ["적용: ...", "면제: ...", "제재: 최대 **1,500만 유로**"],
    "body_after": ["팩트 박스 아래 문단"],
    "source": { ... },
    "topic": "제도규제"                                // side는 항상 이 값
  },

  "intl_feature": [ /* 2건 — 헤드라인 아래 이미지 좌 / 본문 우 */
    { "kicker": "...", "title": "...", "image": "...", "image_label": "...",
      "body": ["...", "..."], "source": { ... }, "topic": "프로젝트" }
  ],

  "intl_grid": [ /* 4건 — 이미지 위 / 본문 아래 */
    { "kicker": "...", "title": "...", "image": "...", "image_label": "...",
      "body": ["..."], "source": { ... }, "topic": "프로젝트" }
  ],

  "korea": [ /* 3~5건 — image 없으면 좌측 오렌지 보더 텍스트 카드 */
    { "kicker": "...", "title": "...", "body": ["..."], "source": { ... }, "topic": "설계공모" }
  ],

  "briefs": [ /* 6~9건 — 3열 단신 */
    { "title": "...", "body": "두 줄 요약", "source": { ... }, "topic": "수상" }
  ]
}
```

`source`는 매체가 둘 이상이면 배열로 넣는다:

```jsonc
"source": [
  { "outlet": "Dezeen",    "links": [{ "text": "기사", "url": "..." }] },
  { "outlet": "ArchDaily", "links": [{ "text": "기사", "url": "..." }] }
]
```

---

## 카드뉴스 (HUEY ARCHI MAGAZINE)

인스타그램 카드뉴스 형식(1080×1350, 4:5 세로형)으로 그날 가장 비중 있는 뉴스 최대 3건을
카드뉴스로 만든다. 메인 페이지 TOP STORY 바로 위에 3개 타일로 나열되고, 클릭하면
`cardnews/<날짜>/<slug>.html` 상세 페이지에서 캐러셀로 크게 볼 수 있다.

**파이프라인**: `data/<날짜>.json`의 `cardnews[]`를 채운 뒤, `render.py`보다 **먼저**
`cardnews.py`를 돌려 PNG를 만들어야 한다.

```bash
python3 cardnews.py <날짜>   # cardnews[] → cardnews/<날짜>/<slug>/01.png..0N.png
python3 render.py <날짜>     # 웹페이지(타일·상세페이지) 생성
```

### data JSON의 `cardnews[]` 스키마

```jsonc
"cardnews": [
  {
    "slug": "libeskind-daechi-celestial",       // URL-safe, 영문 소문자-하이픈
    "tag": "PROJECT",                            // 표지·타일에 보이는 짧은 라벨
    "title": "강남 한복판에 뜨는 49층 '셀레스티얼'", // 타일/상세페이지 제목(웹 UI용)
    "ref": { "section": "top" },                 // 원본 기사 위치 — 출처·원문 링크를 여기서 가져온다
    // ref.section: "top" | "side" | "intl_feature" | "intl_grid" | "korea" | "briefs"
    // top/side가 아니면 "index"(0-based)도 같이 적는다: { "section": "korea", "index": 0 }
    "bg": 0,                                      // 배경 그래픽 0~2 (Unsplash 검색이 아예 안 될 때만 쓰는 최종 폴백)
    "photo_query": "temple wood restoration",     // 영문 검색어 — 이 하나로 슬라이드 수만큼 서로 다른 사진을 한 번에 받아온다
    "slides": [
      // 슬라이드[0] = 표지. heading은 큰 제목(\n으로 줄바꿈), body는 부제 한 줄.
      // 표지에는 검색 결과 1순위(가장 관련도 높은 사진)가 자동 배정된다.
      { "heading": "강남 한복판에\n뜨는 49층 타워", "body": "스튜디오 리베스킨드가 그린 대치쌍용의 새 얼굴" },
      // 슬라이드[1..] = 본문. heading은 소제목(WHAT/SCALE류 짧은 라벨), body는 2~3문장.
      // 이 슬라이드만 item의 photo_query와 확연히 다른 소재를 다룬다면
      // "photo_query"를 슬라이드 객체 안에 따로 넣어 그 슬라이드만 단독 검색하게 할 수 있다.
      { "heading": "WHAT", "body": "..." }
    ]
  }
]
```

- 슬라이드는 3~8장. 기사 본문을 그대로 옮기지 말고 다시 읽고 슬라이드 단위로 재구성할 것
  (표지 1장 + 핵심 포인트별 3~6장 권장).
- `ref`가 가리키는 기사는 `data/<날짜>.json` 안에 **이미 존재해야** 한다 — 카드뉴스는 새 취재가
  아니라 그날 지면 기사 중 하나를 다시 편집한 것.
- 배경 사진은 **Unsplash**에서만 가져온다. item에 영문 검색어를 `photo_query`로 채우면
  `cardnews.py`가 그 검색어로 슬라이드 수만큼 서로 다른 사진을 API 호출 1회로 받아와
  슬라이드마다 다르게 배정한다(같은 사진 반복 금지). 검색 결과 1순위는 항상 표지(맨 앞
  슬라이드)에 들어가 카드뉴스의 대표 이미지 역할을 한다. 슬라이드 각각의 소재 차이를 더
  살리고 싶으면 그 슬라이드 객체 안에 `photo_query`를 따로 넣어 단독 검색시킬 수 있다 —
  다만 Unsplash 무료(Demo) API는 **시간당 50회**로 제한되므로, item당 기본 검색 1회
  외에 슬라이드별 단독 검색은 꼭 필요한 곳에만 아껴 쓴다(하루 카드뉴스 3건이면 기본 3회로
  충분히 여유롭다). 사진마다 아래에 촬영자 크레딧("ⓒ 이름 / Unsplash")이 자동으로 붙는다.
  `UNSPLASH_ACCESS_KEY` 환경변수가 필요하며, 키가 없거나 검색 결과가 없으면 `bg`로 지정한
  브랜드 그래픽(블랙·딥레드·포인트레드 추상 패턴)으로 자동 폴백한다. **매체(Dezeen·ArchDaily
  등) 사진은 여전히 카드뉴스 배경으로 쓰지 않는다** — 핫링크가 아니라 이미지를 그대로 복제해
  재배포하는 셈이라 저작권 리스크가 사이트 임베딩보다 훨씬 크다. Unsplash는 라이선스상 출처
  표기 없이도 재배포·상업적 이용이 자유로워 이 리스크가 없다.
- 카드뉴스가 없는 날은 `cardnews` 필드를 아예 생략하면 된다 — 섹션 자체가 안 보인다.

---

## 브랜드 규칙

- 제호는 **HEUY.ARCHI** — 가운데 점(`.`)만 포인트 레드 `#FF4D1A`, 나머지는 블랙
- 태그라인 `DAILY ARCHITECTURE BRIEFING`
- 디자인 의도: 볼드한 산세리프로 미니멀하면서 강렬한 현대 건축 저널.
  레드 닷은 건축의 그리드 포인트와 데일리 이슈의 명확성을 상징
- 글꼴은 Pretendard(윤고딕 계열) 전용. **명조 사용 금지**
- 팔레트

  | 변수 | 값 | 용도 |
  |---|---|---|
  | `--ink` | `#0B0B0C` | 제목·괘선·검정 바 |
  | `--ink-2` | `#2E2A29` | 본문 |
  | `--ink-3` | `#7A716B` | 캡션·출처 |
  | `--red` | `#9F0F1F` | 킥커·드롭캡 |
  | `--hot` | `#FF4D1A` | 레드 닷·국내 섹션·강조 |
  | `--sand` | `#F2D3B1` | 핵심팩트 박스 |
  | `--paper` | `#EFE3D2` | 바깥 신문지 |
  | `--sheet` | `#FCF7F0` | 지면 |

---

## 하지 말 것

- `index.html` · `archive.html` · `issues/*.html` · `issues.json` · `categories/*.html` ·
  `cardnews/*.html` 직접 수정 (다음 빌드에서 덮어써진다. 반드시 `data/*.json`이나
  `assets/style.css`를 고칠 것)
- 확인되지 않은 기사 URL·이미지 URL 사용
- 이미지 파일을 저장소에 복사 (각 매체 URL을 그대로 링크한다) — 단, 카드뉴스 PNG(`cardnews/**/*.png`)는
  `cardnews.py`가 만드는 우리 자체 그래픽이라 예외. 매체 사진을 카드뉴스 배경으로 쓰지 않는다.
- 기사에 `topic` 필드를 빠뜨리는 것 (카테고리 탭 아카이브에서 누락된다)
- 카드뉴스의 `ref`가 그날 `data/<날짜>.json`에 실제로 없는 기사를 가리키게 두는 것
