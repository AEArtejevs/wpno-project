# HUMAN_GATE: CODEX_EXECUTION_HOST_REQUIRED

The R6 targeted independent verification cannot run on the current Codex CLI
execution host while the required feature isolation is enforced. Codex CLI
0.149.1 authenticated and started, but both read-only operations were routed to
the disabled code-mode host and rejected before execution. Shell and unified
execution were explicitly enabled. No verifier command ran and no package file
was modified.

Prompt:

`/home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6/build/R6_CODEX_PRE_FREEZE_VERIFICATION_PROMPT.md`

Prompt SHA-256:

`2da755202b9cc9bee0528da53e564950898b73c467713552ab8ed7894549eb12`

Run this exact fresh, non-resume command only after providing a Codex execution
host that honors `shell_tool`/`unified_exec` while code mode and code-mode host
remain disabled:

```bash
/home/ubuntu/.npm-global/bin/codex exec --ephemeral --ignore-user-config --disable code_mode --disable code_mode_host --disable apps --disable enable_mcp_apps --disable mcp_2026_07_28 --disable multi_agent --disable multi_agent_v2 --disable plugins --disable remote_plugin --disable browser_use --disable browser_use_external --disable computer_use --disable standalone_web_search --enable shell_tool --enable unified_exec -s workspace-write -C /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6/verification_codex_pre_freeze -o /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6/verification_codex_pre_freeze/CODEX_LAST_MESSAGE_RETRY.txt "Read /home/ubuntu/project/WPNO/08.18.26_Level1_Audits_R6/build/R6_CODEX_PRE_FREEZE_VERIFICATION_PROMPT.md completely and execute that verification exactly. Do not modify anything outside the current verification output directory."
```

Do not use `codex login`, `codex logout`, `codex exec resume`, `/resume`, or any
command that changes `CODEX_HOME`. Do not enable code mode or code-mode host.

Required result before orchestration may continue:

`VERIFICATION_PASS_PRE_FREEZE`
