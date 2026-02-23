# 헤이그라운드 회의실 예약 에이전트 설계

## 개요
Claude Code 스킬(`/book-room`)로 헤이그라운드 회의실을 자연어 명령으로 예약하는 에이전트

## API 엔드포인트

| Method | URL | 용도 |
|--------|-----|------|
| POST | `https://api.heyground.com/api/reservations/credits` | 크레딧 사전 확인 |
| POST | `https://api.heyground.com/api/reservations` | 예약 생성 |
| GET | `https://api.heyground.com/api/reservations/rooms/{날짜}?location={지점}` | 특정 날짜 전체 예약 조회 |
| GET | `https://api.heyground.com/api/reservations/rooms/my?location={지점}` | 내 예약 조회 |
| GET | `https://api.heyground.com/api/members/credit` | 크레딧 잔액 조회 |

## 인증
- JWT Bearer Token (Local Storage 저장)
- `Authorization: Bearer <access_token>` 헤더로 전송
- 토큰 파일: `~/.config/heyground/token.json`
- 만료 시 refresh_token으로 자동 갱신

## 예약 요청 데이터 구조

```json
{
  "pblspc_cd": "S1121M07006A",   // 회의실 코드
  "de_use": "20260223",           // 사용일 (YYYYMMDD)
  "time_use_start": "1000",       // 시작시간 (HHMM)
  "time_use_end": "1030",         // 종료시간 (HHMM)
  "dtl": "회의",                   // 예약 상세
  "memo": "",
  "dong": "1",
  "se": "0291",
  "se_nm": "M",
  "floor": "07",
  "room": "006A",
  "location": "seoulsoop"
}
```

## 회의실 코드 체계

```
S1121M07006A
│    ││  │
│    ││  └── 방 번호 (006A)
│    │└───── 층 (07)
│    └────── 타입 (M = 미팅룸)
└──────────── 지점 프리픽스 (S1121)
```

## 기능 명세

| 명령 | 동작 |
|------|------|
| `/book-room 3/5 14~16시 6인` | 빈 6인실 자동 선택 후 예약 |
| `/book-room 3/5 14~16시 M7-6A` | 특정 방 지정 예약 |
| `/book-room 오늘 빈방` | 오늘 빈 방 조회 |
| `/book-room 내 예약` | 내 예약 목록 확인 |
| `/book-room 크레딧` | 잔여 크레딧 확인 |

## 예약 플로우 (확인 단계 없음)

1. 자연어 입력 파싱 → 날짜/시간/방 타입
2. 전체 예약 조회 → 빈 방 필터링
3. 조건에 맞는 방 자동 선택
4. 바로 예약 실행
5. 결과 출력

## 기술 스택
- Python 3 + requests 라이브러리
- Claude Code 글로벌 스킬 (`~/.claude/skills/book-room/`)
- 토큰 저장: `~/.config/heyground/token.json`

## 지점 정보
- `seoulsoop` = 서울숲점 (기본값)
