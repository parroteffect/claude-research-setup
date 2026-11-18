# Fresh-session setup verification

이 문서는 연구 프로젝트 root에서 **재시작한 Claude Code main**이 수행하는 작은 설치 확인이다.
설치 파일의 존재와 실제 runtime 적용을 구분한다.
확인 작업은 사용자 코드 실행·모델 로딩·학습·평가를 포함하지 않는다.

## Main의 확인
1. 실제로 로드된 지침을 확인한다. Root `CLAUDE.md`의 CLAUDE RESEARCH WORKFLOW block이 현재
   세션 문맥에 있는지, `.claude/CLAUDE.md`·`CLAUDE.local.md`·`.claude/rules/`에 충돌하는 지침이
   없는지 본다. `/memory`로 로드된 파일 목록을 사용자가 직접 확인할 수 있다.
   User/managed 설정과 환경 변수는 관련 key만 확인하고 secret을 출력하지 않는다.
2. Main model/effort는 사용자의 기존 선택을 유지한다. 이번 검증을 위해 변경하지 않는다.
3. 사용할 수 있는 실제 Agent 도구에서 `engineer` subagent 등록과 `effort` 인자 지원을 확인한다.
   등록되지 않았거나 도구가 해당 선택을 지원하지 않으면 그 항목은 BLOCKED/NOT_VERIFIED다.
   `.claude/agents/` 디렉터리가 이번 설치로 처음 생겼다면 재시작 전 세션에는 등록되지 않을 수 있다.
4. 사용자가 이 문서의 검증을 요청했다면 아래 읽기 전용 작업을 **한 번만** high로 위임한다.
   이는 작은 agent 호출 비용이 드는 확인이며 heavyweight 연구 테스트가 아니다.

## 연구 지침의 적용 범위
- Main은 `.claude/research-workflow/guides/research.md`를 읽고 연구 발굴·아이디어 발전·수학적 분석이
  자신의 책임임을 확인한다. 간결함은 설명, 최소 수정은 구현, USER-ONLY는 무거운 실행에 적용한다.
- 연구 guide를 읽었다는 보고는 로딩 확인일 뿐 연구 품질·novelty·수학적 정확성의 검증이 아니다.
  이 설치 확인을 위해 연구 아이디어를 억지로 생성하거나 별도 평가 실험을 실행하지 않는다.
- `.claude/research-workflow/guides/monk.md`의 존재와 CLAUDE.md·research guide·engineer의 연결을 확인한다.
  연구 모드는 새 과제에서 standard, 사용자가 선택한 과제에서 monk이며 STATE로 복원한다.
  이 설치 확인은 monk를 활성화하거나 관련 방법론 survey를 수행하는 요청이 아니다.
  Monk의 정보 사용 규칙을 읽었다는 사실도 실제 행동 준수나 novelty의 검증은 아니다.

## 선택적 Interactive research 설치 확인
- `.claude/research-workflow/guides/interactive-research.md`와 CLAUDE.md·시작 안내·research/goal guide의
  연결을 확인한다. 설치·이 확인만으로 활성화하지 않는다. 사용자 선택 과제의 현재 phase와 대기 결정은 보존한다.
- Phase 내부 자율성과 사용자 전환 선택, goal·monk 독립성, 기존 구현·USER-ONLY 경계를 확인한다.
  기존 STATE·사용자 goal config·ledger를 갱신하거나 새 transition guard를 실행하지 않는다.
- 파일·문구 확인은 runtime 행동 준수·창의성·연구 성과의 검증이 아니다.

## Engineer에 보낼 작업
- Agent 도구: `subagent_type: "engineer"`, `effort: "high"`. `model` 인자는 넘기지 않는다.
- Mode: inspect. 파일 수정·코드 실행·추가 agent 생성 금지.
- Read: CLAUDE.md, .claude/agents/engineer.md.
- Return: (a) heavy final tests의 실행 주체, (b) main의 직접 코드 읽기/검수 권한,
  (c) 명세 변경의 결정 주체를 짧게 답하고 해당 파일/절을 가리킨다.
- Effort는 위임 문자열이 아니라 main이 **실제 spawn의 effort 인자**에서 high로 선택한다.

## 판단
- Main이 실제 engineer spawn/결과 수신을 확인했으면 delegation 확인으로 기록한다.
- 실제 호출 metadata나 도구 반환에서 effort가 확인되면 관찰된 적용값을 기록한다.
- 도구에 high를 보냈지만 최종 resolved effort가 보이지 않으면
  `requested=high; resolved=NOT_VERIFIED`라고 적는다.
- Engineer가 “나는 high다”라고 말한 것은 runtime 설정 증거가 아니다.
- xhigh 호출을 수행하지 않았다면 xhigh runtime 검증은 NOT_RUN이다.
  high가 통과했다는 이유로 둘 다 검증됐다고 하지 않는다.
- 역할 파일의 `effort: high`는 인자 생략 시의 default다. Spawn 인자가 이 default보다 우선하는지,
  `CLAUDE_CODE_EFFORT_LEVEL` 같은 상위 override가 없는지는 관측하지 못했다면 NOT_VERIFIED다.
- 짧은 정책 답변은 지침 이해의 제한적인 증거이지, 장기 행동 준수의 보장이 아니다.
- 다른 업무가 없으면 확인용 thread를 더 사용하지 않고 상태를 짧게 보고한다.

