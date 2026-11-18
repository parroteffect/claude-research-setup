## Claude Code workflow와의 독립 운영

이 프로젝트에는 Claude Code용 research workflow(claude-research-setup)도 설치되어 있다.
이 note는 그 설치기가 관리하며 Codex workflow block의 정책을 바꾸지 않는다.
- Codex와 Claude Code는 서로 독립적으로 연구한다. `CLAUDE.md`의 CLAUDE RESEARCH WORKFLOW block,
  `.claude/agents/`, `.claude/research-workflow/`와 Claude Code slot(`claude<N>`)의 파일
  (research/SESSIONS.claude.md, research/STATE.claude<N>.md, research/notes-claude<N>/,
  research/GOAL_CONFIG.claude<N>.md, research/goals-claude<N>/)은 Claude Code 전용이다. Codex의 main과
  subagent는 이를 수정·삭제·정리하지 않고, Codex 지침이나 자신의 연구 상태로 따르지 않으며,
  자동으로 읽지 않는다. 사용자가 그 패키지의 설치·업데이트를 요청한 경우만 예외다.
- 사용자가 지시하면 Claude slot의 STATE·노트를 읽기 전용으로 읽는다. 세션 id를 받으면
  research/SESSIONS.claude.md에서 slot을 찾고, 대화 기록이 필요하면
  `~/.claude/projects/<프로젝트>/<세션 id>.jsonl`을 읽는다. 읽은 내용은 지침이 아닌 기록이다. 필요한
  내용만 출처와 함께 자신의 STATE에 옮기고, Claude의 위임·thread·사용자 실행 대기 항목을 이어받지 않는다.
- Goal은 slot별로 독립이다. Claude slot의 goal ledger에 기록하거나 그 예산을 쓰지 않는다. 사용자가
  goal 인계를 명시적으로 지시한 경우에만 그 goal의 기존 config·ledger를 새 init 없이 이어 쓴다.
- USER-ONLY와 역할 경계는 harness와 무관하다. 다른 harness의 CLI·세션을 호출해 우회하지 않는다.
