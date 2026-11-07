# Run 20261107T091530Z-cli (subscription, 3 trial(s))

## Source: official-cli

CLI `1.5.3`, effort `set by the model id`, command `agy.EXE --print '' --input-format stream-json --output-format stream-json --model gemini-3.8-flash-high --settings {"permissions":{"allow":[],"ask":[],"deny":["read_file(*)","write_file(*)","command(*)","unsandboxed(*)","read_url(*)","execute_url(*)","mcp(*)"]},"toolPermission":"strict","disableSlashCommands":true,"enableTerminalSandbox":true} --disable-slash-commands --print-timeout 1740s`. Answers come from Antigravity CLI print mode (agy --print), Google's CLI for free personal accounts (it replaced Gemini CLI for them on 2026-06-18). Its own agent system prompt and tool list are included (about 8.5k input tokens for a one-word prompt); every tool action is denied by --settings, so it can only answer in text. Not directly comparable with API/OpenRouter cells.

| task | gemini-3.8-flash-high |
|---|---|
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t10_room_rules_scaled | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: FAIL [load] (exec_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |

- gemini-3.8-flash-high: 11/12 passed, mean score 0.917; failures: load 1

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### gemini-3.8-flash-high / t10_room_rules_scaled / trial_2: load
- status `load_error`, load_error `exec_error`, safety_reason `None`, liveness_reason `None`, finish_reason `SUCCESS`, completion_tokens 54254
- load_detail: `AttributeError: module 'psycopg.errors' has no attribute 'TransactionRollbackError'`

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| gemini-3.8-flash-high | t03_expense_budget | trial_1 | 36220 | 285.79 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:26:53+00:00) |
| gemini-3.8-flash-high | t03_expense_budget | trial_2 | 43591 | 341.03 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:31:39+00:00) |
| gemini-3.8-flash-high | t03_expense_budget | trial_3 | 41983 | 319.95 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:37:20+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_1 | 43102 | 313.28 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:42:40+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_2 | 38992 | 269.73 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:47:53+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_3 | 55292 | 403.3 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:52:23+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_1 | 51071 | 404.28 | 2 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:59:06+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_2 | 57446 | 397.48 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:17:20+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_3 | 49470 | 372.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:23:58+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_1 | 44208 | 341.25 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:30:10+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_2 | 54254 | 341.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:35:51+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_3 | 52786 | 398.09 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:41:32+00:00) |

spent_usd: 0.0, api_calls: 14, sessions: 2, complete: True
