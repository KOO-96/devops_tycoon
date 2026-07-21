# Program 승인 결정 (Program Decisions of Record)

> 이 문서는 **Program이 최종 승인한 결정만** 모아 관리하는 권위 문서다.
> Event/Simulation/Frontend/Backend는 이 문서를 구현 기준으로 사용한다.
> 결정 요청 원본은 [events/program-decisions-required.md](./events/program-decisions-required.md)에 있다.

- 문서 버전: v0.1.0
- 작성 브랜치: `plan/program`
- 최종 수정일: 2026-07-20
- 담당 역할: Program
- 참고 문서: `devops-tycoon-master-plan.md`, `events/mvp-event-catalog.md`, `events/event-design-standard.md`, `events/technology-trigger-matrix.md`, `events/program-decisions-required.md`

## 결정 상태 범례
- **Confirmed**: 확정. 구현 기준으로 사용 가능.
- **Revised**: 수정 승인. 원 제안을 조정하여 확정.
- **Deferred**: 보류. 선행 결정/검증 후 재검토.
- **Rejected**: 반려.
- 수치 상태(값 자체): **Confirmed / Proposed / TBD** — 구조·정책은 확정이어도 세부 수치는 Proposed일 수 있음.

---

## 1. GD-001 — 게임 시간 구조 (Confirmed)

**결정: 실시간 기반 + 고정 Simulation Tick + 배속.** 시간 *구조*는 Confirmed, 세부 *수치*는 Proposed로 유지한다.

| 항목 | 결정 | 상태 |
|------|------|------|
| Tick의 의미 | Simulation의 원자적 결정론 단위. 모든 게임 로직은 Tick 단위로만 진행한다. wall-clock은 결과를 결정하지 않는다. | Confirmed |
| 기본 Tick 간격(1× 실시간) | 1 Tick = 200 ms (실시간). | Proposed |
| 게임 시간 ↔ 실제 시간 | Frontend가 1× 기준 실시간으로 Tick을 재생. 결과는 Tick 수로만 계산(FPS/처리속도 무관). | Confirmed |
| 게임 시간 단위 | 1 게임일(in-game day) = 300 Tick. 1 스프린트 = 7 게임일. | Proposed |
| Pause(속도 0) | GameState 미진행. 관측·계획·명령 예약은 허용, 시간 소요 조치는 재개 후 진행(EVT-D-002 정렬). | Confirmed |
| 배속 1×/2×/4× | 같은 실제 프레임에서 처리하는 Tick 수 배율에만 영향. 계산 결과 자체는 불변. | Confirmed |
| 이벤트 시간 저장 단위 | **Tick(canonical).** `duration_ticks`, `warning_lead_ticks`, `response_window_ticks`, `cooldown_ticks`. | Confirmed |
| 개발·배포 작업 시간 저장 단위 | Tick(`work_duration_ticks`, `deploy_duration_ticks`). | Confirmed |
| 저장·불러오기 시간 상태 | `current_tick`, `simulation_time`, `speed`, `paused`, `rng_state`를 영속화. 복원 후 동일 Tick 진행 시 동일 결과. | Confirmed |
| Frontend 표시 | Tick → 게임일/시각 등 사용자 친화 단위로 변환하여 표시(저장은 Tick). | Confirmed |
| Simulation 테스트 기준 | 테스트는 명시적 Tick 수를 진행하며, 동일 Tick 수·Seed·명령열·Config에서 동일 결과. | Confirmed |

> **근거:** 실시간+배속은 타이쿤 장르 관례이자 마스터 플랜 4.5 방향과 일치. Tick 결정론은 Simulation 재현성(§8 재현성 요구)의 전제. 세부 수치(Tick=200ms, 1일=300Tick)는 플레이테스트로 조정되어야 하므로 Proposed.
> **영향:** Simulation(시간·Tick·저장), Frontend(Tick→게임시간 변환 표시), Event(모든 시간 수치를 Tick으로 정규화).

### 이벤트 시간 정규화 기준 (상대 등급 → Tick, 모두 Proposed)

Event 문서의 상대 표현(짧음/보통/긺)을 아래 기준으로 정규화한다. 값은 Proposed(플레이테스트 조정), 설정 파일로 분리(EVT-D-010).

| 상대 등급 | response_window_ticks | 게임일 환산(1일=300Tick 기준) | 상태 |
|-----------|-----------------------|-------------------------------|------|
| 짧음(급작형) | 30 | ≈ 0.1 게임일 | Proposed |
| 보통 | 90 | ≈ 0.3 게임일 | Proposed |
| 긺(서서히) | 300 | ≈ 1 게임일 | Proposed |

| 항목 | 값 | 상태 |
|------|----|------|
| warning_lead_ticks(사전 징후 최소 노출) | ≥ response_window의 50% | Proposed |
| cooldown_ticks(일반 이벤트) | 600 (≈2 게임일) | Proposed |
| cooldown_ticks(희소 이벤트: 인플루언서) | 3000 (≈10 게임일) | Proposed |

