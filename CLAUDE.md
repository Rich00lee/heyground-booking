# Heyground Booking

헤이그라운드 회의실 예약/조회/취소 CLI (GitHub: `Rich00lee/heyground-booking`, public)

## 핵심 파일
- `heyground.py` — 메인 CLI 스크립트 (예약, 조회, 취소, 크레딧 확인)
- `docs/` — API 문서
- `README.md` — 사용법

## 인증
- 토큰 위치: `~/.config/heyground/token.json` (access_token + slack_webhook_url)
- refresh_token 갱신 로직 필요 (P1)

## 회의실
- 서울숲점 기준, 4~10인실 매핑 완료

## 자동화
- `weekly_booking.py` — 정기 회의실 자동 예약 + Slack 리마인드
  - crontab 매일 08:07 실행 (2주 앞까지 월/수 슬롯 자동 예약)
  - 선호 방: M7-6C > M7-6B > M7-6A (7층 6인실)
  - 당일 예약 있으면 Slack `#사업팀-셀리더-2025`에 리마인드 발송
  - 테스트: `python3 weekly_booking.py --dry`
  - 로그: `weekly_booking.log`

## Slack 연동
- Slack 앱: "리치 비서" (구 noti_SAL, App ID: A0A67JZKC1G)
- webhook: token.json → `slack_webhook_url` 키
- 채널: 사업팀-셀리더-2025
