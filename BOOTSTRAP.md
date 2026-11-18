# Bootstrap contract — 설치를 맡은 Claude Code에게

목표는 **사용자가 현재 작업하려는 연구 프로젝트**에 이 workflow를 설치하는 것이다.
Main은 설치에 필요한 파일 확인·병합·가벼운 정적 검증을 직접 수행한다.
설치되지 않은 engineer를 먼저 호출해야 한다는 규칙은 없다.
본 문서는 보안·사용자 권한을 우회하는 허가가 아니며, 연구 코드 변경이나 실험 실행도 허용하지 않는다.

## 반드시 유지할 결과

- Main은 Research Lead이며 새로운 연구 아이디어·메커니즘·수학적 분석을 직접 발전시킨다.
  필요한 실제 코드·diff·호출부·테스트도 직접 읽고 검수한다.
- 출력 간결함·최소 구현 수정·USER-ONLY 실행을 연구 탐색의 폭과 깊이 제한으로 바꾸지 않는다.
- Engineer가 구현·가벼운 검증·사용자 실행 RUNBOOK 준비를 맡는다.
- Main model/effort는 사용자 선택을 그대로 보존한다.
- Engineer는 default `high`, 필요하면 main이 실제 spawn의 `effort` 인자로 `xhigh`; `max` 사용 금지.
  역할 파일의 `effort: high`는 default로 유지하고 `model`은 고정하지 않는다.
- 무거운 실제 테스트·학습·평가·benchmark·데이터 준비는 사용자만 실행한다.
- 설치 요청만으로 monk·interactive-research·goal을 활성화하지 않는다.
- **Codex workflow가 같은 프로젝트에 있으면 그대로 보존한다.** `.codex/**`와 `AGENTS.md`의
  `CODEX RESEARCH WORKFLOW` block은 읽기만 한다. Codex의 연구 상태(`research/STATE.codex.md`,
  `research/notes-codex/`, `research/GOAL_CONFIG.codex.md`, `research/goals-codex/`)와 이름에 harness가 없는
  이전 경로(`research/STATE.md` 등)는 수정하지 않고, 설치를 위해 내용을 읽을 필요도 없다.

## 1. 소스와 대상을 먼저 확정한다

사용자가 제공한 경로 또는 URL의 README와 이 파일을 읽는다. Revision을 지정했다면 그것을 사용하고,
없다면 접근한 source commit을 기록한다. 설치 도중 다른 revision의 파일을 섞지 않는다.

대상은 **사용자의 연구 프로젝트**다. 현재 작업 경로와 Git root를 확인한다. Source repo, HOME,
`~/.claude`, 임시 다운로드 디렉터리를 설치 대상으로 혼동하지 않는다. 대상을 고를 근거가 없으면 경로만 확인한다.

소스는 대상 밖에 둔다. 소스의 hook·submodule·임의 setup 명령을 실행하지 않는다.
실행 전에 `scripts/install.py`, `manifest.json`, 변경될 payload를 읽는다.
확인하지 않은 원격 코드를 바로 실행하지 않고, 토큰을 명령·문서·로그에 기록하지 않는다.

## 2. 기존 프로젝트와 환경을 읽기 전용으로 확인한다

- `CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/`, 하위 directory의 CLAUDE.md.
- `.claude/agents/`, `.claude/settings.json`·`settings.local.json`의 관련 key, 연구 상태 파일, Git 변경 상태.
- `AGENTS.md`와 `.codex/`: Codex workflow가 설치되어 있는지, `AGENTS.md`에 Codex block 밖의
  프로젝트 고유 지침이 있는지.
- `claude --version` 같은 가벼운 확인만 사용한다. 자동 로그인·CLI 업데이트·패키지 설치는 하지 않는다.
- 현재 파일을 수정 중인 다른 세션·harness가 있으면 설치와 겹치지 않게 사용자에게 확인한다.

Main의 model/effort, 권한, hook, MCP, 인증 설정을 수정하지 않는다. 설정 파일은 관련 key만 읽고 secret을 출력하지 않는다.

