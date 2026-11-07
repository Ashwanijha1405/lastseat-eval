# Run 20261107T050645Z-cli (subscription, 3 trial(s))

## Source: official-cli

CLI `2.1.319 (Claude Code)`, effort `high`, command `claude.EXE -p --model claude-opus-5-5 --effort high --output-format json --tools '' --safe-mode --strict-mcp-config --disable-slash-commands --no-session-persistence`. Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is included before the task prompt, so these cells are not directly comparable with API/OpenRouter cells.

| task | claude-opus-5-5 |
|---|---|
| t01_flash_sale | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |

- claude-opus-5-5: 12/12 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | t01_flash_sale | trial_1 | 906 | 10.04 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:06:49+00:00) |
| claude-opus-5-5 | t01_flash_sale | trial_2 | 982 | 10.65 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:06:59+00:00) |
| claude-opus-5-5 | t01_flash_sale | trial_3 | 708 | 7.83 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:10+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_1 | 1516 | 14.33 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:18+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_2 | 913 | 9.43 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:33+00:00) |
| claude-opus-5-5 | t03_expense_budget | trial_3 | 1743 | 17.32 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:07:42+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_1 | 2210 | 21.57 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:00+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_2 | 2100 | 19.35 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:22+00:00) |
| claude-opus-5-5 | t08_expense_endpoints | trial_3 | 2416 | 22.86 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:08:41+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_1 | 3490 | 32.7 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:09:04+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_2 | 3387 | 31.76 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:09:37+00:00) |
| claude-opus-5-5 | t09_room_rules | trial_3 | 3730 | 33.31 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T05:10:09+00:00) |

spent_usd: 0.0, api_calls: 12, sessions: 1, complete: True
