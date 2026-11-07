# Run final-gemini-3.8-flash-high-cli (subscription, 3 trial(s))

> Note: t04_room_booking/trial_2 was asked twice: the first call ran agy's built-in search_web tool 9 times (not covered by the --settings deny list; no documented rule for it), so the containment check stopped the run and that answer was never graded (kept as *.containment_stop.txt). Re-asked with unchanged settings on the user's decision (2026-11-07); an invalid call, not a re-sample of a result.

> 12 trial(s) reused from earlier runs with the same model, CLI, effort and prompt (graded again by the current grader): t03_expense_budget/trial_1 ← 20261107T091530Z-cli, t03_expense_budget/trial_2 ← 20261107T091530Z-cli, t03_expense_budget/trial_3 ← 20261107T091530Z-cli, t08_expense_endpoints/trial_1 ← 20261107T091530Z-cli, t08_expense_endpoints/trial_2 ← 20261107T091530Z-cli, t08_expense_endpoints/trial_3 ← 20261107T091530Z-cli, t09_room_rules/trial_1 ← 20261107T091530Z-cli, t09_room_rules/trial_2 ← 20261107T091530Z-cli, t09_room_rules/trial_3 ← 20261107T091530Z-cli, t10_room_rules_scaled/trial_1 ← 20261107T091530Z-cli, t10_room_rules_scaled/trial_2 ← 20261107T091530Z-cli, t10_room_rules_scaled/trial_3 ← 20261107T091530Z-cli

## Source: official-cli

CLI `1.5.3`, effort `set by the model id`, command `agy.EXE --print '' --input-format stream-json --output-format stream-json --model gemini-3.8-flash-high --settings {"permissions":{"allow":[],"ask":[],"deny":["read_file(*)","write_file(*)","command(*)","unsandboxed(*)","read_url(*)","execute_url(*)","mcp(*)"]},"toolPermission":"strict","disableSlashCommands":true,"enableTerminalSandbox":true} --disable-slash-commands --print-timeout 1740s`. Answers come from Antigravity CLI print mode (agy --print), Google's CLI for free personal accounts (it replaced Gemini CLI for them on 2026-06-18). Its own agent system prompt and tool list are included (about 8.5k input tokens for a one-word prompt); every tool action is denied by --settings, so it can only answer in text. Not directly comparable with API/OpenRouter cells.

| task | gemini-3.8-flash-high |
|---|---|
| t01_flash_sale | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) ⚠ latent_api_error<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) ⚠ latent_api_error<br>**pass^3: yes** |
| t02_on_call | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t04_room_booking | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t05_wallet_transfer | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t06_idempotent_payment | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t07_node_drain | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) ⚠ latent_api_error<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t10_room_rules_scaled | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: FAIL [load] (exec_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) ⚠ latent_api_error<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |

- gemini-3.8-flash-high: 29/30 passed, mean score 0.967; failures: load 1

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### gemini-3.8-flash-high / t10_room_rules_scaled / trial_2: load
- status `load_error`, load_error `exec_error`, safety_reason `None`, liveness_reason `None`, finish_reason `SUCCESS`, completion_tokens 54254
- load_detail: `AttributeError: module 'psycopg.errors' has no attribute 'TransactionRollbackError'`

## Warnings (do not change the score)

