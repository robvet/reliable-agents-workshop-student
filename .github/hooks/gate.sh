#!/usr/bin/env bash
# PreToolUse gate for Reliable Agents.
#
# Purpose: force manual approval ("ask") on any terminal / command-execution
# tool so the agent can NEVER run a shell command autonomously, regardless of
# how it was prompted or what auto-approve settings are on. This is a
# code-enforced gate, not an advisory instruction.
#
# All other tools are left untouched (empty output -> VS Code's normal flow).
# Every tool call the agent attempts is appended to an audit log.
#
# Schema: https://code.visualstudio.com/docs/agents/reference/hooks-reference
#   input  (stdin):  { "tool_name": "...", "tool_input": {...}, "tool_use_id": "..." }
#   output (stdout): { "hookSpecificOutput": { "hookEventName": "PreToolUse",
#                        "permissionDecision": "allow" | "deny" | "ask",
#                        "permissionDecisionReason": "..." } }

payload="$(cat)"

tool_name="$(printf '%s' "$payload" | python3 -c 'import sys, json
try:
    print(json.load(sys.stdin).get("tool_name", ""))
except Exception:
    print("")' 2>/dev/null)"

# Audit trail: record every tool the agent attempts to call. Use this file to
# confirm the exact tool_name VS Code passes for terminal execution and tighten
# the match list below if needed.
log="${TMPDIR:-/tmp}/reliable-agents-tool-audit.log"
printf '%s\t%s\n' "$(date -u +%FT%TZ)" "${tool_name:-<unknown>}" >> "$log" 2>/dev/null || true

case "$tool_name" in
  run_in_terminal | create_and_run_task | run_task | run_vscode_command)
    printf '%s' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Reliable Agents policy: terminal / command execution requires manual approval."}}'
    ;;
  *)
    : # emit nothing -> default VS Code approval flow applies
    ;;
esac

exit 0
