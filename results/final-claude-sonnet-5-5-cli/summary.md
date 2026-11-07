# Run final-claude-sonnet-5-5-cli (subscription, 3 trial(s))

## Source: official-cli

CLI `2.1.319 (Claude Code)`, effort `high`, command `claude.EXE -p --model claude-sonnet-5-5 --effort high --output-format json --tools '' --safe-mode --strict-mcp-config --disable-slash-commands --no-session-persistence`. Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is included before the task prompt, so these cells are not directly comparable with API/OpenRouter cells.

| task | claude-sonnet-5-5 |
|---|---|
| t01_flash_sale | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t02_on_call | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t04_room_booking | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t05_wallet_transfer | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t06_idempotent_payment | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t07_node_drain | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t10_room_rules_scaled | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |

- claude-sonnet-5-5: 30/30 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | t01_flash_sale | trial_1 | 807 | 8.02 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:48:28+00:00) |
| claude-sonnet-5-5 | t01_flash_sale | trial_2 | 598 | 6.33 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:48:37+00:00) |
| claude-sonnet-5-5 | t01_flash_sale | trial_3 | 644 | 7.17 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:48:43+00:00) |
| claude-sonnet-5-5 | t02_on_call | trial_1 | 1079 | 9.98 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:48:51+00:00) |
| claude-sonnet-5-5 | t02_on_call | trial_2 | 1094 | 10.09 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:01+00:00) |
| claude-sonnet-5-5 | t02_on_call | trial_3 | 1168 | 11.66 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:11+00:00) |
| claude-sonnet-5-5 | t03_expense_budget | trial_1 | 1328 | 11.0 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:23+00:00) |
| claude-sonnet-5-5 | t03_expense_budget | trial_2 | 1052 | 9.43 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:34+00:00) |
| claude-sonnet-5-5 | t03_expense_budget | trial_3 | 1178 | 10.21 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:44+00:00) |
| claude-sonnet-5-5 | t04_room_booking | trial_1 | 1224 | 10.71 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:49:54+00:00) |
| claude-sonnet-5-5 | t04_room_booking | trial_2 | 1236 | 11.39 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:50:05+00:00) |
| claude-sonnet-5-5 | t04_room_booking | trial_3 | 1364 | 12.21 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:50:17+00:00) |
| claude-sonnet-5-5 | t05_wallet_transfer | trial_1 | 1158 | 10.22 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:50:29+00:00) |
| claude-sonnet-5-5 | t05_wallet_transfer | trial_2 | 1139 | 11.11 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:50:40+00:00) |
| claude-sonnet-5-5 | t05_wallet_transfer | trial_3 | 1292 | 11.16 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:50:51+00:00) |
| claude-sonnet-5-5 | t06_idempotent_payment | trial_1 | 1590 | 13.2 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:51:03+00:00) |
| claude-sonnet-5-5 | t06_idempotent_payment | trial_2 | 1519 | 12.43 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:51:16+00:00) |
| claude-sonnet-5-5 | t06_idempotent_payment | trial_3 | 1576 | 12.73 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:51:29+00:00) |
| claude-sonnet-5-5 | t07_node_drain | trial_1 | 1868 | 16.88 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:51:42+00:00) |
| claude-sonnet-5-5 | t07_node_drain | trial_2 | 1945 | 17.5 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:51:59+00:00) |
| claude-sonnet-5-5 | t07_node_drain | trial_3 | 2133 | 18.57 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:52:16+00:00) |
| claude-sonnet-5-5 | t08_expense_endpoints | trial_1 | 1877 | 13.88 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:52:35+00:00) |
| claude-sonnet-5-5 | t08_expense_endpoints | trial_2 | 2201 | 15.46 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:52:49+00:00) |
| claude-sonnet-5-5 | t08_expense_endpoints | trial_3 | 1931 | 14.58 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:53:05+00:00) |
| claude-sonnet-5-5 | t09_room_rules | trial_1 | 3042 | 22.1 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:53:20+00:00) |
| claude-sonnet-5-5 | t09_room_rules | trial_2 | 2615 | 18.79 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:53:42+00:00) |
| claude-sonnet-5-5 | t09_room_rules | trial_3 | 2814 | 21.16 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:54:01+00:00) |
| claude-sonnet-5-5 | t10_room_rules_scaled | trial_1 | 5781 | 45.19 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:54:23+00:00) |
| claude-sonnet-5-5 | t10_room_rules_scaled | trial_2 | 5980 | 50.1 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:55:08+00:00) |
| claude-sonnet-5-5 | t10_room_rules_scaled | trial_3 | 5464 | 40.81 | 1 | end_turn | claude.ai (claude -p) (model shown claude-sonnet-5-5, 2026-11-07T11:55:58+00:00) |

spent_usd: 0.0, api_calls: 30, sessions: 1, complete: True
