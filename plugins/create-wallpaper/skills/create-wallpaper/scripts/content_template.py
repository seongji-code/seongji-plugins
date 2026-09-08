# -*- coding: utf-8 -*-
"""[템플릿] 언어별 문구 — 작업 폴더에 content.py 로 복사해 채운다.

키 구성은 화면에 맞게 바꿔도 된다. render.py 와 짝만 맞으면 된다.
지켜야 할 것:
  - date, wd 는 손으로 짓지 말고 `swift datecheck.swift <년> <월> <일>` 결과를 그대로 쓴다.
  - carrier(통신사명)는 참고용으로만 적어 둔다. 화면에는 그리지 않는다 (지운 채로 둔다).
  - 폭이 고정된 칸(칩)의 문구는 12자를 넘기지 않는다. 길면 줄여 쓴다.
    (예: Kelas Mandarin -> Mandarin, Cours de chinois -> Chinois)
"""
LOCALES = {
"ko": dict(name="한국어", carrier="LG U+",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"ja": dict(name="日本語", carrier="docomo",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"zh-TW": dict(name="繁體中文", carrier="中華電信",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"ms": dict(name="Bahasa Melayu", carrier="Maxis",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"en-US": dict(name="English (US)", carrier="AT&T",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"en-GB": dict(name="English (UK)", carrier="EE",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"fr": dict(name="Français", carrier="Orange",
  date="", wd=[], chips=[], overdue=[], sections=[]),
"vi": dict(name="Tiếng Việt", carrier="Viettel",
  date="", wd=[], chips=[], overdue=[], sections=[]),
}
