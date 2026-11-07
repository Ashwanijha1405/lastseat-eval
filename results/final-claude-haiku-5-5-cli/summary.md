# Run final-claude-haiku-5-5-cli (subscription, 3 trial(s))

## Source: official-cli

CLI `2.1.319 (Claude Code)`, effort `high`, command `claude.EXE -p --model claude-haiku-5-5 --effort high --output-format json --tools '' --safe-mode --strict-mcp-config --disable-slash-commands --no-session-persistence`. Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is included before the task prompt, so these cells are not directly comparable with API/OpenRouter cells.

| task | claude-haiku-5-5 |
|---|---|
| t01_flash_sale | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t02_on_call | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t04_room_booking | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t05_wallet_transfer | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t06_idempotent_payment | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t07_node_drain | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: FAIL [spec] 0.50 (sa 0.50 / so 0.00 / li 0.00)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t10_room_rules_scaled | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |

- claude-haiku-5-5: 29/30 passed, mean score 0.983; failures: spec 1

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### claude-haiku-5-5 / t09_room_rules / trial_1: spec
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `end_turn`, completion_tokens 10516
- solo FAIL: a booking moves within a full day (it does not count against itself): returned False, expected True; violated: expected state: SELECT starts_at = '2026-11-09T15:00:00Z' FROM bookings WHERE id = 1 (got [(False,)])
- scenario `two moves between two days in opposite directions, both fit`: status ok, safe=True (0 unsafe), live=False (148 unlive) of 148 schedules, exhaustive=True, reproduced=True
- scenario `a move within a day and a booking on that day, both fit`: status ok, safe=True (0 unsafe), live=False (80 unlive) of 119 schedules, exhaustive=True, reproduced=True
- counterexample: `results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_1.txt`
- counterexample: `results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_2.txt`
- counterexample: `results/final-claude-haiku-5-5-cli/claude-haiku-5-5/t09_room_rules/trial_1/counterexample_3.txt`

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| claude-haiku-5-5 | t01_flash_sale | trial_1 | 1303 | 8.21 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:15:24+00:00) |
| claude-haiku-5-5 | t01_flash_sale | trial_2 | 3357 | 16.99 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:15:32+00:00) |
| claude-haiku-5-5 | t01_flash_sale | trial_3 | 2236 | 12.17 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:15:50+00:00) |
| claude-haiku-5-5 | t02_on_call | trial_1 | 5097 | 24.82 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:16:02+00:00) |
| claude-haiku-5-5 | t02_on_call | trial_2 | 3982 | 20.05 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:16:27+00:00) |
| claude-haiku-5-5 | t02_on_call | trial_3 | 3370 | 17.3 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:16:47+00:00) |
| claude-haiku-5-5 | t03_expense_budget | trial_1 | 5805 | 25.09 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:17:05+00:00) |
| claude-haiku-5-5 | t03_expense_budget | trial_2 | 4285 | 18.69 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:17:30+00:00) |
| claude-haiku-5-5 | t03_expense_budget | trial_3 | 3249 | 15.75 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:17:49+00:00) |
| claude-haiku-5-5 | t04_room_booking | trial_1 | 2481 | 12.04 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:18:05+00:00) |
| claude-haiku-5-5 | t04_room_booking | trial_2 | 3428 | 17.01 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:18:17+00:00) |
| claude-haiku-5-5 | t04_room_booking | trial_3 | 3328 | 16.95 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:18:35+00:00) |
| claude-haiku-5-5 | t05_wallet_transfer | trial_1 | 32973 | 156.44 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:18:52+00:00) |
| claude-haiku-5-5 | t05_wallet_transfer | trial_2 | 3938 | 18.5 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:21:29+00:00) |
| claude-haiku-5-5 | t05_wallet_transfer | trial_3 | 4508 | 21.93 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:21:48+00:00) |
| claude-haiku-5-5 | t06_idempotent_payment | trial_1 | 4187 | 19.89 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:22:10+00:00) |
| claude-haiku-5-5 | t06_idempotent_payment | trial_2 | 5015 | 24.68 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:22:30+00:00) |
| claude-haiku-5-5 | t06_idempotent_payment | trial_3 | 4005 | 19.18 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:22:55+00:00) |
| claude-haiku-5-5 | t07_node_drain | trial_1 | 7646 | 38.18 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:23:14+00:00) |
| claude-haiku-5-5 | t07_node_drain | trial_2 | 6168 | 29.6 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:23:53+00:00) |
| claude-haiku-5-5 | t07_node_drain | trial_3 | 5657 | 26.91 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:24:22+00:00) |
| claude-haiku-5-5 | t08_expense_endpoints | trial_1 | 5732 | 24.85 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:24:50+00:00) |
| claude-haiku-5-5 | t08_expense_endpoints | trial_2 | 8104 | 35.28 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:25:15+00:00) |
| claude-haiku-5-5 | t08_expense_endpoints | trial_3 | 15622 | 69.79 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:25:50+00:00) |
| claude-haiku-5-5 | t09_room_rules | trial_1 | 10516 | 44.24 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:27:00+00:00) |
| claude-haiku-5-5 | t09_room_rules | trial_2 | 11651 | 48.72 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:27:45+00:00) |
| claude-haiku-5-5 | t09_room_rules | trial_3 | 11688 | 52.28 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:28:34+00:00) |
| claude-haiku-5-5 | t10_room_rules_scaled | trial_1 | 15831 | 70.39 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:29:26+00:00) |
| claude-haiku-5-5 | t10_room_rules_scaled | trial_2 | 20675 | 90.91 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:30:37+00:00) |
| claude-haiku-5-5 | t10_room_rules_scaled | trial_3 | 22674 | 101.25 | 1 | end_turn | claude.ai (claude -p) (model shown claude-haiku-5-5, 2026-11-07T14:32:08+00:00) |

spent_usd: 0.0, api_calls: 30, sessions: 1, complete: True
