# HEUY.ARCHI — 저장소 지침

건축·건축설계 데일리 브리핑 **「HEUY.ARCHI — DAILY ARCHITECTURE BRIEFING」**을
매일 아침 발행하는 GitHub Pages 사이트입니다. 편집·제작: HUEY.

공개 주소: <https://ks683527-gif.github.io/>

---

## 구조

```
data/<YYYY-MM-DD>.json   ← 그날의 기사 내용     (매일 새로 추가하는 유일한 파일)
assets/style.css         ← 디자인               (모양을 바꾸려면 여기)
render.py                ← 마크업 생성기        (구조를 바꾸려면 여기)
─────────────────────────── 아래는 전부 자동 생성물, 직접 수정 금지 ───────
index.html               ← 최신호
archive.html             ← 지난호 목록
issues/<YYYY-MM-DD>.html ← 날짜별 보관본
issues.json              ← 발행 이력
```

**내용 / 디자인 / 구조가 분리되어 있습니다.**
디자인 수정은 `assets/style.css` 한 파일로 끝나고, 과거 지면에도 소급 적용됩니다
(`python3 render.py --all`).

빌드:

```bash
python3 render.py 2026-08-17   # 특정 날짜
python3 render.py --all        # 전체 재생성 (CSS·구조 수정 후)
```

표준 라이브러리만 사용합니다. 의존성 설치 불필요.

---

## 매일 발행 작업

### 1단계 · 리서치

- 오늘 날짜는 한국 시간 기준. `TZ=Asia/Seoul date +%F`로 확인한다.
- WebSearch / WebFetch로 **최근 1~3일** 뉴스를 우선 수집한다.
- **해외 비중을 높게** 잡는다: Dezeen, ArchDaily, designboom, Architectural Record,
  The Architect's Newspaper, Archinect, The Architectural Review.
- 국내: 국토교통부·조달청 보도자료, 대한건축사협회(kira.or.kr), 한국건축가협회(kia.or.kr),
  대한건축학회, 건축공간연구원(auri.re.kr), 서울시 도시공간본부, 국내 건축전문지.
- 분량 목표
  - `top` 1건 (그날 가장 큰 뉴스)
  - `side` 1건 — **설계 실무에 영향을 주는 제도·규제·기술 이슈를 반드시 배치**
  - `intl_feature` 2건, `intl_grid` 4건, `korea` 2~4건, `briefs` 6~9건
  - `teasers` 4건 (단신·수상 등에서 뽑아 상단 스트립에 배치)

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
    "source": { "outlet": "Dezeen", "links": [{ "text": "...", "url": "..." }] }
  },

  "side": {                                          // 우측 제도·규제 박스
    "label": "실무 직결 · 제도/규제",
    "image": "...", "image_label": "...",
    "title": "...",
    "body": ["팩트 박스 위 문단"],
    "facts": ["적용: ...", "면제: ...", "제재: 최대 **1,500만 유로**"],
    "body_after": ["팩트 박스 아래 문단"],
    "source": { ... }
  },

  "intl_feature": [ /* 2건 — 헤드라인 아래 이미지 좌 / 본문 우 */
    { "kicker": "...", "title": "...", "image": "...", "image_label": "...",
      "body": ["...", "..."], "source": { ... } }
  ],

  "intl_grid": [ /* 4건 — 이미지 위 / 본문 아래 */
    { "kicker": "...", "title": "...", "image": "...", "image_label": "...",
      "body": ["..."], "source": { ... } }
  ],

  "korea": [ /* 2~4건 — image 없으면 좌측 오렌지 보더 텍스트 카드 */
    { "kicker": "...", "title": "...", "body": ["..."], "source": { ... } }
  ],

  "briefs": [ /* 6~9건 — 3열 단신 */
    { "title": "...", "body": "두 줄 요약", "source": { ... } }
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

- `index.html` · `archive.html` · `issues/*.html` · `issues.json` 직접 수정
  (다음 빌드에서 덮어써진다. 반드시 `data/*.json`이나 `assets/style.css`를 고칠 것)
- 확인되지 않은 기사 URL·이미지 URL 사용
- 이미지 파일을 저장소에 복사 (각 매체 URL을 그대로 링크한다)
