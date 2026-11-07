# Run 20261106T203525Z (free, 1 trial(s))

| task | nemotron-3-ultra |
|---|---|
| t08_expense_endpoints | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |
| t09_room_rules | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |

- nemotron-3-ultra: 2/2 passed, mean score 1.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| nemotron-3-ultra | t08_expense_endpoints | trial_1 | 10356 | 289.93 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_1 | 9110 | 236.02 | 1 | stop | Nvidia |

spent_usd: 0.0, api_calls: 2, sessions: 1, complete: True
