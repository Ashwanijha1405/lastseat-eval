# Run 20261107T060621Z-cli (subscription, 3 trial(s))

## Source: official-cli

CLI `2.1.319 (Claude Code)`, effort `high`, command `claude.EXE -p --model claude-opus-5-5 --effort high --output-format json --tools '' --safe-mode --strict-mcp-config --disable-slash-commands --no-session-persistence`. Answers come from Claude Code headless mode (claude -p). The CLI's own system prompt is included before the task prompt, so these cells are not directly comparable with API/OpenRouter cells.

| task | claude-opus-5-5 |
|---|---|
| t10_room_rules_scaled | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |

- claude-opus-5-5: 3/3 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **spec** = a logic bug that shows without concurrency: a solo check failed, or a serial schedule (one request finished before the next started) broke an invariant or liveness; **concurrency** = correct alone and in every serial order, but an interleaved schedule broke an invariant or liveness; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| claude-opus-5-5 | t10_room_rules_scaled | trial_1 | 4213 | 40.44 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:06:24+00:00) |
| claude-opus-5-5 | t10_room_rules_scaled | trial_2 | 4289 | 40.49 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:07:05+00:00) |
| claude-opus-5-5 | t10_room_rules_scaled | trial_3 | 5974 | 58.41 | 1 | end_turn | claude.ai (claude -p) (model shown claude-opus-5-5, 2026-11-07T06:07:45+00:00) |

spent_usd: 0.0, api_calls: 3, sessions: 1, complete: True