결과는 FILES / DELEGATION / EFFORT / COEXISTENCE / LIMITATIONS로 간단히 정리한다.
설정 실패를 해결하려고 model·권한·settings를 임의 변경하거나 무거운 실험을 실행하지 않는다.
이후 사용자가 연구 시작까지 요청했다면 .claude/research-workflow/RESEARCH_START.txt에 따른다.

## Codex workflow와의 독립 운영 확인
- `.codex/research-workflow-install.json` 또는 AGENTS.md의 CODEX RESEARCH WORKFLOW block이 있으면
  두 workflow가 함께 설치된 프로젝트다. 없으면 이 절은 N/A다.
- Claude Code는 `CLAUDE.md`가 있으면 기본적으로 AGENTS.md를 읽지 않는다. 현재 세션에 Codex block이
  함께 로드되어 있다면(설정 또는 `@AGENTS.md` import) CLAUDE block의 우선 규칙을 적용 중인지 확인한다.
  AGENTS.md의 marker 밖 프로젝트 고유 지침이 CLAUDE.md에 반영되지 않았다면 그 사실을 보고한다.
- `.codex/**`와 AGENTS.md의 Codex block을 읽기만 하고 수정하지 않는다. AGENTS.md의
  CLAUDE-CODEX COEXISTENCE NOTE 유무를 보고한다. 없으면 Codex 쪽은 독립 운영 규칙을 전달받지 못한 상태다.
- `.claude/research-workflow/tools/goal_guard.py`와 `.codex/tools/goal_guard.py`의 내용이 같은지,
  두 설치 metadata의 upstream version이 같은지 확인한다. 다르면 사용자가 goal 인계를 지시하기 전 정리 대상으로 보고한다.
- Codex slot의 파일(research/SESSIONS.codex.md, research/*.codex<N>.md, research/*-codex<N>/)과 이름에
  slot이 없는 이전 경로(research/STATE.md·research/notes/·research/GOAL_CONFIG.md·research/goals/ 등)는
  존재 여부만 보고하고, 사용자가 지시하지 않았다면 내용을 읽거나 수정하지 않는다. 이전 버전에서 Claude가
  Codex와 함께 쓰던 STATE(지금은 research/STATE.codex0.md 또는 research/STATE.md)에 남긴 기록이 있을 수
  있으면 그 사실만 알리고, 옮길 내용은 사용자 지시를 받아 정한다.
  이 확인을 위해 Codex를 실행하거나 상대 harness의 thread를 제어하지 않는다.

## Slot 확인
- `echo $CLAUDE_CODE_SESSION_ID`로 세션 id를 확인할 수 있는지 보고한다. 비어 있으면 slot 배정의 자동 복원은
  NOT_VERIFIED이며 사용자가 번호를 지정해야 한다.
- research/SESSIONS.claude.md와 0번 slot의 research/STATE.claude0.md·research/GOAL_CONFIG.claude0.md,
  research/_templates/의 STATE·SESSIONS·GOAL_CONFIG 양식이 있는지 확인한다.
- CLAUDE.md의 규칙대로 이 세션의 slot을 정해 보고한다. 다른 세션의 active 행을 replaced로 바꿨다면
  그 세션 id와 last active를 함께 알린다. 확인만을 위해 다른 번호의 slot 파일을 만들지 않는다.

## 선택적 Goal 설치 확인
- `.claude/research-workflow/guides/goal.md`, guard, 사용자 GOAL_CONFIG(create-only), template,
  supervisor/qa 역할 파일의 존재를 확인한다. 새 기본 양식은 disabled/unset이며 검증 실패가 정상이다.
  기존 작성본/STATE/goal history는 보존한다.
- 역할 파일은 frontmatter의 name/description/`effort: high`/`disallowedTools: Agent`와 본문 지침을 가지며
  model pin이 없어야 한다. Main 제외3슬롯에 Engineer+QA+Supervisor를 공유하며 single writer는1명이다.
- 사용자가 goal 역할 runtime 확인까지 요청하면 코드를 실행하지 않는 inspect를 역할별 한 번만
  순차 위임한다. QA는 반복 규칙 확인 medium, 최초 evaluator 검토 high; Supervisor routine high,
  중요한 채택/유망방향 기각/논쟁적 기각/방향변경/수학판단 xhigh. 실제 spawn의 effort 인자로 선택한다.
  Thread effort 변경을 followup으로 주장하지 않는다. 필요한 역할이 없으면 해당 gate UNVERIFIED다.
- 요청/관측 effort·실제 결과 수신을 구분한다. 역할 답변은 장기 독립성/과학적 정확성 증명이 아니다.
  검증 요청 없이 새 role을 호출하거나 goal을 시작하지 않는다.
- Helper는 metadata validation/freeze/reservation ledger이며 experiment runner/OS sandbox가 아니다.
  외부 bounded executor의 exact revision과 실제 enforcement를 QA가 검수해야 light proxy를 반복할 수 있다.
  미지원 필수 한도는 NEEDS_USER_RUN. 파일 설치/작은 unittest가 runtime·자원강제를 검증하지 않는다.
  Token/provider 비용은 자동 관측하지 않는다. Goal outcome/연구 품질은 별도 미검증이다.

- GOAL_SETUP managed template와 별도 사용자 SETUP/RUN 배정·준비/QA→완료→init 순서를 확인한다.
  SETUP Markdown 회계/시작 gate는 운영 검수이며 guard가 강제·계측하지 않는다.
  기존 사용자 form의 schema1은 유지하며 준비 비용 확인 없이 init READY를 startup 승인으로 쓰지 않는다.
