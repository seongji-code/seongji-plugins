# seongji-plugins

개인용 Claude Code 플러그인 모음.

## create-wallpaper

핸드폰 **화면 스크린샷 1장** + 그 화면을 넣을 **사진 1장**을 주면,
화면을 8개 언어(ko ja zh-TW ms en-US en-GB fr vi)로 다시 그리고
사진 속 폰에 원근을 맞춰 합성해 16장을 한 번에 뽑는다.

이미지 생성 모델은 쓰지 않는다. 폰트 렌더링과 기하 합성만 한다 — 그래야 잔글씨가 안 뭉갠다.

### 설치

```bash
# Claude Code 안에서
/plugin marketplace add seongji-code/seongji-plugins
/plugin install create-wallpaper@seongji-plugins
```

설치한 뒤 **처음 한 번은 환경 점검을 돌린다.**

```bash
python3 ~/.claude/plugins/cache/seongji-plugins/create-wallpaper/*/skills/create-wallpaper/scripts/doctor.py
```

빠진 폰트·패키지와 받는 곳을 알려 준다.

### 쓰는 법

```text
/create-wallpaper <화면.png 경로> <사진.png 경로>
```

이미지는 **파일 경로**로 줘야 한다. 채팅에 붙여넣으면 사람은 볼 수 있어도 스크립트가 못 읽는다.
터미널에 파일을 드래그 앤 드롭하면 경로가 들어간다.

결과는 `<결과폴더>/YYYYMMDD/` 에 `화면_{언어}.png` 8장 + `합성_{언어}.png` 8장.
`<결과폴더>` 는 환경변수 `CREATE_WALLPAPER_OUT` → `~/Desktop/홍보` → 현재 작업 폴더 순으로 정해진다.

### 필요한 것

- **macOS 전용.** 날짜 표기 검증에 `swift`(Foundation/CLDR)를, 날짜 줄에 macOS 시스템 폰트를 쓴다.
- 파이썬 패키지: `opencv-python` `Pillow` `numpy` `fonttools`
- 폰트 6종 — **아래 라이선스 사정으로 저장소에 같이 넣지 못한다. 각자 설치해야 한다.**

### 폰트와 라이선스

`doctor.py` 가 없는 것만 골라 받는 곳을 알려 주지만, 미리 정리하면 이렇다.

| 폰트 | 쓰이는 곳 | 라이선스 | 받는 곳 |
|---|---|---|---|
| 그리운 프롬솔 | 한국어 본문 | 상업적 사용 O / **폰트파일 재배포·수정 X** | <https://www.griun.co.kr/fonts/fromsol> |
| 온글잎 행복한맹쿼카체 | 한국어 폴백(`·` 등) | VoyagerX 자체 / 수정·판매 X | 눈누에서 검색 |
| Shin Retro Maru Gothic (Bold·Medium) | 일본어 | SIL OFL 1.1 | <https://typographish.booth.pm/items/4607768> |
| Resource Han Rounded CN (Bold·Medium) | 번체·라틴·베트남어 | SIL OFL 1.1 | <https://github.com/CyanoHao/Resource-Han-Rounded/releases> |
| SF Pro | 시계 위 날짜 줄(라틴) | Apple / **재배포 X** | <https://developer.apple.com/fonts/> |
| Apple SD Gothic Neo · 히라기노 · PingFang | 날짜 줄(한·일·번체) | macOS 동봉 | 기본 설치 |

**SF Pro 는 용도 제한이 있다.** 애플 라이선스는 "애플 OS에서 도는 소프트웨어의 UI 목업 제작"으로
용도를 한정하고, 별도로 artwork·웹 콘텐츠 등 작업물 제작에 쓰지 말라는 문구도 둔다.
이 스킬이 만드는 것은 iOS 잠금화면 목업이지만, 그 결과물을 홍보물로 쓸 때 어디까지 허용되는지는
쓰는 쪽에서 확인해야 한다.

폰트 세트를 바꾸고 싶으면 `skills/create-wallpaper/scripts/textkit.py` 의 `FONTS` 만 고치면 된다.

### 만들면서 걸러낸 것들

`skills/create-wallpaper/references/실측과-함정.md` 에 실측값과 실패 사례를 적어 뒀다.
새 화면·새 사진으로 작업할 때 같은 함정에 다시 빠지지 않으려고 남긴 기록이다.

## 라이선스

MIT (플러그인 코드에 한함). 폰트는 각 폰트의 라이선스를 따른다.
