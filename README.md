# Research Dojo 1.0.1

**English** | [한국어](README.ko.md)

Run measured research experiments with **native Claude Code or Codex subagents**
and a local Python runner. Delegate hypotheses, implementation, debugging, and
review to the host's agents; select solutions using actual evaluation results.

No separate LLM API key, model server, or MCP server is required. Your host
account, subscription, and usage limits still apply. Subagents provide reasoning
and code; experiments still need real compute. GPU training still requires a GPU.

**License: [CC BY-NC 4.0](LICENSE).** This release is available for noncommercial
use under its terms. See [attribution and licensing history](NOTICE.md).

## What is included

- A shared research skill: define a goal, measure a baseline, implement candidates,
  evaluate, review, and iterate.
- Claude Code implementer/debugger/reviewer agent definitions and Codex native
  delegation instructions.
- A Python standard-library runner with frozen evaluators, fixed seeds, median
  scores, and hashes of measured code and evaluation inputs.
- Attempt, evaluation concurrency, execution time, and log size limits.
- Failure records, recovery, Markdown/JSON reports, and export of measured snapshots.
- Host plugin manifests, local marketplaces, and a project installer/uninstaller.
- A CPU demo, automated tests, and a reproducible release builder.

Candidates are written in separate directories. Implementation may run in
parallel; timing measurements are sequential by default to reduce interference.
This is an independent project inspired by [AIRA Dojo](https://github.com/facebookresearch/aira-dojo/).
It is not an official Meta product or a reproduction of AIRA's benchmark results.

## Requirements and checkout

Use Python 3.10+ on Linux, macOS, or WSL. Install and sign in to Claude Code or
Codex separately. Parallel delegation requires native subagent tools in your
host session. The runner itself has no pip dependencies; your experiment may.

```bash
git clone https://github.com/jhlee0619/research-dojo.git
cd research-dojo
python3 verify.py
python3 -m unittest discover -s tests -v
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py doctor
```

The verifier checks checksums, manifests, license notices, linked resources, and
Python syntax. Actual host loading is checked separately during installation.

## Claude Code

Load the plugin for a session from the repository root:

```bash
claude plugin validate ./plugins/research-dojo
claude --plugin-dir ./plugins/research-dojo
```

Then ask:

```text
/research-dojo:research-dojo Create the CPU demo. Use native subagents to implement two distinct candidates, compare them with the baseline, and export the best measured solution.
```

For a persistent installation, register this checkout as a local marketplace:

```bash
claude plugin marketplace add .
claude plugin install research-dojo@research-dojo-local --scope user
```

Apply the installation as directed by the host, using a new session or
`/reload-plugins` where supported. Keep the registered checkout in place.

## Codex

Register the checkout as a local marketplace:

```bash
codex plugin marketplace add /absolute/path/to/research-dojo
```

Use the supported plugin management interface to install and enable Research Dojo
from `research-dojo-local`. To place the plugin directly in a project instead:

```bash
python3 install.py --project /absolute/path/to/your-project --host codex
```

The installer writes the plugin and `.agents/plugins/marketplace.json`. If needed,
add the following to a trusted project's `.codex/config.toml`, preserving existing
settings and using the actual marketplace name printed by the installer:

```toml
[plugins."research-dojo@research-dojo-local"]
enabled = true
```

Select `$research-dojo` and ask:

```text
$research-dojo Optimize this project's bottleneck. Check correctness with the existing tests, delegate distinct candidates to native subagents, and compare real execution times.
```

For a client that supports skills but not plugins, copy the **complete**
`plugins/research-dojo/skills/research-dojo` directory, including its `LICENSE` and
`NOTICE.md`, to `.agents/skills/research-dojo` in your project. Avoid installing
both copies. Codex uses the host's native delegation tools; it does not assume
that Claude's `agents/*.md` files are automatically registered.

## Project installation, updates, and removal

Place the plugin for both hosts:

```bash
python3 install.py --project /absolute/path/to/your-project --host both
```

Existing marketplace names and unrelated entries are preserved. The installer
does not change host accounts or global settings. In Claude, add the target
project as a marketplace and install using the printed name. In Codex, enable it
as described above.

Update by running the same command from a newer checkout. The installer refuses
to overwrite modified or unmanaged plugin files; preserve your edits first.
Update any host-managed cached installation through that host's plugin manager.

Remove the project installation:

```bash
python3 install.py --project /absolute/path/to/your-project --uninstall
```

Other plugins and experiment folders remain. Disable or uninstall any cached
host installation separately in the host's plugin manager.

## Try the runner without an agent

These commands run without model calls:

```bash
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py demo --output demo-task
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py init --task demo-task/task.json --run demo-run
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py run --run demo-run --candidate baseline
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py report --run demo-run
```

The demo calculates the sum of squared differences across all pairs of integers.
Its baseline uses nested loops. A fixed evaluator checks correctness and runtime;
agents write the improved candidates. For your own task, configure source folders,
evaluation commands, and metrics in `task.json`. See the
[task protocol](plugins/research-dojo/skills/research-dojo/references/task-protocol.md).

## Resume and export

Ask the skill to continue an existing run:

```text
$research-dojo Resume /absolute/path/to/demo-run and improve the result within the remaining budget.
```

Or inspect and export directly:

```bash
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py resume --run demo-run
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py report --run demo-run --format json
python3 plugins/research-dojo/skills/research-dojo/scripts/dojo.py export --run demo-run --attempt best --output selected-solution
```

`resume` reconciles active/abandoned work; it does not launch a model. The skill
reads that state to continue. Export uses the exact measured snapshot and includes
provenance. It does not overwrite your original project.

## Validation and limits

[VALIDATION.md](VALIDATION.md) records 23 automated tests, an actual native-subagent
workflow, and the successful Linux/macOS × Python 3.10/3.12 CI matrix for the
previous code release. The experiment engine is unchanged in 1.0.1 apart from its
version identifier. Current runs are visible in [GitHub Actions](https://github.com/jhlee0619/research-dojo/actions).

The build environment has no Claude Code or Codex CLI executable, so their actual
plugin loaders have **not** been exercised here. Run the host installation checks
above. WSL is a supported target, but has not been tested separately.

Directory separation and hash checks detect accidental changes; this runner is
**not an OS security sandbox** for hostile code running as the same user. Keep
host permissions and sandbox policies in effect. Timeout/SIGINT/SIGTERM clean up
evaluation process groups; SIGKILL, hardware failures, or hostile daemonized code
may require manual recovery. Demo timings do not establish general performance.

## License and attribution

Copyright (c) 2026 Research Dojo contributors.

Version 1.0.1 is distributed under **Creative Commons Attribution-NonCommercial
4.0 International (CC BY-NC 4.0)**. Retain the supplied attribution and license
information, identify changes when sharing adaptations, and comply with the
noncommercial restriction. Read [LICENSE](LICENSE) for the full terms, including
warranty disclaimers and exceptions; this paragraph is only a summary.

[NOTICE.md](NOTICE.md) records AIRA Dojo's origin and license, independent
implementation scope, and the previous MIT distribution. The change does not
revoke permissions already granted for earlier MIT copies. AIRA's separate
third-party components retain their own terms. This project includes no upstream
source, datasets, model weights, or figures. No affiliation or endorsement is
claimed. The license choice is not a legal clearance or non-infringement guarantee.

## Development

```bash
python3 tools/build_release.py --output /absolute/path/to/research-dojo-release.zip
```

Use a new archive path outside the checkout. The builder refreshes `SHA256SUMS`
and creates the same archive for the same input and root folder name. Tests cover
evaluation integrity, recovery, resource limits, and safe installer updates.
See [CHANGELOG.md](CHANGELOG.md) for release changes.

Host documentation:

- [OpenAI plugin format](https://developers.openai.com/plugins/build/plugins)
- [Skills](https://learn.chatgpt.com/docs/build-skills)
- [Native subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Claude Code plugin creation](https://code.claude.com/docs/en/plugins/create)
- [Claude Code plugin installation](https://code.claude.com/docs/en/plugins/install)
