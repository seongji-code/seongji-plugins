// 잠금화면 날짜 줄과 캘린더 요일 헤더를 macOS Foundation(CLDR)에 물어본다.
// iOS 와 같은 데이터라 결과가 곧 실제 iOS 표기다. 직관으로 찍으면 반드시 틀린다.
//
//   swift datecheck.swift 2026 9 7
//
// 날짜 줄  = setLocalizedDateFormatFromTemplate("EEEEMMMMd")
// 요일 헤더 = veryShortWeekdaySymbols   (shortWeekdaySymbols 아님)
import Foundation

let a = CommandLine.arguments
let y = a.count > 1 ? Int(a[1])! : 2026
let m = a.count > 2 ? Int(a[2])! : 9
let dd = a.count > 3 ? Int(a[3])! : 7

let ids = ["ko": "ko_KR", "ja": "ja_JP", "zh-TW": "zh_TW", "ms": "ms_MY",
           "en-US": "en_US", "en-GB": "en_GB", "fr": "fr_FR", "vi": "vi_VN"]
let order = ["ko", "ja", "zh-TW", "ms", "en-US", "en-GB", "fr", "vi"]

let cal = Calendar(identifier: .gregorian)
let date = cal.date(from: DateComponents(year: y, month: m, day: dd))!

print("기준일 \(y)-\(m)-\(dd)\n")
for k in order {
    let loc = Locale(identifier: ids[k]!)
    let f = DateFormatter(); f.locale = loc
    f.setLocalizedDateFormatFromTemplate("EEEEMMMMd")
    let s = DateFormatter(); s.locale = loc
    let wd = s.veryShortWeekdaySymbols!.joined(separator: " ")
    print(String(format: "%-6@", k as NSString), "날짜줄: \(f.string(from: date))")
    print("       요일:   \(wd)")
}
