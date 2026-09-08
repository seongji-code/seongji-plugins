# seongji-plugins

개인용 Claude Code 플러그인 모음. 지금은 `create-wallpaper` 하나 들어 있다.

---

# create-wallpaper

**화면 스크린샷 한 장으로 8개 언어 홍보 이미지 16장을 뽑는다.**

주는 것

- 다국어로 바꿀 **핸드폰 화면 스크린샷** 1장
- 그 화면을 넣을 **사진** 1장 (폰을 든 손, 책상 위 등)

받는 것 — `화면_{언어}.png` 8장 + `합성_{언어}.png` 8장

> 한국어 · 日本語 · 繁體中文 · Bahasa Melayu · English (US) · English (UK) · Français · Tiếng Việt

**이미지 생성 AI를 쓰지 않는다.** 화면 글자를 폰트로 다시 그리고, 사진 속 폰 화면에 원근을
맞춰 붙일 뿐이다. 생성 모델로 만들면 잔글씨가 뭉개져서 홍보물로 못 쓴다.

날짜와 요일 표기는 지어내지 않고 macOS(CLDR)에 물어본다. 그래서 `Tuesday 8 September`(영국)와
`Tuesday, September 8`(미국)처럼 눈으로는 잘 안 걸리는 차이까지 실제 iOS 표기와 같다.

---

## 처음 한 번만 하면 되는 것

### 0. macOS 인지 확인

**맥에서만 돈다.** 날짜 검증에 `swift`를, 날짜 줄에 macOS 시스템 폰트를 쓰기 때문이다.
윈도우에서는 안 된다.

### 1. 저장소 접근 권한 받기

이 저장소는 **비공개**다. `@seongji-code` 에게 본인 **GitHub 계정 이름**을 알려주고
Collaborator(Read 권한)로 초대받는다.

> 초대 전에 아래를 실행하면 "repository not found" 라고 나온다. 오타처럼 보이지만
> **권한이 없어서** 그런 것이다. GitHub은 권한 없는 비공개 저장소를 없는 것처럼 취급한다.

### 2. GitHub 인증 (터미널)

```bash
brew install gh     # 이미 있으면 건너뛴다
gh auth login       # GitHub.com → HTTPS → 브라우저 로그인
```

### 3. 설치 (Claude Code 안에서)

```text
/plugin marketplace add seongji-code/seongji-plugins
/plugin install create-wallpaper@seongji-plugins
```

### 4. 환경 점검 — 이 단계를 건너뛰지 말 것

```bash
python3 ~/.claude/plugins/cache/seongji-plugins/create-wallpaper/*/skills/create-wallpaper/scripts/doctor.py
```

빠진 폰트·패키지가 있으면 **무엇이 없고 어디서 받는지** 하나씩 알려준다.
전부 ✅ 가 뜰 때까지 채운다. 이걸 안 하면 글자가 네모(`□□□`)로 나오거나 중간에 멈춘다.

