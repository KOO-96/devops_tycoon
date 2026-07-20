# Program 결정 필요 사항 (Event → Program)

> Event 담당자가 단독으로 확정할 수 없는 항목을 정리한다. 임의 확정하지 않으며, Program 승인 후 각 문서의 수치 상태를 `Proposed → Confirmed`로 갱신한다.

- 문서 버전: v0.1.0
- 작성 브랜치: `plan/event`
- 최종 수정일: 2026-07-20
- 담당 역할: Event
- 참고 Program 문서: `origin/plan/program:...master-plan.md` (commit `a28fd84`)

## 1. 결정 요청 표

| ID | 결정 항목 | 선택지 | Event 권장안 | 영향 범위 | 결정 필요자 |
|----|-----------|--------|--------------|-----------|-------------|
| EVT-D-001 | Black Friday 준비 기간 | 1일 / 3일 / 7일 | 3일(Normal) | Campaign, Simulation, EVT-EXT-003 | Program |
| EVT-D-002 | 이벤트 중 게임 일시정지 | 허용 / 제한 / 금지 | 제한 허용(분석·예약 가능, 시간 소요 조치는 재개 후) | Frontend, Simulation | Program |
| EVT-D-003 | 게임 시간 단위(GD-001 연계) | 실시간 / 하루 / 스프린트 | 실시간+배속 | 전 이벤트의 시간 수치 | Program, DevCTO |
| EVT-D-004 | 대응 제한 시간 표준화 방식 | 절대값 고정 / 게임시간 비율 / 이벤트별 개별 | 이벤트별 개별(GD-007 연계) | Simulation, 전 이벤트 | Program |
| EVT-D-005 | 신뢰도 하락/보상 밸런스 상한 | 낮음 / 보통 / 높음 | 이벤트당 상한 적용(급락 방지) | Simulation, 4.15 | Program |
| EVT-D-006 | "금요일 배포"의 시간 정의 | 요일 개념 도입 / 주기 슬롯 / 미도입 | 주기 슬롯(GD-001 확정 후) | Simulation, EVT-EXT-004 | Program |
| EVT-D-007 | 확률 발동 이벤트 허용 여부 | 허용(Seed 기반) / 조건부만 / 금지 | 허용(Seed 결정론 준수) | Simulation, EVT-EXT-002, EVT-SRV-001 | Program |
| EVT-D-008 | 최대 연쇄 깊이 상한 | 3 / 4 / 5 | 4(CHN-001) | Simulation, Campaign | Program |
| EVT-D-009 | Black Friday 성공→단계3 승급 연계 | 연계 / 비연계 | 연계(마스터 플랜 4.14 정렬) | Campaign, Simulation | Program |
| EVT-D-010 | 수치 밸런스 데이터 분리 형식 | 설정 파일 / DB 밸런스 테이블 | 설정 파일(밸런스 데이터) | Simulation, Backend | Program, Simulation |

## 2. 대표 Proposed 수치(승인 필요)

이벤트 카탈로그의 난이도표는 전부 Proposed이며, 아래는 승인 우선순위가 높은 대표값이다.

| 항목 | 값 | 상태 | 근거 |
|------|----|------|------|
| DB Connection Warning | 80% | Proposed(Program 방향 정렬) | 장애 전 경고 구간 필요(마스터 플랜 FE-12/4.16) |
| DB Connection Critical | 95% | Proposed | Timeout 직전 상태 표현 |
| App CPU Warning / Critical | 70% / 90% | Proposed | 선행 징후→포화 구간 구분 |
| Cache Hit 발동 임계 / 목표 | 70% / 90% | Proposed | 캐시 효과 저하 감지 및 회복 기준 |
| Event Cooldown(일반) | 보통 | TBD | 캠페인 시간 구조(GD-001) 확정 필요 |
| Black Friday 준비 기간 | 3일 | TBD(EVT-D-001) | 준비-대응 밸런스 |

> 각 Proposed 값에는 제안 이유가 있으며, 난이도별 변경 가능성과 Simulation 테스트 필요 부분은 카탈로그 난이도표에 병기했다.

## 3. Simulation 검증 필요 항목

- 파생 병목(P6) 전가 계수: App 확장 → DB 커넥션 증가량, 풀 확대 → DB CPU 부담량.
- 캐시 스탬피드 순간 동시성 임계의 수치화(GD-001 의존).
- 연쇄 깊이 제한과 "심화로 대체" 로직의 결정론 재현성.
- 신뢰도/자금 변화의 이벤트당 상한 적용(급락 방지).

## 4. Program 기획과의 정렬/미해결

- **정렬됨:** 노드 상태(Healthy/Warning/Critical/Down), EV-1~10 승인 게이트, DB Connection Warning 80%, Seed 결정론, MVP 범위(4.8), CTO 성향(가디언/부스터).
- **미해결(Program 결정 대기):** 위 EVT-D-001~010. 특히 GD-001(시간 단위) 확정 전에는 모든 절대 시간 수치가 TBD로 남는다.
- **충돌 발견:** 현재 Program 기획과의 **직접 충돌 없음.** 향후 충돌 발견 시 이 절에 기록하고 임의로 덮어쓰지 않는다.

## 변경 기록

| 버전 | 날짜 | 변경 내용 | 작성자 | 승인 상태 |
|------|------|-----------|--------|-----------|
| v0.1.0 | 2026-07-20 | Program 결정 요청 10건 + 대표 수치 정리 | Event | Draft |