> 4배속에서도 조작 가능성을 위해 최소 대응 창(짧음)은 실시간 기준 4× 재생 시 최소 수 초가 확보되도록 Simulation 플레이테스트에서 검증한다(추가 검증 필요).

---

## 2. EVT-D-009 — Black Friday 성장 단계 승급 정책 (Confirmed, Revised)

**결정: 연계하되, 완전 성공만을 승급 조건으로 삼지 않는다.** 부분 성공도 생존·복구·Postmortem 완료 시 승급 가능. 치명적 실패 시 승급 보류(캠페인 강제 종료는 아님).

### 세 결과 정의 및 영향

| 결과 | 판정 | 단계3 승급 | 보상 | 페널티 | 후속 이벤트 | CTO 반응 | 신뢰도(사용자/투자자) |
|------|------|-----------|------|--------|-------------|----------|------------------------|
| **Success** | 피크 기간 무중대장애 통과 + 회사 생존 + Postmortem 완료 | 승급 | 매출 대폭↑, 투자자 신뢰 대폭↑ | 없음 | 단계3 신규 목표 해금 | 부스터: 성장 자축 / 가디언: 안정 유지 당부 | 상승 |
| **Partial Success** | 일부 장애/성능 저하 발생했으나 **핵심 서비스 복구 + 회사 생존 + Postmortem 완료** + 신뢰도 임계 이상 | 승급 가능 | 매출 중폭↑ | 신뢰도 소폭 하락, 기술 부채/피로도 증가 | 재발 방지 미션(선택) | 가디언: 재발 방지 강조 / 부스터: 다음 기회 독려 | 소폭 하락(임계 이상 유지) |
| **Failure** | 회사 파산 / 장기 서비스 중단 / 데이터 유실 등 치명적 결과 | **승급 보류** | 없음 | 대형 손실 | **복구 미션 또는 재도전** 제공(즉시 게임 오버 아님) | 가디언: 원인 규명 우선 / 부스터: 재정비 | 큰 폭 하락 |

### 승급 조건(권장안 반영, Confirmed)
아래를 **모두** 충족하면 승급(Success/Partial 공통):
1. Black Friday 이벤트 종료
2. 회사 생존(파산 아님)
3. 핵심 서비스 복구(모든 핵심 노드 `Healthy`)
4. Postmortem 완료
5. 사용자 신뢰도 **또는** 투자자 신뢰도가 최소 임계 이상 (임계값 Proposed, GD-009 연계)

> **근거:** 마스터 플랜 P3(장애는 콘텐츠, 실패 화면 아님)·4.15(복구 가능 상태 vs 게임 오버 구분)와 정렬. 완전 성공 강요는 P4(복수 정답)·난이도 형평에 반함. Failure에도 복구/재도전을 주어 "억울한 종료"를 방지.
> **영향:** Campaign(15단계 승급 로직), Simulation(3결과 판정 + 승급 게이트 계산), Frontend(결과·복구 미션 표시), DevCTO(결과별 CTO 반응).
> **미확정:** 신뢰도 최소 임계값(Proposed, GD-009), 복구 미션 구체 설계(다음 캠페인 작업).

---

## 3. EVT-D-001 ~ EVT-D-010 결정 표

