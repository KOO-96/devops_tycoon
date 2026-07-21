# DevOps Tycoon — 이벤트 기획 문서 (Event Design)

## 목적

이 디렉터리는 DevOps Tycoon의 **상황·기술 필요성·장애·운영·외부 이벤트** 기획을 담는다.
단순한 DevOps 기술 설명이 아니라, **플레이어가 특정 기술의 필요성을 언제 체감하는지**, **기술 도입의 장점·비용·복잡도·새 장애**를 게임 규칙과 이벤트로 설계한다.

## Event 담당자의 책임 범위

- 상황·기술 필요성·이벤트 구조 설계
- 사전 징후(P7)와 복수의 대응 선택지(P4) 설계
- 성공/부분 성공/실패 판정, 후폭풍(P6), 반복 제어(쿨다운) 정의
- 테스트 가능한 초기 수치(Proposed) 제안 및 근거 기록

## 역할 경계

| 역할 | 책임 |
|------|------|
| **Program** | 전체 게임 방향·MVP 범위 결정, Event 기획 승인, 최종 기획 의도 판단 |
| **Event** | 상황·기술 필요성·이벤트 구조·사전 징후·대응 선택지 설계, 초기 수치 제안 |
| **Simulation** | 승인된 이벤트 조건·수치를 코드로 계산. **Event 문서에 없는 규칙을 임의 추가하지 않음** |

> 경계 원칙: Event는 관측 불가한 사실을 확정하지 않고, Simulation은 문서 밖 규칙을 만들지 않는다(마스터 플랜 P8).

## Simulation 담당자에게 전달되는 내용

- 각 이벤트의 발동/제외 조건, 사전 징후 지표, 대응별 효과·후폭풍, 성공·실패 판정 기준
- 각 이벤트의 **Simulation 인터페이스**(필요 입력 / 출력해야 하는 결과)
- 파생 병목(P6) 전가 관계와 연쇄 구조(CHN-001~003), 최대 연쇄 깊이
- 모든 수치는 상태 라벨(Confirmed/Proposed/TBD)과 함께 전달. 밸런스 데이터(설정 파일)로 분리 가능하도록 정의

## MVP / Post-MVP 구분

- **MVP:** Load Balancer, App Scaling, PostgreSQL, Redis, 기본 로그/메트릭, Health Check, 수동 배포, Rollback, 기본 CI/CD 및 관련 장애 16종.
- **Post-MVP:** Kafka, Kubernetes(복잡 운영), Service Mesh, Multi Region, Global DB, 복잡 Auto Scaling, 대규모 MSA, 고급 분산 추적 → [post-mvp-event-backlog.md](./post-mvp-event-backlog.md)에 보관(삭제 아님).

## 문서 목록

| 문서 | 설명 | 상태 |
|------|------|------|
| [event-design-standard.md](./event-design-standard.md) | 모든 이벤트 공통 템플릿·ID·수치 규칙 | **Approved** |
| [mvp-event-catalog.md](./mvp-event-catalog.md) | MVP 이벤트 16종 + 연쇄 3종 상세 | **Approved** (수치 Proposed) |
| [technology-trigger-matrix.md](./technology-trigger-matrix.md) | 문제↔기술 도입 관계 매트릭스 | **Approved** |
| [post-mvp-event-backlog.md](./post-mvp-event-backlog.md) | Post-MVP 기술·이벤트 백로그 | Draft |
| [program-decisions-required.md](./program-decisions-required.md) | Program 결정 필요 사항(결정 완료) | **Resolved** → [../program-decisions.md](../program-decisions.md) |

## 이벤트 상태

`Draft → Program Review → Approved / Rejected`, 범위 밖은 `Post-MVP`. 상태 정의는 [event-design-standard.md](./event-design-standard.md) §3 참조.

## 변경 절차

1. 이벤트 추가/변경은 [event-design-standard.md](./event-design-standard.md) 템플릿과 EV-1~10 게이트를 충족해야 한다.
2. 수치는 반드시 상태 라벨(Confirmed/Proposed/TBD)과 근거를 함께 기록한다.
3. 미확정 값은 [program-decisions-required.md](./program-decisions-required.md)에 등록한다.
4. 각 문서 하단 변경 기록 표를 갱신한다.
5. Program 기획과 충돌 발견 시 임의로 덮어쓰지 않고 결정 필요 문서에 기록한다.

## PR 대상 브랜치

- 작업 브랜치: `plan/event` (dev에서 생성)
- **PR 대상: `plan/program`**
- 금지: `plan/program` / `review/devcto` / `dev`에 직접 Push, 타 역할 브랜치에서 작업.

## 승인 절차

1. `plan/event`에서 문서 단위로 커밋 후 push.
2. `plan/program` 대상으로 PR 생성. 필수 검토자: **Program**. 참고 검토자: Simulation / Backend / DevCTO.
3. Program이 EV-1~10 게이트와 MVP 정합성을 검토·승인.
4. 승인 후 각 이벤트 상태를 `Approved`로, 승인된 수치를 `Confirmed`로 갱신.

## 승인 체크리스트

- [ ] 각 이벤트에 발동 조건이 있다.
- [ ] 각 이벤트에 사전 징후가 있다(P7).
- [ ] 대응 방법이 하나로 제한되지 않는다(P4).
- [ ] 성공·부분 성공·실패가 구분된다.
- [ ] 기술 도입의 장점과 부작용이 모두 존재한다(P5).
- [ ] 반복 방지와 쿨다운이 정의된다(EV-9).
- [ ] Simulation에서 계산 가능한 구조다(입력/출력 명시).
- [ ] MVP 범위를 벗어나지 않는다.
