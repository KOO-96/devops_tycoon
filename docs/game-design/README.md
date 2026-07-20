# DevOps Tycoon — 게임 기획 문서 (Game Design Docs)

## 목적

이 디렉터리는 DevOps Tycoon의 **게임 기획 문서**를 모아둔 곳입니다.
개발팀(Frontend / Backend / Simulation / Ops / DevCTO / Event / Infra)이
**실제 구현 기준**으로 참조하는 단일 기준 문서를 제공합니다.

> 이 문서들은 기획(요구사항)을 정의하며, 코드 구현 세부는 강제하지 않습니다.
> 확정되지 않은 값은 `TBD`로 표기하고, 마스터 플랜의 **결정 필요 사항**에 정리합니다.

## 주요 기획 문서 목록

| 문서 | 설명 | 담당 역할 |
|------|------|-----------|
| [devops-tycoon-master-plan.md](./devops-tycoon-master-plan.md) | 통합 게임 기획안(게임 개요·핵심 루프·MVP·역할별 요구사항·AC·결정 필요 사항) | Program |
| README.md (본 문서) | 기획 문서 진입점·갱신 규칙·검토 절차 | Program |

향후 추가 예정(별도 브랜치/담당):

| 예정 문서 | 담당 역할 | 비고 |
|-----------|-----------|------|
| 이벤트/장애 상세 데이터 | Event (`plan/event`) | 마스터 플랜 [4.13] 승인 기준 준수 |
| API / WebSocket 스키마 명세 | Backend | 마스터 플랜 [GD-010] |
| Simulation 규칙 상세 명세 | Simulation | 결정론·밸런싱 수치 확정 |

## 각 문서의 담당 역할

- **Program**: 통합 기획안·문서 인덱스·역할 간 경계 정의.
- **Event (plan/event)**: 개별 이벤트/장애 데이터 상세 설계.
- **Backend / Simulation / Frontend / DevCTO / Ops / Infra**: 각 역할별 요구사항은 마스터 플랜 [4.17 역할별 개발 전달 사항] 참조.

## 문서 갱신 규칙

1. 기획 변경은 반드시 마스터 플랜의 **[4.19 기획 변경 기록]** 표에 버전·날짜·변경 내용·작성자·승인 상태를 남깁니다.
2. 문서 버전은 [Semantic Versioning](https://semver.org) 방식(`vMAJOR.MINOR.PATCH`)을 따릅니다.
3. 확정되지 않은 값은 임의로 확정하지 말고 `TBD`로 표기하며, **[4.18 결정 필요 사항]**에 항목을 추가합니다.
4. 기존 기획의 핵심 방향을 바꿀 때는 **이유와 영향 범위**를 기록하고 검토를 거칩니다.
5. 게임 속 인프라(콘텐츠)와 실제 운영 인프라(예: k3s)를 문서에서 혼동하지 않습니다.
6. 문서 상태는 `Draft → Review → Approved` 순서로 전이합니다.

## 관련 브랜치

| 브랜치 | 용도 |
|--------|------|
| `main` | 안정 브랜치 |
| `dev` | 통합 개발 브랜치(기획/개발 작업의 기준) |
| `plan/program` | 통합 기획안 작성 브랜치(본 문서 작업) |
| `plan/event` | 이벤트 기획 작업 브랜치 |
| `review/devcto` | 기획/개발 PR 검토 대상 브랜치 |

> 작업은 `dev` 기준으로 시작하며, `dev` / `review/devcto`에 직접 push하지 않습니다.
> `review/devcto` 브랜치 정책은 마스터 플랜 [GD-003] 참조.

## 기획 PR 검토 절차

1. `plan/program`에서 작업 후 커밋합니다.
2. PR 대상: **`review/devcto`**.
3. 필수 검토자: **Frontend / Backend / Simulation / DevCTO** 담당자.
4. 검토 관점:
   - Frontend: 화면 요구사항이 구현 가능한가.
   - Backend: API/세션/영속화 요구사항이 구현 가능한가.
   - Simulation: 게임 규칙이 계산 가능·결정론적인가.
   - DevCTO: 전체 아키텍처·프로젝트 방향과 일치하는가.
5. 검토 완료 후 문서 상태를 `Review → Approved`로 갱신하고 병합합니다.

## 검토 체크리스트

- [ ] 기존 기획 방향과 일치한다.
- [ ] MVP 범위가 명확하다.
- [ ] Frontend 구현 요구사항이 검증 가능하다(측정 가능한 AC).
- [ ] Backend와 Simulation 책임이 분리되어 있다.
- [ ] AI CTO가 게임 상태를 임의로 결정하지 않는다.
- [ ] 주요 기능에 Acceptance Criteria가 존재한다.
- [ ] 미확정 사항(TBD)이 결정 필요 사항에 정리되어 있다.