| ID | 최종 결정 | 상태 | 결정 이유 | 영향 범위 | 후속 작업 |
|----|-----------|------|-----------|-----------|-----------|
| EVT-D-001 | Black Friday 준비 기간 **3 게임일 기본**(Easy 7 / Hard 1) | Confirmed(구조) / 수치 Proposed | 준비-대응 밸런스, 난이도 스케일 제공 | Campaign, Simulation, EVT-EXT-003 | Tick 환산(3일=900Tick) 설정화, 플레이테스트 |
| EVT-D-002 | 이벤트 중 일시정지 **제한 허용**(관측·계획·예약 가능, 시간 소요 조치는 재개 후) | Confirmed | 진단 게임 특성상 계획은 허용하되 시간 진행 이득은 차단 | Frontend, Simulation | Pause 시 명령 큐잉 규칙 문서화 |
| EVT-D-003 | 게임 시간 구조 **실시간+고정 Tick+배속** | Confirmed(구조) / 수치 Proposed | GD-001 §1 참조 | 전 이벤트 시간 수치 | §1 정규화 표 적용 |
| EVT-D-004 | 대응 제한 시간 **이벤트별 개별**(`response_window_ticks`) | Confirmed | 장애 특성별 유예가 다름, 획일 비율은 부자연 | Simulation, 전 이벤트 | §1 상대등급→Tick 표로 초기화 |
| EVT-D-005 | 신뢰도/보상 **이벤트당 상한 적용**(급락 방지) | Confirmed(정책) / 상한값 Proposed | 단일 이벤트로 신뢰도 붕괴하는 "억울함" 방지(4.15) | Simulation, 4.15 | 이벤트당 Δ상한값 밸런싱 |
| EVT-D-006 | "금요일 배포" → **주기적 고위험 배포 슬롯**(Tick 기반), 실제 요일 개념 미도입 | **Revised** | 실제 캘린더 결합 회피, Tick 결정론 유지. "금요일"은 표시용 은유 | Simulation, EVT-EXT-004, Frontend | 주기 슬롯 위치/폭 정의, 표시 문구는 Frontend |
| EVT-D-007 | 확률 발동 **허용(Seed 기반 PRNG)** | Confirmed | 재현성 유지하며 예측불가 연출 가능(마스터 플랜 4.11, Sim §8) | Simulation, EVT-EXT-002, EVT-SRV-001 | 모든 확률은 명시적 RNG State에서 도출 |
| EVT-D-008 | 최대 연쇄 깊이 **4** | Confirmed | 무한 연쇄 방지, 복합 장애 체감 균형(CHN-001 4단계) | Simulation, Campaign | 깊이 초과 시 "심화로 대체" 로직 결정론 검증 |
| EVT-D-009 | Black Friday 승급 **연계(부분 성공 승급 허용)** | Confirmed(정책) / 임계 Proposed | §2 참조 | Campaign, Simulation, DevCTO, Frontend | 신뢰도 임계 확정, 복구 미션 설계 |
| EVT-D-010 | 밸런스 수치 **설정 파일(BalanceConfig)로 분리** | Confirmed | 하드코딩 금지(Sim §21), 밸런싱 반복 용이 | Simulation, Backend | 수치별 메타데이터(값/단위/상태/출처/EventID) 포함 |

**요약:** Confirmed 9건(EVT-D-001~005, 007~010), Revised 1건(EVT-D-006). Deferred/Rejected 없음.

---

## 4. 대표 Proposed 수치 검토 결과

각 값을 일괄 Confirmed로 바꾸지 않고 개별 검토했다. 대부분은 **정책/기준으로는 유효하나 절대 수치는 플레이테스트 필요** → Proposed 유지.

| 항목 | 값 | 결정 상태 | 비고 |
|------|----|-----------|------|
| DB Connection Warning | 80% | **Confirmed** | 마스터 플랜 FE-12/4.16에 이미 확정된 기준과 일치 |
| DB Connection Critical | 95% | Proposed | Timeout 직전 표현. Sim 플레이테스트로 미세조정 |
| App CPU Warning / Critical | 70% / 90% | Proposed | 선행 징후→포화 구분 기준으로 타당하나 수치 검증 필요 |
| Cache Hit 발동 / 목표 | 70% / 90% | Proposed | 캐시 효과 저하 감지·회복 기준으로 타당, 검증 필요 |
| Event Cooldown(일반) | 600 Tick(≈2일) | Proposed | GD-001 확정으로 Tick 정규화 완료(값은 Proposed) |
| Black Friday 준비 기간 | 3일=900 Tick | Proposed | EVT-D-001 확정으로 단위 정규화(값 Proposed) |
| 대응 제한 시간(짧음/보통/긺) | 30/90/300 Tick | Proposed | §1 정규화 표 |

> **검토 관점 적용:** 대응 시간은 1×~4× 모두 조작 가능해야 하므로 최소 창(짧음=30Tick)은 4배속 재생 시 조작 가능성 추가 검증 필요(Simulation). 반복 빈도는 cooldown으로 통제. 모든 값은 EVT-D-010에 따라 설정 파일 분리.

---

## 5. 남은 TBD

| TBD | 소유 | 선행 조건 |
|-----|------|-----------|
| Tick 절대 간격(200ms) 확정 | Simulation | 플레이테스트 |
| 1 게임일 = 300 Tick 확정 | Simulation | 플레이테스트 |
| 대응 제한 시간/쿨다운 Tick 값 확정 | Simulation + Event | 플레이테스트 |
| 신뢰도 최소 승급 임계(GD-009) | Program + Simulation | 밸런싱 |
| 이벤트당 신뢰도/보상 Δ상한(EVT-D-005) | Program + Simulation | 밸런싱 |
| 복구 미션/재도전 상세 설계 | Program(Campaign) | 다음 캠페인 작업 |
| 주기적 배포 슬롯 위치·폭(EVT-D-006) | Event + Simulation | GD-001 기반 세부화 |

---

## 변경 기록

| 버전 | 날짜 | 변경 내용 | 작성자 | 승인 상태 |
|------|------|-----------|--------|-----------|
| v0.1.0 | 2026-07-20 | GD-001 시간구조 Confirmed, EVT-D-001~010 결정(Confirmed 9/Revised 1), EVT-D-009 Black Friday 승급 정책 확정, 대표 수치 검토 | Program | Approved |
