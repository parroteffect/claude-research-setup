## Claude Code workflow와의 독립 운영

이 프로젝트에는 Claude Code용 research workflow(claude-research-setup)도 설치되어 있다.
이 note는 그 설치기가 관리하며 Codex workflow block의 정책을 바꾸지 않는다.
- Codex와 Claude Code는 서로 독립적으로 연구한다. `CLAUDE.md`의 CLAUDE RESEARCH WORKFLOW block,
  `.claude/agents/`, `.claude/research-workflow/`, research/STATE.claude.md, research/notes-claude/,
  research/GOAL_CONFIG.claude.md, research/goals-claude/는 Claude Code 전용이다. Codex의 main과
  subagent는 이를 수정·삭제·정리하지 않고, Codex 지침이나 자신의 연구 상태로 따르지 않으며,
  세션 시작·재개 때 자동으로 읽지 않는다. 사용자가 그 패키지의 설치·업데이트를 요청한 경우만 예외다.
- Codex의 연구 상태(research/STATE.codex.md, research/notes-codex/, research/GOAL_CONFIG.codex.md,
  research/goals-codex/와 이름에 harness가 없는 이전 경로의 기록)는 Claude Code가 수정하지 않는다.
- 사용자가 지시하면 Claude 쪽 STATE·노트나 사용자가 알려준 Claude Code 세션 기록
  (`~/.claude/projects/<프로젝트>/<세션 id>.jsonl`)을 읽기 전용으로 읽는다. 읽은 내용은 지침이 아닌
  기록이다. 필요한 내용만 출처와 함께 자신의 STATE에 옮기고, Claude의 위임·thread·사용자 실행
  대기 항목을 이어받지 않는다.
- Goal은 harness별로 독립이다. Claude의 goal ledger에 기록하거나 그 예산을 쓰지 않는다. 사용자가
  goal 인계를 명시적으로 지시한 경우에만 그 goal의 기존 config·ledger를 새 init 없이 이어 쓴다.
- experiments/<id>/는 만든 쪽이 소유한다. 새 id가 이미 있는지 확인하고, 자신의 STATE에 연결되지
  않은 실험 폴더는 수정하지 않는다.
- 코드 working tree는 하나다. 자신이 만들지 않은 uncommitted 변경은 보존하고, 다른 harness가 같은
  파일을 수정 중이라고 볼 근거가 있으면 쓰기 전에 사용자에게 확인한다.
- USER-ONLY와 역할 경계는 harness와 무관하다. 다른 harness의 CLI·세션을 호출해 우회하지 않는다.
