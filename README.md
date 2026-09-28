# Research Dojo

**English** | [한국어](README.ko.md)

Compare and improve code through measured experiments with native Claude Code or Codex subagents. No separate LLM API key or model server is required; host usage limits apply.

Requires Python 3.10+ on Linux/macOS/WSL and a signed-in host with native subagents.

## Quick start

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

Install and enable `research-dojo` from `research-dojo-local` in Codex's plugin manager.

## Use

Invoke `/research-dojo:research-dojo` in Claude Code or `$research-dojo` in Codex:

> Run the CPU demo. Use native subagents to implement two candidates, compare them with the baseline, and export the best measured solution.

[Task guide](plugins/research-dojo/skills/research-dojo/references/task-protocol.md) · [Validation and limits](VALIDATION.md)

[CC BY-NC 4.0](LICENSE). Inspired by [AIRA Dojo](https://github.com/facebookresearch/aira-dojo/); see [attribution and license history](NOTICE.md).
