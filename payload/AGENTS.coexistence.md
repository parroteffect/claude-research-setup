## Claude Code workflow와의 공존

이 프로젝트에는 Claude Code용 research workflow(claude-research-setup)도 설치되어 있다.
이 note는 그 설치기가 관리하며 Codex workflow block의 정책을 바꾸지 않는다.
- `CLAUDE.md`의 CLAUDE RESEARCH WORKFLOW block, `.claude/agents/`, `.claude/research-workflow/`는
  Claude Code 전용이다. Codex의 main과 subagent는 이를 수정·삭제·정리하지 않고 Codex 지침으로
  따르지도 않는다. 사용자가 그 패키지의 설치·업데이트를 요청한 경우만 예외다.
- research/STATE.md·연구 노트·research/GOAL_CONFIG.md·research/goals/·experiments/는 두 harness가
  공유한다. 세션 시작·재개 때 다시 읽고 다른 harness가 남긴 결정·위임·사용자 실행 대기 항목을 보존한다.
- 한 checkout의 writer는 harness를 통틀어 하나다. 다른 harness가 같은 파일을 수정 중이라고 볼
  근거가 있으면 쓰기 전에 사용자에게 확인한다. STATE의 위임·thread·effort 기록에는
  harness(codex / claude)를 적고, 다른 harness의 thread를 기존 thread로 간주하지 않는다.
- Goal의 config·계약·SETUP/RUN 배정·ledger는 harness 공통으로 하나다. Harness를 바꿔 재개해도
  새 init·예산 초기화·중복 예약을 하지 않는다.
- USER-ONLY와 역할 경계는 harness와 무관하다. 다른 harness의 CLI·세션을 호출해 우회하지 않는다.
