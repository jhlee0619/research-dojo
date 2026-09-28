# Research Dojo

[English](README.md) | **한국어**

Claude Code·Codex의 내장 서브에이전트로 코드를 개선하고 실제 실험으로 비교합니다. 별도 LLM API 키나 모델 서버는 필요 없으며, 호스트 사용량 한도는 적용됩니다.

Python 3.10+, Linux/macOS/WSL, 로그인된 호스트와 네이티브 서브에이전트가 필요합니다.

## 시작하기

```bash
git clone https://github.com/jhlee0619/research-dojo.git
cd research-dojo
```

**Claude Code**

```bash
claude --plugin-dir ./plugins/research-dojo
```

**Codex**

```bash
codex plugin marketplace add /absolute/path/to/research-dojo
```

Codex 플러그인 관리 화면에서 `research-dojo-local`의 `research-dojo`를 설치·활성화하세요.

## 사용하기

Claude Code에서는 `/research-dojo:research-dojo`, Codex에서는 `$research-dojo`로 요청하세요.

> CPU 예제를 실행해줘. 내장 서브에이전트로 후보 2개를 구현하고 baseline과 비교한 뒤, 가장 좋은 측정 결과의 코드를 내보내줘.

[실험 가이드](plugins/research-dojo/skills/research-dojo/references/task-protocol.md) · [검증과 한계](VALIDATION.md)

[CC BY-NC 4.0](LICENSE). [AIRA Dojo](https://github.com/facebookresearch/aira-dojo/)에서 영감을 받은 독립 구현입니다. [출처·라이선스 이력](NOTICE.md)을 확인하세요.
