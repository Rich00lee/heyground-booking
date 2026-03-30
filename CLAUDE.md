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
  - launchd 매일 08:07 실행 (2주 앞까지 월/수 슬롯 자동 예약)
  - plist: `~/Library/LaunchAgents/com.liveklass.heyground-booking.plist`
  - cron에서 전환 (3/25) — macOS 잠자기 시 cron 누락 문제 해결, launchd는 밀린 실행 보상
  - **맥 자동 기상**: `sudo pmset repeat wakeorpoweron MTWRFSU 08:05:00` — 매일 08:05 자동 기상 (launchd 08:07 실행 전 2분 여유). 맥 잠자기 시 launchd도 트리거 안 되기 때문에 필요. 확인: `pmset -g sched`
  - **네트워크 대응**: `wait_for_network()` — DNS 연결 재시도 (최대 5회, 30초 간격)
  - 선호 방: M7-6C > M7-6B > M7-6A (7층 6인실)
  - 당일 예약 있으면 Slack `#사업팀-셀리더-2025`에 리마인드 발송
  - 테스트: `python3 weekly_booking.py --dry`
  - 로그: `weekly_booking.log`

## Slack 연동
- Slack 앱: "리치 비서" (구 noti_SAL, App ID: A0A67JZKC1G)
- webhook: token.json → `slack_webhook_url` 키
- 채널: 사업팀-셀리더-2025