**AGENTS.md fallback.** Claude Code는 `CLAUDE.md`(또는 `.claude/CLAUDE.md`, `CLAUDE.local.md`)가 없을 때만
`AGENTS.md`를 프로젝트 지침으로 읽는다. 이 설치가 `CLAUDE.md`를 처음 만든다면 그 fallback이 끝난다.
`AGENTS.md`에 Codex block 밖의 프로젝트 고유 지침(빌드·보안·코딩 규칙 등)이 있으면 설치기가
`ATTENTION`으로 알린다. 그 경우 다음 중 하나로 해소하고 무엇을 했는지 보고한다.

1. 권장: Claude도 따라야 하는 프로젝트 고유 지침을 `CLAUDE.md`의 managed block **밖**에 옮긴다.
   Codex 전용 내용(`.codex/` 설정, Codex block)은 옮기지 않는다. `AGENTS.md`는 수정하지 않는다.
2. 사용자가 원하면 `CLAUDE.md`에 `@AGENTS.md` import를 두거나 project instructions 설정을 바꾼다.
   이때 Codex block도 함께 로드되지만 CLAUDE block이 우선 규칙을 가진다. 설정 변경은 사용자가 직접 한다.

의미가 충돌하는 지침을 단순히 둘 다 붙인 뒤 성공이라고 하지 않는다. 이전의 “agent가 승인 후 heavy run”
규칙은 USER-ONLY 정책에 맞춰 해소하고, 더 엄격한 보안 제한은 유지한다.

## 3. 계획을 검토하고 설치한다

Python 3.9+가 이미 있는 경우 아래를 사용한다. 실제 절대 경로로 치환하고 인자를 quote한다.

```sh
python3 /path/to/source/scripts/install.py --target /path/to/research-project --source-revision REVIEWED_COMMIT
```

기본값은 **dry run**이다. Payload checksum, 파일 충돌, 변경 목록과 `ATTENTION`/`CODEX_DETECTED` 안내를 확인한다.
계획이 요청 범위 안이면 형식적 승인 대기 없이 다음을 수행한다. 환경이 요구하는 실제 권한 승인은 정상 절차를 따른다.

```sh
python3 /path/to/source/scripts/install.py --target /path/to/research-project --source-revision REVIEWED_COMMIT --apply
python3 /path/to/source/scripts/install.py --target /path/to/research-project --check
```

| 대상 | 방식 |
|---|---|
| `CLAUDE.md` | 기존 프로젝트 내용을 보존하고 `CLAUDE RESEARCH WORKFLOW` managed block 추가/갱신 |
| `.claude/agents/{engineer,qa,supervisor}.md`, `.claude/research-workflow/**` | 신규 생성 또는 확인된 미수정 배포본만 갱신 |
| `research/STATE.claude.md`, `research/GOAL_CONFIG.claude.md` | 없을 때만 생성; 기존 파일은 보존 |
| `research/STATE.codex.md`, `research/GOAL_CONFIG.codex.md`, `research/goals-codex/`, `research/notes-codex/` | Codex 쪽 연구 상태. 절대 쓰지 않음 |
| `research/STATE.md`, `research/GOAL_CONFIG.md`, `research/goals/`, `research/notes/` | Codex 5.5.0 전의 경로. 절대 쓰지 않음 |
| `research/_templates/*`, `experiments/_templates/*` | 없으면 생성. Codex workflow가 있으면 그 패키지 소유로 보고 절대 덮어쓰지 않음 |
| `AGENTS.md` | Codex workflow가 감지될 때만 별도 marker의 공존 note를 끝에 추가. Codex block은 불변 |
| `.gitignore` | 설치 백업 폴더 제외 block만 추가 |
| `.codex/**`, `.claude/settings*.json` | 절대 쓰지 않음 |

