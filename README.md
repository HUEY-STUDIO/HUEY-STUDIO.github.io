# HEUY.ARCHI

**DAILY ARCHITECTURE BRIEFING** — 건축·건축설계 데일리 브리핑
편집·제작 HUEY · 매일 오전 9시(KST) 발행

🔗 <https://ks683527-gif.github.io/>

국내외 건축 전문 매체를 매일 조사해 신문 1면 형식으로 편집합니다.
해외(Dezeen, ArchDaily, designboom, Architectural Record 등) 비중을 높게 두고,
설계 실무에 영향을 주는 제도·규제 이슈를 매일 한 건 이상 배치합니다.

## 빌드

```bash
python3 render.py 2026-08-17   # 특정 날짜 발행
python3 render.py --all        # 디자인 수정 후 전체 재생성
```

의존성 없음 (Python 표준 라이브러리만 사용).

## 수정하는 곳

| 바꾸고 싶은 것 | 고칠 파일 |
| --- | --- |
| 그날 기사 내용 | `data/<날짜>.json` |
| 색·여백·글자 크기 | `assets/style.css` |
| 지면 구성·섹션 순서 | `render.py` |
| 편집 방침 | `CLAUDE.md` |

자동 생성물(`index.html`, `archive.html`, `issues/`, `issues.json`)은 직접 고치지 않습니다.

작업 지침 전문은 [CLAUDE.md](CLAUDE.md) 참조.
