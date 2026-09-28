# Research Dojo 1.0.0

Claude Code와 Codex의 **내장 서브에이전트**로 가설·코딩·디버깅·검토를 나누고,
로컬 CPU에서 실험을 실행하는 Plugin입니다. 별도 LLM API 키, 모델 서버, MCP
서버를 요구하지 않습니다. 호스트 서비스의 로그인·사용량 한도는 그대로 적용됩니다.

실험 실행기는 Python 표준 라이브러리만 사용합니다. Linux/macOS/WSL의 Python
3.10 이상을 지원합니다. Claude Code/Codex 자체는 따로 설치하고 로그인해야 하며,
실제 병렬 위임에는 해당 세션의 네이티브 서브에이전트 기능이 필요합니다.

## 포함 기능

- 공통 연구 Skill: 목표 설정 → 기준 성능 측정 → 후보 병렬 구현 → 실제 평가 → 검토 → 개선
- Claude Code용 implementer/debugger/reviewer 에이전트 정의
- Codex용 네이티브 위임 지침: 호스트가 제공하는 에이전트 도구 사용
- 고정 평가기, 시드별 반복 실행과 중앙값, 코드·평가기 해시 확인
- 최대 시도 횟수, 동시 평가 수, 시간·로그 크기 제한
- 실패·중단 기록, 상태 조회·재개, Markdown/JSON 비교 보고서
- 측정된 코드 사본과 출처 정보 내보내기
- 양쪽 호스트의 Plugin manifest와 로컬 marketplace, 프로젝트 설치·업데이트·제거 도구
- CPU 예제, 자동 검증, CI 설정, 재현 가능한 배포 아카이브 생성 도구

실험 코드는 별도 후보 폴더에서 작성하고 실제 실행 점수로 선택합니다. 코드 작성은
병렬로, 시간 측정은 기본적으로 순차 실행합니다. GPU 학습이 필요한 과제에는 별도
연산 자원이 필요하며, 이 Plugin이 GPU를 제공하지는 않습니다.

## 1. 패키지 확인

압축을 푼 프로젝트 루트에서 실행합니다.

```bash
python3 verify.py
python3 -m unittest discover -s tests -v
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py doctor
```

`verify.py`는 파일 체크섬, manifest 간 일치, 참조 파일, Python 문법을 확인합니다.
호스트가 실제로 Plugin을 로드하는 검증은 아래 설치 단계에서 수행합니다.

## 2. Claude Code

가장 짧은 시작 방법입니다. 이 방식은 해당 세션에서 Plugin을 로드합니다.

```bash
claude plugin validate ./plugins/research-dojo
claude --plugin-dir ./plugins/research-dojo
```

세션에서 입력합니다.

```text
/research-dojo:research-dojo CPU 예제를 만들고 baseline과 서로 다른 후보 2개를 비교해줘. 내장 subagent를 사용하고 최종 결과를 내보내줘.
```

계속 사용할 설치본은 패키지 루트에서 marketplace를 등록합니다.

```bash
claude plugin marketplace add .
claude plugin install research-dojo@research-dojo-local --scope user
```

설치 결과에 따라 새 세션을 열거나 `/reload-plugins`로 적용합니다. 실험할 프로젝트에서
위 Skill 명령을 사용합니다. 등록한 패키지 폴더는 삭제하거나 이동하지 마세요.

## 3. Codex

패키지 루트를 로컬 marketplace로 등록합니다.

```bash
codex plugin marketplace add /absolute/path/to/research-dojo-1.0.0
```

지원되는 Plugin 관리 화면에서 `research-dojo-local` 소스의 Research Dojo를
설치·활성화합니다. 프로젝트에 직접 배치하려면 다음 명령을 사용합니다.

```bash
python3 install.py --project /absolute/path/to/your-project --host codex
```

이 명령은 Plugin과 `.agents/plugins/marketplace.json`을 배치합니다. 필요하면
신뢰하는 프로젝트의 `.codex/config.toml`에 다음 설정을 추가합니다. 기존 내용은
유지하고, 설치 도구가 출력한 실제 marketplace 이름을 사용하세요.

```toml
[plugins."research-dojo@research-dojo-local"]
enabled = true
```

세션에서 `$research-dojo`를 선택하고 다음처럼 요청합니다.

```text
$research-dojo 이 프로젝트의 병목 함수를 개선해줘. 기존 테스트로 정확성을 검사하고,
서로 다른 후보를 native subagent에 맡겨 실제 실행 시간으로 비교해줘.
```

Plugin을 지원하지 않지만 Skill을 지원하는 클라이언트에서는
`plugins/research-dojo/skills/research-dojo` 폴더를 프로젝트의
`.agents/skills/research-dojo`에 복사해 동일한 워크플로우를 사용할 수 있습니다.
Plugin 설치와 중복 등록하지 마세요. Codex는 Claude의 `agents/*.md`를 자동 등록하는
것으로 가정하지 않고, Skill이 각 역할의 작업 지침을 네이티브 서브에이전트에 전달합니다.

## 4. 양쪽 호스트에 프로젝트 단위로 배치