설치 출처·version·hash는 `.claude/research-workflow/install.json`에, 설치 전 원본은
`.claude/research-workflow/backups/<id>/`에 남는다. 백업을 공개 저장소에 올리지 않는다.
설치는 파일별 atomic replacement이며 여러 파일 전체에 대한 transaction은 아니다.

사용자가 `AGENTS.md`를 전혀 건드리지 않기를 원하면 `--no-codex-note`를 쓴다. 이 경우 Codex 쪽은
`.claude/`·`CLAUDE.md`·Claude의 연구 상태를 보존하고 자동으로 읽지 말라는 규칙을 전달받지 못한다는 점을 보고한다.

### 이전 버전(`5.4.0+claude.1`)에서 올릴 때

그 버전은 `research/STATE.md`와 goal을 Codex와 함께 썼다. 이 버전은 Claude의 연구 상태를
`research/STATE.claude.md`·`research/notes-claude/`·`research/GOAL_CONFIG.claude.md`·`research/goals-claude/`로 나누고,
Codex 패키지(5.5.0)는 자기 상태를 `research/STATE.codex.md` 등으로 옮긴다. 두 패키지를 같이 올리도록 안내한다.

- 이 설치기는 새 파일을 빈 양식으로 만들 뿐, 함께 쓰던 STATE의 내용을 복사하거나 고치지 않는다.
  그 파일은 Codex 설치기를 먼저 돌렸으면 `research/STATE.codex.md`에, 아니면 `research/STATE.md`에 있다.
  `ATTENTION … starts empty`가 가리키는 경로와 아래 선택지를 사용자에게 보고한다.
- `research/STATE.md`를 `research/STATE.codex.md`로 옮기는 것은 Codex 설치기의 일이다. 이 설치기나 설치를
  맡은 Claude가 대신 옮기지 않는다. 사용자가 요청한 경우에만 Codex 설치기를 실행한다.
- 옮길 내용은 사용자가 정한다. 사용자가 지시하면 그 파일을 읽기 전용으로 읽고 Claude 작업에
  해당하는 항목만 출처와 함께 `research/STATE.claude.md`에 옮긴다. 원본에서 지우지 않는다.
- Claude가 이전 버전에서 시작해 `research/goals/` 아래에 ledger가 있는 goal은 옮기거나 새로 init하지 않는다.
  사용자가 계속하라고 지시하면 그 goal의 기존 config·ledger 경로를 그대로 쓴다.
- 설치 중에 임의로 파일 이름을 바꾸거나 함께 쓰던 STATE를 `research/STATE.claude.md`로 복사하지 않는다.

### Codex workflow가 함께 있을 때

- 설치 순서는 상관없다. Codex가 나중에 설치되면 이 설치기를 한 번 더 실행해 note를 추가한다.
- `ATTENTION policy revisions differ` 또는 `goal guard copies differ`가 나오면 고치려고 `.codex/`를 수정하지 않는다.
  사용자에게 두 패키지의 upstream version을 맞추도록 알리고, 그 전에는 상대 harness가 시작한 goal을 이어받지 않게 한다.
- `PRESERVED shared …` 안내는 정상이다. 공유 템플릿은 Codex 패키지가 갱신한다.
- 설치 확인을 위해 Codex를 실행하거나 Codex 설치기를 대신 돌리지 않는다. 사용자가 요청한 경우만 예외다.
- root `AGENTS.override.md`가 있으면 Codex는 그것을 읽는다. Note를 그 파일에 수동으로 병합해야 하는지 사용자에게 알린다.

### 자동 병합이 멈추는 경우

사용자 수정이 있는 managed file, 출처를 알 수 없는 block, symlink, 같은 이름의 다른 subagent 파일,
`.claude/CLAUDE.md`에 이미 있는 block 등은 자동 덮어쓰기 대상이 아니다.

이때 읽을 수 있는 근거로 동일한 정책을 충족하는 최소 수동 병합을 수행한다. 단 다음을 지킨다.