폰트는 라이선스 때문에 저장소에 같이 넣지 못했다. 아래 [폰트와 라이선스](#폰트와-라이선스) 참고.

---

## 쓰는 법

Claude Code 안에서:

```text
/create-wallpaper <화면 스크린샷 경로> <사진 경로>
```

**이미지는 반드시 파일 경로로 준다.** 채팅창에 붙여넣으면 Claude 는 볼 수 있어도 스크립트가
읽지 못한다. **파인더에서 파일을 터미널 창으로 드래그 앤 드롭**하면 경로가 그대로 입력된다.

경로를 안 주고 그냥 "이 화면 다국어로 만들어서 사진에 합성해줘" 라고 해도 스킬이 뜬다.
그러면 Claude 가 경로를 물어본다.

### 결과

```text
<결과폴더>/20260908/
  화면_ko.png  화면_ja.png  화면_zh-TW.png  화면_ms.png
  화면_en-US.png  화면_en-GB.png  화면_fr.png  화면_vi.png
  합성_ko.png  합성_ja.png  합성_zh-TW.png  합성_ms.png
  합성_en-US.png  합성_en-GB.png  합성_fr.png  합성_vi.png
  _작업/        ← 중간 파일. 결과물 아니다
```

`<결과폴더>` 는 이 순서로 정해진다.

1. 환경변수 `CREATE_WALLPAPER_OUT` (`~/.zshrc` 에 `export CREATE_WALLPAPER_OUT=~/Desktop/작업` 처럼)
2. `~/Desktop/홍보` 폴더가 있으면 거기
3. 둘 다 없으면 지금 작업 폴더

### 걸리는 시간

화면 구조를 처음 읽고 좌표를 재는 데 시간이 든다. 같은 화면으로 두 번째부터는 훨씬 빠르다.
중간에 Claude 가 **"이렇게 나왔는데 괜찮냐"** 고 그림을 보여주며 물어보는 지점이 몇 군데 있다.
눈으로 확인하고 답해주면 된다.

---

## 자주 막히는 곳

| 증상 | 원인과 해결 |
|---|---|
| `repository not found` | 저장소 초대를 아직 못 받았다. 1단계로 |
| 글자가 네모(`□□□`)로 나온다 | 폰트가 없다. `doctor.py` 실행 |
| 스크립트가 파일을 못 읽는다 | 이미지를 채팅에 붙여넣었다. 경로로 줘야 한다 |
| `~/Documents` 안 파일을 못 읽는다 | macOS 권한에 막힌다. 데스크톱이나 다른 폴더로 옮긴다 |
| 화면 가장자리에 원래 화면 색이 비친다 | 좌표가 안쪽으로 잡혔다. Claude 에게 "좌표 다시 확인해" 라고 하면 다시 잡는다 |
| 합성한 화면의 잔글씨가 뭉갰다 | 배경 사진이 작다. 더 큰 사진을 쓰거나 `--scale` 을 올린다 |

---

## 알아둘 것 (한계)

- **macOS 전용.**
- **원본 화면이 휑하면 합성으로 못 고친다.** 배경이 흰색이라 폰 안이 비어 보이는 것은
  원본 화면의 문제다. 화면을 다시 만들어야 한다.
- **화면 구조가 많이 다르면 그리는 부분을 새로 써야 한다.** 글자 크기·정렬·합성은 그대로
  재사용되지만, 위젯 배치가 다르면 좌표를 다시 잡는다. Claude 가 알아서 하지만 시간이 더 걸린다.
- **폰트 세트는 고정이다.** 원본 화면이 다른 폰트를 쓰더라도 아래 세트로 그린다.
  시리즈 전체의 통일이 우선이기 때문이다. 바꾸려면 `textkit.py` 의 `FONTS` 를 고친다.

---

## 폰트와 라이선스

**폰트 파일은 저장소에 넣지 않았다.** 6종 중 재배포가 되는 것이 2종뿐이라,
일부만 넣으면 오히려 헷갈린다. `doctor.py` 가 없는 것만 골라 받는 곳을 알려준다.

| 폰트 | 쓰이는 곳 | 라이선스 | 받는 곳 |
|---|---|---|---|
| 그리운 프롬솔 | 한국어 본문 | 상업적 사용 O / **폰트파일 재배포·수정 X** | <https://www.griun.co.kr/fonts/fromsol> |
| 온글잎 행복한맹쿼카체 | 한국어 폴백 (`·` 등) | VoyagerX 자체 / 수정·판매 X | <https://noonnu.cc> 에서 검색 |
| Shin Retro Maru Gothic (Bold·Medium) | 일본어 | SIL OFL 1.1 | <https://typographish.booth.pm/items/4607768> |
| Resource Han Rounded CN (Bold·Medium) | 번체·라틴·베트남어 | SIL OFL 1.1 | <https://github.com/CyanoHao/Resource-Han-Rounded/releases> |
| SF Pro | 시계 위 날짜 줄 (라틴) | Apple / **재배포 X** | <https://developer.apple.com/fonts/> |
| Apple SD Gothic Neo · 히라기노 · PingFang | 날짜 줄 (한·일·번체) | macOS 동봉 | 기본 설치 |

받은 폰트는 `~/Library/Fonts/` 에 넣으면 된다 (더블클릭 → "설치" 도 같다).

> **SF Pro 는 용도 제한이 있다.** 애플 라이선스는 "애플 OS에서 도는 소프트웨어의 UI 목업 제작"
> 으로 용도를 한정하고, 별도로 artwork·웹 콘텐츠 등 작업물 제작에 쓰지 말라는 문구도 둔다.
> 이 스킬이 만드는 것은 iOS 잠금화면 목업이지만, **그 결과물을 대외 홍보물로 쓸 때 어디까지
> 허용되는지는 쓰는 쪽에서 확인해야 한다.** SF Pro 는 시계 위 날짜 줄 한 줄에만 쓰인다.

---

## 고치고 싶을 때

| 하고 싶은 것 | 볼 곳 |
|---|---|
| 언어 추가·제거 | `scripts/textkit.py` 의 `LANGS`, `datecheck.swift` 의 로케일 목록 |
| 폰트 세트 변경 | `scripts/textkit.py` 의 `FONTS` |
| 작업 절차 자체 | `skills/create-wallpaper/SKILL.md` (9단계, ⚠ 는 눈으로 확인할 단계) |
| 실측값·과거에 걸러낸 실수 | `skills/create-wallpaper/references/실측과-함정.md` |

`references/실측과-함정.md` 는 지난 작업에서 실제로 틀렸던 것들을 적어 둔 문서다.
아이폰 화면 모서리 반경, 좌표 검출이 왜 어긋나는지, 반사광 처리가 옛 글자를 끌어오는 문제 같은
것들이라 새 화면·새 사진으로 작업할 때 같은 함정을 다시 밟지 않게 해준다.

고친 게 쓸 만하면 `@seongji-code` 에게 알려주거나 PR 을 보내면 된다.
반영된 뒤 각자 받는 법:

```text
/plugin marketplace update seongji-plugins
/plugin update create-wallpaper@seongji-plugins
```

스킬은 버전별 캐시에서 읽히므로, 마켓플레이스만 갱신하고 플러그인을 업데이트하지 않으면
예전 것이 그대로 돈다. 두 줄을 같이 실행한다.

---

## 라이선스

MIT (플러그인 코드에 한함). 폰트는 각 폰트의 라이선스를 따른다.
