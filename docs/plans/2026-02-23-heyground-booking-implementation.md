# 헤이그라운드 회의실 예약 에이전트 구현 계획

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Claude Code에서 `/book-room 3/5 14~16시 6인` 같은 자연어 명령으로 헤이그라운드 회의실을 예약하는 스킬 구축

**Architecture:** Python 스크립트(`heyground.py`)가 헤이그라운드 REST API를 호출하고, Claude Code 스킬(`/book-room`)이 자연어 입력을 파싱해서 스크립트를 실행하는 2계층 구조

**Tech Stack:** Python 3 + requests, Claude Code Skill (SKILL.md)

---

## Task 1: 프로젝트 구조 + 토큰 설정

**Files:**
- Create: `~/heyground-booking/heyground.py`
- Create: `~/.config/heyground/token.json`

**Step 1: 토큰 설정 디렉토리 생성**

Run: `mkdir -p ~/.config/heyground`

**Step 2: 토큰 파일 생성**

브라우저 Local Storage에서 복사한 토큰을 저장하는 설정 파일.

`~/.config/heyground/token.json`:
```json
{
  "access_token": "(브라우저 Local Storage에서 복사)",
  "refresh_token": "(브라우저 Local Storage에서 복사)",
  "user_name": "your.email@company.com",
  "location": "seoulsoop"
}
```

**Step 3: .gitignore 생성**

`~/heyground-booking/.gitignore`:
```
__pycache__/
*.pyc
token.json
```

---

## Task 2: 핵심 Python 스크립트 — API 호출 모듈

**Files:**
- Create: `~/heyground-booking/heyground.py`

**Step 1: API 래퍼 함수 작성**

