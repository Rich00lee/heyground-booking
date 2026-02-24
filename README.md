# 헤이그라운드 회의실 예약 자동화

Claude Code에서 자연어로 헤이그라운드 회의실을 예약하는 도구입니다.

```
"내일 14시 6인실 예약해줘"  →  예약 완료! HG#2 M4-6, 14:00~15:00, 6크레딧 차감
```

## 어떻게 만들었나

### 1단계: API 역분석 (HAR 파일 분석)

헤이그라운드는 공개 API를 제공하지 않습니다. 그래서 브라우저 개발자도구(F12)의 Network 탭에서 실제 예약 과정을 HAR 파일로 캡처하고, 이 파일을 파싱해서 내부 API 엔드포인트를 역분석했습니다.

**발견된 API 5개:**

| Method | 엔드포인트 | 용도 |
|--------|-----------|------|
| `GET` | `/api/reservations/rooms/{날짜}` | 특정 날짜 전체 예약 조회 |
| `GET` | `/api/members/credit` | 잔여 크레딧 확인 |
| `POST` | `/api/reservations/credits` | 예약 전 크레딧 사전 확인 |
| `POST` | `/api/reservations` | 예약 생성 |
| `DELETE` | `/api/reservations/{코드}` | 예약 취소 |

### 2단계: 인증 방식 파악

브라우저 Local Storage에 저장된 JWT 토큰을 `Authorization: Bearer` 헤더로 전송하는 방식입니다.

### 3단계: Python CLI 스크립트

API 호출을 Python `requests` 라이브러리로 래핑한 CLI 도구(`heyground.py`)를 만들었습니다.

### 4단계: Claude Code 스킬 연결

Claude Code 스킬(`/book-room`)을 만들어서, 사용자가 자연어로 "3/5 14~16시 6인실 예약"이라고 말하면 Claude가 파싱 규칙에 따라 CLI 인자로 변환 후 실행합니다.

> **다른 사이트도 같은 방식으로 자동화하고 싶다면?** → `/reverse-api` 글로벌 스킬이 이 1~4단계 전체를 재사용 가능하게 패키징해둔 도구입니다. HAR 파일만 주면 분석부터 스킬 생성까지 가이드합니다.

```
사용자 입력: "3/5 14~16시 6인실 예약해줘"
         ↓ Claude Code가 파싱
python3 heyground.py book --date 20260305 --start 1400 --end 1600 --capacity 6
         ↓ 스크립트가 API 호출
1. GET  /api/reservations/rooms/2026-03-05  → 빈 방 확인
2. POST /api/reservations/credits           → 크레딧 확인
3. POST /api/reservations                   → 예약 실행
         ↓
"예약 완료! M5-6A, 14:00~16:00, 12크레딧 차감"
```

## 지원 기능

| 명령 | 예시 |
|------|------|
| 예약 | `"3/5 14~16시 6인 회의실 예약"` |
| 특정 방 예약 | `"3/5 14~16시 M7-6A 예약"` |
| 빈 방 조회 | `"오늘 빈방 알려줘"` |
| 내 예약 확인 | `"내 예약"` |
| 예약 취소 | `"예약 K2602230081 취소해줘"` |
| 크레딧 확인 | `"크레딧 얼마 남았어"` |

## 회의실 목록 (서울숲점, 26개)

| 층 | 4인실 | 6인실 | 8인실 | 10인실 | 기타 |
|----|-------|-------|-------|--------|------|
| 4층 | M4-4 | M4-6 | M4-8 | M4-10 | |
| 5층 | M5-4 | M5-6A, 6B, 6C | | M5-10 | |
| 6층 | M6-4 | M6-6A, 6C | | M6-10 | |
| 7층 | M7-4 | M7-6A, 6B, 6C | | M7-10 | |
| 8층 | M8-4 | M8-6A, 6B, 6C | | M8-10 | |
| 9층 | | | | M9-10 | |
| 10층 | | | | | CAMF14(14인), DEEP9(9인) |

## 설치 방법 (Claude Code 사용자)

### 1. 파일 복사

```bash
# 스크립트 복사
cp heyground.py ~/heyground-booking/heyground.py

# 스킬 복사
cp SKILL.md ~/.claude/skills/book-room/SKILL.md
```

### 2. 토큰 설정

1. Chrome에서 `member.heyground.com` 로그인
2. `F12` → Application → Local Storage → `access_token` 값 복사
3. 토큰 파일 생성:

```bash
mkdir -p ~/.config/heyground
```

`~/.config/heyground/token.json`:
```json
{
  "access_token": "여기에_복사한_토큰_붙여넣기",
  "refresh_token": "",
  "user_name": "your.email@company.com",
  "location": "seoulsoop"
}
```

### 3. 테스트

```bash
python3 ~/heyground-booking/heyground.py credit
# → 잔여 크레딧: 248
```

### 4. 사용

Claude Code에서 자연어로 말하면 됩니다:
- "내일 14시 6인실 예약해줘"
- "오늘 빈방 확인"
- "크레딧 얼마?"

## 제약사항

- **비공식 API**: 헤이그라운드가 사이트를 업데이트하면 동작이 멈출 수 있음
- **토큰 만료**: ~4개월마다 브라우저에서 새 토큰을 복사해야 함
- **서울숲점만**: 현재 서울숲점(seoulsoop) 데이터만 포함

## 기술 스택

- Python 3 + requests
- Claude Code Skill (SKILL.md)
- Heyground REST API (비공식, HAR 역분석)
- JWT Bearer Token 인증
