# Run 20261106T203525Z (free, 1 trial(s))

## Source: openrouter

| task | nemotron-3-ultra |
|---|---|
| t08_expense_endpoints | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |
| t09_room_rules | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |

- nemotron-3-ultra: 2/2 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **spec** = a logic bug that shows without concurrency: a solo check failed, or a serial schedule (one request finished before the next started) broke an invariant or liveness; **concurrency** = correct alone and in every serial order, but an interleaved schedule broke an invariant or liveness; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| nemotron-3-ultra | t08_expense_endpoints | trial_1 | 10356 | 289.93 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_1 | 9110 | 236.02 | 1 | stop | Nvidia |

spent_usd: 0.0, api_calls: 2, sessions: 1, complete: True