`~/heyground-booking/heyground.py`:
```python
#!/usr/bin/env python3
"""헤이그라운드 회의실 예약 CLI"""

import json
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    print("requests 라이브러리가 필요합니다: pip3 install requests")
    sys.exit(1)

# === 설정 ===
API_BASE = "https://api.heyground.com/api"
TOKEN_PATH = Path.home() / ".config" / "heyground" / "token.json"

# === 회의실 데이터 (서울숲점) ===
ROOMS = {
    "S1121M040004": {"name": "M4-4",   "floor": "04", "room": "0004", "capacity": 4},
    "S1121M040006": {"name": "M4-6",   "floor": "04", "room": "0006", "capacity": 6},
    "S1121M040008": {"name": "M4-8",   "floor": "04", "room": "0008", "capacity": 8},
    "S1121M040010": {"name": "M4-10",  "floor": "04", "room": "0010", "capacity": 10},
    "S1121M050004": {"name": "M5-4",   "floor": "05", "room": "0004", "capacity": 4},
    "S1121M050010": {"name": "M5-10",  "floor": "05", "room": "0010", "capacity": 10},
    "S1121M05006A": {"name": "M5-6A",  "floor": "05", "room": "006A", "capacity": 6},
    "S1121M05006B": {"name": "M5-6B",  "floor": "05", "room": "006B", "capacity": 6},
    "S1121M05006C": {"name": "M5-6C",  "floor": "05", "room": "006C", "capacity": 6},
    "S1121M060004": {"name": "M6-4",   "floor": "06", "room": "0004", "capacity": 4},
    "S1121M060010": {"name": "M6-10",  "floor": "06", "room": "0010", "capacity": 10},
    "S1121M06006A": {"name": "M6-6A",  "floor": "06", "room": "006A", "capacity": 6},
    "S1121M06006C": {"name": "M6-6C",  "floor": "06", "room": "006C", "capacity": 6},
    "S1121M070004": {"name": "M7-4",   "floor": "07", "room": "0004", "capacity": 4},
    "S1121M070010": {"name": "M7-10",  "floor": "07", "room": "0010", "capacity": 10},
    "S1121M07006A": {"name": "M7-6A",  "floor": "07", "room": "006A", "capacity": 6},
    "S1121M07006B": {"name": "M7-6B",  "floor": "07", "room": "006B", "capacity": 6},
    "S1121M07006C": {"name": "M7-6C",  "floor": "07", "room": "006C", "capacity": 6},
    "S1121M080004": {"name": "M8-4",   "floor": "08", "room": "0004", "capacity": 4},
    "S1121M080010": {"name": "M8-10",  "floor": "08", "room": "0010", "capacity": 10},
    "S1121M08006A": {"name": "M8-6A",  "floor": "08", "room": "006A", "capacity": 6},
    "S1121M08006B": {"name": "M8-6B",  "floor": "08", "room": "006B", "capacity": 6},
    "S1121M08006C": {"name": "M8-6C",  "floor": "08", "room": "006C", "capacity": 6},
    "S1121M090010": {"name": "M9-10",  "floor": "09", "room": "0010", "capacity": 10},
    "S1121M10CA14": {"name": "CAMF14", "floor": "10", "room": "CA14", "capacity": 14},
    "S1121M10DP09": {"name": "DEEP9",  "floor": "10", "room": "DP09", "capacity": 9},
}

# 방 이름으로도 검색할 수 있도록 역방향 매핑
NAME_TO_CODE = {v["name"]: k for k, v in ROOMS.items()}
# 대소문자 무시 + 하이픈 무시 매핑 추가
NAME_TO_CODE_LOWER = {v["name"].lower().replace("-", ""): k for k, v in ROOMS.items()}


def load_token():
    """토큰 파일에서 access_token 읽기"""
    if not TOKEN_PATH.exists():
        print(f"토큰 파일이 없습니다: {TOKEN_PATH}")
        print("브라우저 Local Storage에서 access_token을 복사해서 토큰 파일을 만들어주세요.")
        sys.exit(1)
    with open(TOKEN_PATH) as f:
        config = json.load(f)
    return config


def get_headers(token):
    """API 요청 헤더 생성"""
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://member.heyground.com",
        "Referer": "https://member.heyground.com/",
    }


def get_reservations(date_str, location, token):
    """특정 날짜의 전체 예약 조회 (YYYY-MM-DD 형식)"""
    url = f"{API_BASE}/reservations/rooms/{date_str}?location={location}"
    resp = requests.get(url, headers=get_headers(token))
    resp.raise_for_status()
    return resp.json()


def get_my_reservations(location, token):
    """내 예약 목록 조회"""
    url = f"{API_BASE}/reservations/rooms/my?location={location}"
    resp = requests.get(url, headers=get_headers(token))
    resp.raise_for_status()
    return resp.json()


def get_credit(token):
    """잔여 크레딧 조회"""
    url = f"{API_BASE}/members/credit"
    resp = requests.get(url, headers=get_headers(token))
    resp.raise_for_status()
    return resp.json()


def check_credit(booking_data, token):
    """예약 전 크레딧 사전 확인"""
    url = f"{API_BASE}/reservations/credits"
    resp = requests.post(url, json=booking_data, headers=get_headers(token))
    resp.raise_for_status()
    return resp.json()


def create_reservation(booking_data, token):
    """예약 생성"""
    url = f"{API_BASE}/reservations"
    resp = requests.post(url, json=booking_data, headers=get_headers(token))
    resp.raise_for_status()
    return resp.json()


def find_available_rooms(date_str, start_time, end_time, capacity, location, token):
    """빈 회의실 찾기

    Args:
        date_str: "YYYY-MM-DD" 형식
        start_time: "HHMM" 형식 (예: "1400")
        end_time: "HHMM" 형식 (예: "1600")
        capacity: 필요 인원 수 (4, 6, 8, 10, 14)
        location: 지점 코드 (예: "seoulsoop")
        token: access_token
    """
    reservations = get_reservations(date_str, location, token)

    # 해당 시간대에 예약된 방 코드 수집
    start = int(start_time)
    end = int(end_time)
    booked_rooms = set()
    for r in reservations:
        r_start = int(r["time_use_start"])
        r_end = int(r["time_use_end"])
        # 시간이 겹치는지 확인
        if r_start < end and r_end > start:
            booked_rooms.add(r["pblspc_cd"])

    # 용량 조건에 맞는 빈 방 필터링
    available = []
    for code, info in ROOMS.items():
        if code in booked_rooms:
            continue
        if info["capacity"] >= capacity:
            available.append({"code": code, **info})

    # 용량이 작은 것 우선 (딱 맞는 방 추천)
    available.sort(key=lambda x: (x["capacity"], x["floor"]))
    return available


def build_booking_data(room_code, date_yyyymmdd, start_hhmm, end_hhmm, dtl="회의", location="seoulsoop"):
    """예약 요청 데이터 생성"""
    room_info = ROOMS[room_code]
    return {
        "pblspc_cd": room_code,
        "de_use": date_yyyymmdd,
        "time_use_start": start_hhmm,
        "time_use_end": end_hhmm,
        "dtl": dtl,
        "memo": "",
        "dong": "1",
        "se": "0291",
        "se_nm": "M",
        "floor": room_info["floor"],
        "room": room_info["room"],
        "location": location,
    }


def resolve_room_code(room_input):
    """사용자 입력에서 방 코드 찾기 (이름 또는 코드)"""
    # 이미 코드인 경우
    if room_input in ROOMS:
        return room_input
    # 이름으로 검색
    if room_input in NAME_TO_CODE:
        return NAME_TO_CODE[room_input]
    # 대소문자/하이픈 무시 검색
    normalized = room_input.lower().replace("-", "").replace(" ", "")
    if normalized in NAME_TO_CODE_LOWER:
        return NAME_TO_CODE_LOWER[normalized]
    return None


# === CLI 명령 ===

def cmd_book(args, config):
    """예약 실행: --date 20260305 --start 1400 --end 1600 [--room M7-6A | --capacity 6]"""
    token = config["access_token"]
    location = config.get("location", "seoulsoop")

    date_ymd = args.get("date")
    start = args.get("start")
    end = args.get("end")
    room_input = args.get("room")
    capacity = int(args.get("capacity", 4))

    date_dash = f"{date_ymd[:4]}-{date_ymd[4:6]}-{date_ymd[6:]}"

    if room_input:
        # 특정 방 지정
        room_code = resolve_room_code(room_input)
        if not room_code:
            print(f"방을 찾을 수 없습니다: {room_input}")
            sys.exit(1)
    else:
        # 빈 방 자동 선택
        available = find_available_rooms(date_dash, start, end, capacity, location, token)
        if not available:
            print(f"{date_dash} {start}~{end} 시간대에 {capacity}인 이상 빈 방이 없습니다.")
            sys.exit(1)
        room_code = available[0]["code"]
        print(f"자동 선택: {available[0]['name']} ({available[0]['capacity']}인실)")

    # 예약 데이터 생성
    booking = build_booking_data(room_code, date_ymd, start, end, location=location)

    # 크레딧 확인
    credit_info = check_credit(booking, token)
    print(f"필요 크레딧: {credit_info['credit']}")

    # 예약 실행
    result = create_reservation(booking, token)
    room_name = ROOMS[room_code]["name"]
    print(f"\n예약 완료!")
    print(f"  예약코드: {result['cd']}")
    print(f"  회의실: HG#2 {room_name}")
    print(f"  날짜: {date_dash}")
    print(f"  시간: {start[:2]}:{start[2:]}~{end[:2]}:{end[2:]}")
    print(f"  차감 크레딧: {result.get('crt_count', credit_info['credit'])}")
    print(f"  상태: {result.get('stat_nm', 'RESERVED')}")


def cmd_available(args, config):
    """빈 방 조회: --date 20260305 --start 1400 --end 1600 [--capacity 4]"""
    token = config["access_token"]
    location = config.get("location", "seoulsoop")

    date_ymd = args.get("date")
    start = args.get("start")
    end = args.get("end")
    capacity = int(args.get("capacity", 1))

    date_dash = f"{date_ymd[:4]}-{date_ymd[4:6]}-{date_ymd[6:]}"
    available = find_available_rooms(date_dash, start, end, capacity, location, token)

    if not available:
        print(f"{date_dash} {start}~{end} 시간대에 빈 방이 없습니다.")
        return

    print(f"{date_dash} {start[:2]}:{start[2:]}~{end[:2]}:{end[2:]} 빈 회의실:")
    for r in available:
        print(f"  {r['name']:10s} ({r['capacity']}인실) - {r['floor']}층")


def cmd_my(config):
    """내 예약 목록"""
    token = config["access_token"]
    location = config.get("location", "seoulsoop")
    reservations = get_my_reservations(location, token)

    if not reservations:
        print("예약이 없습니다.")
        return

    print("내 예약 목록:")
    for r in reservations:
        s = r["time_use_start"]
        e = r["time_use_end"]
        print(f"  [{r['cd']}] {r['de_use'][:4]}-{r['de_use'][4:6]}-{r['de_use'][6:]} "
              f"{s[:2]}:{s[2:]}~{e[:2]}:{e[2:]} {r['pblspc_nm']} "
              f"({r.get('stat_nm', r.get('stat', ''))})")


def cmd_credit(config):
    """잔여 크레딧 확인"""
    token = config["access_token"]
    info = get_credit(token)
    print(f"잔여 크레딧: {info['credit']}")


def main():
    if len(sys.argv) < 2:
        print("사용법:")
        print("  python3 heyground.py book --date 20260305 --start 1400 --end 1600 --capacity 6")
        print("  python3 heyground.py book --date 20260305 --start 1400 --end 1600 --room M7-6A")
        print("  python3 heyground.py available --date 20260305 --start 1400 --end 1600")
        print("  python3 heyground.py my")
        print("  python3 heyground.py credit")
        sys.exit(1)

    config = load_token()
    command = sys.argv[1]

    # 인자 파싱
    args = {}
    i = 2
    while i < len(sys.argv):
        if sys.argv[i].startswith("--"):
            key = sys.argv[i][2:]
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                args[key] = sys.argv[i + 1]
                i += 2
            else:
                args[key] = True
                i += 1
        else:
            i += 1

    if command == "book":
        cmd_book(args, config)
    elif command == "available":
        cmd_available(args, config)
    elif command == "my":
        cmd_my(config)
    elif command == "credit":
        cmd_credit(config)
    else:
        print(f"알 수 없는 명령: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Step 2: 동작 확인 (읽기 전용)**

Run: `python3 ~/heyground-booking/heyground.py credit`
Expected: `잔여 크레딧: 248` (또는 현재 잔액)

Run: `python3 ~/heyground-booking/heyground.py my`
Expected: 현재 예약 목록 출력

이 단계에서 인증이 실패하면 → 토큰 전송 방식을 조정해야 함 (쿠키 방식 등)

---

## Task 3: Claude Code 스킬 생성

**Files:**
- Create: `~/.claude/skills/book-room/SKILL.md`

**Step 1: 스킬 파일 작성**

`~/.claude/skills/book-room/SKILL.md`:
````markdown
---
name: book-room
description: 헤이그라운드 회의실 예약/조회/크레딧 확인. "회의실 예약해줘", "빈방 조회", "크레딧 확인" 등의 요청에 사용.
---

# 헤이그라운드 회의실 예약 스킬

## 사용할 스크립트
`~/heyground-booking/heyground.py`

## 사용자 요청 파싱 규칙

사용자가 자연어로 요청하면 아래 규칙에 따라 파싱하여 스크립트를 실행한다.

### 1. 예약 요청

사용자 예시: "3/5 14~16시 6인 예약", "내일 10시~12시 M7-6A 예약"

파싱 규칙:
- **날짜**: "3/5" → 20260305, "내일" → 오늘+1일 계산, "오늘" → 오늘 날짜
- **시간**: "14~16시" → start=1400, end=1600 / "10시~12시" → start=1000, end=1200
- **방 지정**: "M7-6A" 같은 방 이름이 있으면 --room 옵션 사용
- **인원 지정**: "6인", "6명", "6인실" → --capacity 6 (방 이름 없을 때만)

실행:
```bash
python3 ~/heyground-booking/heyground.py book --date {YYYYMMDD} --start {HHMM} --end {HHMM} [--room {방이름} | --capacity {인원}]
```

### 2. 빈 방 조회

사용자 예시: "오늘 빈방", "3/5 14~16시 빈 회의실"

실행:
```bash
python3 ~/heyground-booking/heyground.py available --date {YYYYMMDD} --start {HHMM} --end {HHMM} [--capacity {인원}]
```

### 3. 내 예약 확인

사용자 예시: "내 예약", "예약 현황"

실행:
```bash
python3 ~/heyground-booking/heyground.py my
```

### 4. 크레딧 확인

사용자 예시: "크레딧", "잔여 크레딧"

실행:
```bash
python3 ~/heyground-booking/heyground.py credit
```

## 회의실 목록 (서울숲점)

| 이름 | 인원 | 층 |
|------|------|----|
| M4-4 | 4인 | 4층 |
| M4-6 | 6인 | 4층 |
| M4-8 | 8인 | 4층 |
| M4-10 | 10인 | 4층 |
| M5-4 | 4인 | 5층 |
| M5-6A/B/C | 6인 | 5층 |
| M5-10 | 10인 | 5층 |
| M6-4 | 4인 | 6층 |
| M6-6A/C | 6인 | 6층 |
| M6-10 | 10인 | 6층 |
| M7-4 | 4인 | 7층 |
| M7-6A/B/C | 6인 | 7층 |
| M7-10 | 10인 | 7층 |
| M8-4 | 4인 | 8층 |
| M8-6A/B/C | 6인 | 8층 |
| M8-10 | 10인 | 8층 |
| M9-10 | 10인 | 9층 |
| CAMF14 | 14인 | 10층 |
| DEEP9 | 9인 | 10층 |

## 응답 형식

예약 성공 시 결과를 요약해서 보여줄 것:
- 예약코드, 회의실, 날짜, 시간, 차감 크레딧

에러 시 원인을 쉽게 설명:
- 401/403 → "토큰이 만료되었을 수 있어요. 브라우저에서 토큰을 다시 복사해주세요."
- 빈 방 없음 → "해당 시간대에 빈 방이 없어요. 다른 시간대를 시도해보세요."
````

---

## Task 4: 토큰 설정 + API 연결 테스트

**Step 1: 토큰 파일에 실제 토큰 저장**

사용자에게 브라우저 Local Storage의 `access_token`, `refresh_token` 값을 복사하도록 안내.

**Step 2: 읽기 전용 API 테스트**

Run: `python3 ~/heyground-booking/heyground.py credit`

- 성공 → Task 5로 진행
- 401 에러 → 인증 방식 조정 필요 (쿠키 기반으로 전환 등)

**Step 3: 빈 방 조회 테스트**

Run: `python3 ~/heyground-booking/heyground.py available --date 20260224 --start 1400 --end 1600`

Expected: 빈 방 목록 출력

---

## Task 5: 실제 예약 테스트

**Step 1: 테스트 예약 실행**

사용자에게 테스트 예약할 날짜/시간 확인 후 실행.

Run: `python3 ~/heyground-booking/heyground.py book --date {테스트날짜} --start {시간} --end {시간} --capacity 4`

Expected: 예약 완료 메시지 + 예약코드

**Step 2: 예약 확인**

Run: `python3 ~/heyground-booking/heyground.py my`

Expected: 방금 만든 예약이 목록에 표시

---

## Task 6: 글로벌 CLAUDE.md에 스킬 등록

**Files:**
- Modify: `~/.claude/CLAUDE.md`

Skills 섹션에 추가:
```
- `/book-room` — 헤이그라운드 회의실 예약/조회/크레딧 확인 (`~/.claude/skills/book-room/`)
```
