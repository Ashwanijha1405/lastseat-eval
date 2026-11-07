# Run final-claude-opus-5-5-cli (subscription, 3 trial(s))

> 15 trial(s) reused from earlier runs with the same model, CLI, effort and prompt (graded again by the current grader): t01_flash_sale/trial_1 ← 20261107T050645Z-cli, t01_flash_sale/trial_2 ← 20261107T050645Z-cli, t01_flash_sale/trial_3 ← 20261107T050645Z-cli, t03_expense_budget/trial_1 ← 20261107T050645Z-cli, t03_expense_budget/trial_2 ← 20261107T050645Z-cli, t03_expense_budget/trial_3 ← 20261107T050645Z-cli, t08_expense_endpoints/trial_1 ← 20261107T050645Z-cli, t08_expense_endpoints/trial_2 ← 20261107T050645Z-cli, t08_expense_endpoints/trial_3 ← 20261107T050645Z-cli, t09_room_rules/trial_1 ← 20261107T050645Z-cli, t09_room_rules/trial_2 ← 20261107T050645Z-cli, t09_room_rules/trial_3 ← 20261107T050645Z-cli, t10_room_rules_scaled/trial_1 ← 20261107T060621Z-cli, t10_room_rules_scaled/trial_2 ← 20261107T060621Z-cli, t10_room_rules_scaled/trial_3 ← 20261107T060621Z-cli

## Source: official-cli

CLI `2.1.319 (Claude Code)`, effort `high`, command `claude.EXE -p --model claude-opus-5-5 --effort high --output-format json --tools '' --safe-mode --strict-mcp-config --disable-slash-commands --no-session-persistence`. Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is included before the task prompt, so these cells are not directly comparable with API/OpenRouter cells.

| task | claude-opus-5-5 |
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

- claude-opus-5-5: 30/30 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | t01_flash_sale | trial_1 | 906 | 10.04 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:06:49+00:00) |
| claude-opus-5-5 | t01_flash_sale | trial_2 | 982 | 10.65 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:06:59+00:00) |
| claude-opus-5-5 | t01_flash_sale | trial_3 | 708 | 7.83 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:10+00:00) |
| claude-opus-5-5 | t02_on_call | trial_1 | 1372 | 14.12 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:22:10+00:00) |
| claude-opus-5-5 | t02_on_call | trial_2 | 1653 | 17.59 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:22:24+00:00) |
| claude-opus-5-5 | t02_on_call | trial_3 | 1492 | 14.74 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:22:42+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_1 | 1516 | 14.33 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:18+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_2 | 913 | 9.43 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:33+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_3 | 1743 | 17.32 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:42+00:00) |
| claude-opus-5-5 | t04_room_booking | trial_1 | 1574 | 15.71 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:22:57+00:00) |
| claude-opus-5-5 | t04_room_booking | trial_2 | 1686 | 16.75 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:23:13+00:00) |
| claude-opus-5-5 | t04_room_booking | trial_3 | 1414 | 14.25 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:23:30+00:00) |
| claude-opus-5-5 | t05_wallet_transfer | trial_1 | 2261 | 22.81 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:23:45+00:00) |
| claude-opus-5-5 | t05_wallet_transfer | trial_2 | 1537 | 14.67 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:24:08+00:00) |
| claude-opus-5-5 | t05_wallet_transfer | trial_3 | 1563 | 15.84 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:24:23+00:00) |
| claude-opus-5-5 | t06_idempotent_payment | trial_1 | 1722 | 17.1 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:24:39+00:00) |
| claude-opus-5-5 | t06_idempotent_payment | trial_2 | 1827 | 17.33 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:24:56+00:00) |
| claude-opus-5-5 | t06_idempotent_payment | trial_3 | 1904 | 18.21 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:25:14+00:00) |
| claude-opus-5-5 | t07_node_drain | trial_1 | 2420 | 25.1 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:25:32+00:00) |
| claude-opus-5-5 | t07_node_drain | trial_2 | 2511 | 25.22 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:25:57+00:00) |
| claude-opus-5-5 | t07_node_drain | trial_3 | 2379 | 24.43 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T11:26:23+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_1 | 2210 | 21.57 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:00+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_2 | 2100 | 19.35 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:22+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_3 | 2416 | 22.86 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:41+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_1 | 3490 | 32.7 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:09:04+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_2 | 3387 | 31.76 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:09:37+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_3 | 3730 | 33.31 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:10:09+00:00) |
| claude-opus-5-5 | t10_room_rules_scaled | trial_1 | 4213 | 40.44 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:06:24+00:00) |
| claude-opus-5-5 | t10_room_rules_scaled | trial_2 | 4289 | 40.49 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:07:05+00:00) |
| claude-opus-5-5 | t10_room_rules_scaled | trial_3 | 5974 | 58.41 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:07:45+00:00) |

spent_usd: 0.0, api_calls: 15, sessions: 1, complete: True
