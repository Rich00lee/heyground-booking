# Heyground Booking

헤이그라운드 회의실 예약/조회/취소 CLI (GitHub: `Rich00lee/heyground-booking`, public)

## 핵심 파일
- `heyground.py` — 메인 CLI 스크립트 (예약, 조회, 취소, 크레딧 확인)
- `docs/` — API 문서
- `README.md` — 사용법

## 인증
- 토큰 위치: `~/.config/heyground/token.json` (access_token + refresh_token + slack_webhook_url)
- **자동 갱신**: `load_token()` 호출 시 만료 1일 전이면 자동 refresh (OAuth2, client: heyground-web:foo)
- weekly_booking.py에서 401 발생 시에도 자동 갱신 재시도

## 회의실
- 서울숲점 기준, 4~10인실 매핑 완료

## 자동화
- `weekly_booking.py` — 정기 회의실 자동 예약 + Slack 리마인드
  - launchd 매일 08:07 실행 (2주 앞까지 슬롯 자동 예약)
  - plist: `~/Library/LaunchAgents/com.liveklass.heyground-booking.plist`
  - cron에서 전환 (3/25) — macOS 잠자기 시 cron 누락 문제 해결, launchd는 밀린 실행 보상
  - **맥 자동 기상**: `sudo pmset repeat wakeorpoweron MTWRFSU 08:05:00` — 매일 08:05 자동 기상 (launchd 08:07 실행 전 2분 여유). 맥 잠자기 시 launchd도 트리거 안 되기 때문에 필요. 확인: `pmset -g sched`
  - **네트워크 대응**: `wait_for_network()` — DNS 연결 재시도 (최대 5회, 30초 간격)
  - 7층 6인실 고정. 정기 회의 선호 방: M7-6C > M7-6B > M7-6A
  - 당일 예약 있으면 Slack 리마인드 (스케줄별 채널 분기)
  - 테스트: `python3 weekly_booking.py --dry`
  - 로그: `weekly_booking.log`

## 정기 스케줄 (`WEEKLY_SCHEDULE`)
| 요일 | 시간 | 용도 | 선호 방 | 리마인드 채널 |
|------|------|------|---------|----------------|
| 월 | 09:30~10:30 | 정기 회의 | M7-6C 1순위 | #사업팀-셀리더-2025 |
| 수 | 11:00~12:00 | 정기 회의 | M7-6C 1순위 | #사업팀-셀리더-2025 |

## 휴일·휴가 블랙리스트 (`EXCLUDED_DATES`)
- **취소만 하면 재예약됨** → 제외하려면 반드시 `EXCLUDED_DATES[dtl]`에 YYYY-MM-DD 등록
- 구조: `{"ax daily camp": {"2026-05-01", ...}}` — dtl별 set
- `get_target_dates`에서 `(dtl, date)` 매칭으로 슬롯 자체를 생성 안 함
- 같은 날 다른 dtl(예: 5/6 정기 회의)은 영향 없음

## Slack 연동
- Slack 앱: "리치 비서" (구 noti_SAL, App ID: A0A67JZKC1G)
- token.json webhook 키 (스케줄별 분기 라우팅):
  - `slack_webhook_url` → `#사업팀-셀리더-2025` (기본/fallback)
  - `slack_webhook_url_ax_hero_camp` → `#ax-hero-camp`
- 채널 매칭: `WEEKLY_SCHEDULE[].reminder_webhook_key` 기준 (요일+시작+종료 매칭). 스케줄에 없는 예약은 기본 webhook으로 발송
