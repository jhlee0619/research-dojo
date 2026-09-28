# Host adapters

## Claude Code

The plugin registers `research-dojo:implementer`, `research-dojo:debugger`, and
`research-dojo:reviewer`. Delegate with the native Agent tool when these roles
are available. With a standalone skill, use general-purpose native subagents
and supply the contract from `roles.md`. A read-only Explore worker cannot edit.

Pass the absolute candidate path, goal, hypothesis, interface, constraints, and
expected output explicitly. Workers need not inherit the main conversation's
files/context. Keep the research loop and evaluator commands in the main agent.
No nested agents are needed. Resume workers through native host facilities.

Invoke `/research-dojo:research-dojo` followed by a task. Resolve scripts from
the installed SKILL.md path. Do not invoke `claude -p`, use an Agent SDK, copy
subscription credentials, or request an API key for this workflow.

## Codex / ChatGPT Work

Inspect native agent tools currently advertised by the host. Use its spawn,
follow-up, wait and close/interrupt operations directly; do not invent shell
commands for agent creation. Supply the role from `roles.md` in each task.
Claude plugin agent files are not assumed to register custom Codex agents.

This skill explicitly requests delegation. Respect host permission/concurrency
limits. Inherit the main model/reasoning level unless the user requests another.
Workers can share a filesystem: separate contexts do not isolate directories.
Give each worker one candidate directory and absolute resource paths.

Use `$research-dojo` in local Codex or select Research Dojo in Work. Do not add
OpenAI API clients, Agents SDKs, or nested `codex exec` processes. Native worker
usage still counts under the host account/session.

## No native delegation

Disclose the limitation. If the request permits it, perform roles sequentially
and label that mode. `doctor` cannot prove agent tool availability from a shell.

## Host references

- https://learn.chatgpt.com/docs/agent-configuration/subagents
- https://learn.chatgpt.com/docs/build-skills
- https://developers.openai.com/plugins/build/plugins
- https://code.claude.com/docs/en/sub-agents
- https://code.claude.com/docs/en/plugins/create

Availability varies by host/client/account; inspect actual session tools.