- gemini-3.8-flash-high / t01_flash_sale / trial_2: **latent_api_error** `psycopg.errors.TransactionRollbackError` at line(s) 27: not defined in the pinned psycopg 3.3.6 (passed anyway: the name is looked up only when that line runs)
- gemini-3.8-flash-high / t01_flash_sale / trial_3: **latent_api_error** `psycopg.errors.TransactionRollbackError` at line(s) 33: not defined in the pinned psycopg 3.3.6 (passed anyway: the name is looked up only when that line runs)
- gemini-3.8-flash-high / t08_expense_endpoints / trial_2: **latent_api_error** `psycopg.errors.TransactionRollbackError` at line(s) 53, 113, 154: not defined in the pinned psycopg 3.3.6 (passed anyway: the name is looked up only when that line runs)
- gemini-3.8-flash-high / t10_room_rules_scaled / trial_2: **latent_api_error** `psycopg.errors.TransactionRollbackError` at line(s) 8: not defined in the pinned psycopg 3.3.6

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| gemini-3.8-flash-high | t01_flash_sale | trial_1 | 44564 | 334.65 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:21:40+00:00) |
| gemini-3.8-flash-high | t01_flash_sale | trial_2 | 35454 | 260.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:27:15+00:00) |
| gemini-3.8-flash-high | t01_flash_sale | trial_3 | 55344 | 397.64 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:31:35+00:00) |
| gemini-3.8-flash-high | t02_on_call | trial_1 | 38480 | 273.17 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:38:12+00:00) |
| gemini-3.8-flash-high | t02_on_call | trial_2 | 41327 | 303.49 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:42:46+00:00) |
| gemini-3.8-flash-high | t02_on_call | trial_3 | 39101 | 262.18 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:47:49+00:00) |
| gemini-3.8-flash-high | t03_expense_budget | trial_1 | 36220 | 285.79 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:26:53+00:00) |
| gemini-3.8-flash-high | t03_expense_budget | trial_2 | 43591 | 341.03 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:31:39+00:00) |
| gemini-3.8-flash-high | t03_expense_budget | trial_3 | 41983 | 319.95 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:37:20+00:00) |
| gemini-3.8-flash-high | t04_room_booking | trial_1 | 42886 | 298.45 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T12:52:11+00:00) |
| gemini-3.8-flash-high | t04_room_booking | trial_2 | 48525 | 304.67 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:14:00+00:00) |
| gemini-3.8-flash-high | t04_room_booking | trial_3 | 60400 | 386.68 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:19:05+00:00) |
| gemini-3.8-flash-high | t05_wallet_transfer | trial_1 | 46686 | 301.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:25:31+00:00) |
| gemini-3.8-flash-high | t05_wallet_transfer | trial_2 | 39530 | 278.86 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:30:32+00:00) |
| gemini-3.8-flash-high | t05_wallet_transfer | trial_3 | 47629 | 370.86 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:35:11+00:00) |
| gemini-3.8-flash-high | t06_idempotent_payment | trial_1 | 31298 | 251.68 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:41:22+00:00) |
| gemini-3.8-flash-high | t06_idempotent_payment | trial_2 | 25802 | 219.82 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:45:34+00:00) |
| gemini-3.8-flash-high | t06_idempotent_payment | trial_3 | 32286 | 264.16 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:49:14+00:00) |
| gemini-3.8-flash-high | t07_node_drain | trial_1 | 50934 | 406.98 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T13:53:38+00:00) |
| gemini-3.8-flash-high | t07_node_drain | trial_2 | 51947 | 442.19 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T14:00:25+00:00) |
| gemini-3.8-flash-high | t07_node_drain | trial_3 | 43662 | 350.61 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T14:07:47+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_1 | 43102 | 313.28 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:42:40+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_2 | 38992 | 269.73 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:47:53+00:00) |
| gemini-3.8-flash-high | t08_expense_endpoints | trial_3 | 55292 | 403.3 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:52:23+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_1 | 51071 | 404.28 | 2 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T09:59:06+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_2 | 57446 | 397.48 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:17:20+00:00) |
| gemini-3.8-flash-high | t09_room_rules | trial_3 | 49470 | 372.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:23:58+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_1 | 44208 | 341.25 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:30:10+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_2 | 54254 | 341.05 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:35:51+00:00) |
| gemini-3.8-flash-high | t10_room_rules_scaled | trial_3 | 52786 | 398.09 | 1 | SUCCESS | Google sign-in (agy --print) (model shown gemini-3.8-flash-high, 2026-11-07T10:41:32+00:00) |

spent_usd: 0.0, api_calls: 19, sessions: 2, complete: True