```bash
python3 install.py --project /absolute/path/to/your-project --host both
```

기존 marketplace 이름과 다른 Plugin 항목은 보존합니다. 설치 도구는 호스트 계정이나
전역 설정을 변경하지 않습니다. Claude에서는 대상 프로젝트를 marketplace로 추가한
뒤 출력된 이름으로 설치하세요. Codex에서는 위 활성화 절차를 사용하세요.

업데이트는 새 배포본의 같은 명령을 실행합니다. 설치 파일을 직접 수정했다면 덮어쓰지
않고 중단하므로 먼저 수정본을 보관하세요. 호스트가 캐시한 설치본은 호스트의 Plugin
관리 기능으로 업데이트해야 합니다. 새 공개 릴리스에서는 manifest의 버전도 올리세요.

프로젝트에 배치한 파일을 제거하려면:

```bash
python3 install.py --project /absolute/path/to/your-project --uninstall
```

다른 Plugin과 실험 폴더는 유지합니다. 호스트에 이미 설치된 캐시는 호스트의 Plugin
관리 기능에서 별도로 비활성화/제거합니다.

## 5. 에이전트 없이 실행기를 직접 확인

프로젝트 루트에서 다음을 실행합니다. 아래 명령은 모델 호출 없이 동작합니다.

```bash
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py demo --output demo-task
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py init --task demo-task/task.json --run demo-run
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py run --run demo-run --candidate baseline
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py report --run demo-run
```

CPU 예제는 정수 목록의 모든 쌍에 대한 제곱 차이 합을 계산합니다. baseline은 중첩
반복문입니다. 고정 평가기가 정확성과 실행 시간을 검사하며 후보 개선은 에이전트가
작성합니다. 자체 프로젝트는 task.json의 입력 폴더, 평가 명령, 지표를 설정하세요.

전체 계약은 `plugins/research-dojo/skills/research-dojo/references/task-protocol.md`에
있습니다. 별도 pip 패키지가 필요한 프로젝트는 사용자의 환경에 준비해야 합니다.

## 재개와 결과 내보내기

```text
$research-dojo /absolute/path/to/demo-run 실험을 재개하고 남은 예산 안에서 개선해줘.
```

직접 조회할 때는 다음 명령을 사용합니다.

```bash
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py resume --run demo-run
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py report --run demo-run --format json
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py export --run demo-run --attempt best --output selected-solution
```

`resume`는 진행 중인 프로세스와 남은 작업을 확인하며 모델을 자체 실행하지 않습니다.
Skill이 이 결과를 읽고 연구를 이어갑니다. 최종 내보내기는 현재 편집본 대신 실제 측정한
코드 사본을 사용합니다. 기존 프로젝트에 자동으로 덮어쓰지 않습니다.

## 실행 범위와 검증

실험 폴더 격리와 해시 확인은 실수로 평가 기준이 바뀌는 일을 탐지합니다. 같은 사용자
권한으로 실행한 악의적인 코드를 격리하는 OS sandbox는 아닙니다. 호스트의 기존
권한·샌드박스 정책을 유지하세요. SIGINT/SIGTERM/timeout은 평가 프로세스 그룹을
정리하지만 SIGKILL이나 장비 장애에는 수동 확인이 필요할 수 있습니다.

검증 환경과 확인한 범위는 `VALIDATION.md`에 기록되어 있습니다. Linux의 실제 CPU
실행과 네이티브 서브에이전트 흐름을 확인했습니다. 이 제작 환경에는 Claude Code와
Codex CLI 실행 파일이 없으므로 두 로컬 클라이언트의 실제 Plugin 로더는 검증하지
못했습니다. 지원 클라이언트에서 위 로딩 확인을 수행하세요.

## 배포 및 개발

이 폴더는 두 marketplace 파일을 포함한 배포 가능한 프로젝트입니다. 원하는 Git
저장소에 올리면 같은 상대 경로 구조를 그대로 사용할 수 있습니다. 공개 marketplace
등록이나 외부 저장소 게시 자체는 이 파일 묶음 생성과 별개입니다.

```bash
python3 tools/build_release.py --output /absolute/path/to/research-dojo-release.zip
```

이 명령은 체크섬을 갱신하고 동일 입력에서 동일한 아카이브를 생성합니다. 런타임에는
Python 표준 라이브러리만 필요합니다. 테스트는 실험 복구·평가 무결성·자원 제한·설치
보존 동작을 검증합니다. CI는 Linux/macOS, Python 3.10/3.12 조합으로 구성되어 있습니다.

Research Dojo는 AIRA Dojo의 연구 루프에서 영감을 받은 독립 구현입니다. Meta의
공식 제품, upstream 소스의 포크, MLE-bench 재현판이 아닙니다. 원본 코드나 데이터는
포함하지 않습니다. 이 패키지의 새 코드는 MIT License로 배포합니다.

공식 호스트 문서:

- https://developers.openai.com/plugins/build/plugins
- https://learn.chatgpt.com/docs/build-skills
- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://code.claude.com/docs/en/plugins/create
- https://code.claude.com/docs/en/plugins/install
- https://github.com/facebookresearch/aira-dojo/