1. 변경 대상 원본과 Git 상태를 보존한다.
2. 프로젝트 고유 지침·보안 제한을 유지하며 충돌 부분만 고친다.
3. Main model/effort·권한 관련 설정은 건드리지 않는다.
4. 기존 custom `engineer`의 프로젝트 고유 지침은 보존하되, frontmatter는 `effort: high`,
   `model` 미지정, `disallowedTools`에 `Agent` 포함이라는 계약을 만족시킨다.
5. `CLAUDE.md`가 `AGENTS.md`로의 symlink이면 symlink를 따라 쓰지 않는다. 사용자와 상의해 실제 파일로
   바꾸는 방안(필요하면 `@AGENTS.md` import 포함)을 제안하고, 승인 전에는 `BLOCKED`로 남긴다.
6. 수동으로 병합한 파일·이유·미확인 사항을 최종 보고한다. Metadata를 위조하거나 marker만 붙여 우회하지 않는다.

Python 3.9+가 없으면 dependency를 설치하지 말고 위 규칙과 `manifest.json`의 대응표로 파일을 병합한다.

## 4. 정적 검증과 실제 적용을 구분한다

설치기의 `--check`는 **로컬 파일·frontmatter·block 확인**이다. 다음까지 확인했다고 확대하지 않는다.

- User/managed 설정과 환경 변수(`CLAUDE_CODE_EFFORT_LEVEL` 등)를 포함한 effective model/effort.
- 현재 세션의 instruction chain, `engineer` 등 subagent의 실제 등록.
- 실제 spawn에 적용된 reasoning effort와 행동 준수.
- 다른 harness(Codex)의 runtime 동작.

Claude Code는 세션 시작 시 지침을 읽는다. `.claude/agents/` 디렉터리가 이번에 처음 생겼다면 재시작 전에는
subagent가 등록되지 않을 수 있다. 파일 설치 후 기존 세션에 즉시 적용됐다고 가정하지 말고,
새 세션에서 `.claude/research-workflow/VERIFY_SETUP.md`로 확인하도록 안내한다.
설치 확인을 핑계로 별도 Claude Code 프로세스를 자동 실행하거나 현재 세션을 종료하지 않는다.

## 5. 종료 보고

연구 결과를 만들거나 테스트를 확장하지 말고 다음을 짧게 보고한다.

- Source revision, 실제 대상 경로, 변경/보존/수동 병합한 파일.
- 백업 경로, 정적 검증 PASS/FAIL/NOT_VERIFIED, `REVIEW` 항목.
- `FILES_INSTALLED` / `PARTIAL` / `BLOCKED`, runtime은 `NOT_VERIFIED` 여부.
- Codex workflow 공존 상태: 감지 여부, note 추가 여부, version·guard 일치 여부, AGENTS.md fallback 처리,
  새로 만든 Claude 연구 상태 파일과 `starts empty` 안내 여부.
- 재시작이 필요하면 다음에 붙여넣을 메시지를 제공하고 멈춘다.

```text
CLAUDE.md와 .claude/research-workflow/VERIFY_SETUP.md를 읽고 설치 적용 상태를 확인해줘.
등록된 engineer에 짧은 읽기 전용 확인을 high로 위임하되 코드와 실험은 실행하지 마.
확인된 설정과 확인하지 못한 runtime 정보는 구분해줘.
그다음 .claude/research-workflow/RESEARCH_START.txt에 따라 연구 상태를 파악해줘.
```

## 복구

백업의 `RESTORE.json`에는 각 경로의 기존 존재 여부와 before/after hash가 있다.
기존 파일은 같은 상대 경로의 백업 원본으로 복구할 수 있다.
**현재 파일이 설치 후 다른 작업으로 바뀌었다면 자동으로 되돌리지 않는다.**
새로 생긴 파일도 현재 내용이 설치본 그대로인지 먼저 확인하고, 사용자 요청 없이 삭제하지 않는다.
이 패키지를 제거해도 `.codex/`, Codex block, Codex의 연구 상태, 공유 템플릿은 남겨 둔다.
