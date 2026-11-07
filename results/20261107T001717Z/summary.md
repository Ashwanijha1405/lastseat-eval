# Run 20261107T001717Z (free, 1 trial(s))

| task | nemotron-3-ultra | gemma-4-31b |
|---|---|---|
| t01_flash_sale | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing (api error) |
| t02_on_call | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t03_expense_budget | FAIL [concurrency] 0.50 (sa 0.00 / so 0.25 / li 0.25) | missing |
| t04_room_booking | FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) | missing |
| t05_wallet_transfer | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t06_idempotent_payment | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t07_node_drain | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t08_expense_endpoints | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t09_room_rules | FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) | missing |

- nemotron-3-ultra: 6/9 passed, mean score 0.722; failures: concurrency 1, load 2
- gemma-4-31b: 0/9 passed, mean score 0.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### nemotron-3-ultra / t03_expense_budget / trial_1: concurrency
- status `graded`, load_error `None`, safety_reason `None`, finish_reason `stop`, completion_tokens 15913
- scenario `nothing approved yet, two approvals that do not both fit`: status ok, safe=False (14 unsafe), live=True (0 unlive) of 24 schedules, exhaustive=True, reproduced=True
- scenario `one already approved, two approvals that do not both fit`: status ok, safe=False (14 unsafe), live=True (0 unlive) of 24 schedules, exhaustive=True, reproduced=True
- counterexample: `results/20261107T001717Z/nemotron-3-ultra/t03_expense_budget/trial_1/counterexample_1.txt`
- counterexample: `results/20261107T001717Z/nemotron-3-ultra/t03_expense_budget/trial_1/counterexample_2.txt`

### nemotron-3-ultra / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, finish_reason `stop`, completion_tokens 3005
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 5:                     tsrange(starts_at, ends_at) WITH &&
                            ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts`

### nemotron-3-ultra / t09_room_rules / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, finish_reason `stop`, completion_tokens 13435
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 3:         EXCLUDE USING gist (room_id WITH =, tsrange(starts_a...
                                                    ^
HINT:  No function matches the given name and argument types. You might`

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| nemotron-3-ultra | t01_flash_sale | trial_1 | 2827 | 35.23 | 1 | stop | Nvidia |
| nemotron-3-ultra | t02_on_call | trial_1 | 7708 | 124.45 | 1 | stop | Nvidia |
| nemotron-3-ultra | t03_expense_budget | trial_1 | 15913 | 191.81 | 1 | stop | Nvidia |
| nemotron-3-ultra | t04_room_booking | trial_1 | 3005 | 44.1 | 1 | stop | Nvidia |
| nemotron-3-ultra | t05_wallet_transfer | trial_1 | 3928 | 54.26 | 1 | stop | Nvidia |
| nemotron-3-ultra | t06_idempotent_payment | trial_1 | 3405 | 48.17 | 1 | stop | Nvidia |
| nemotron-3-ultra | t07_node_drain | trial_1 | 15936 | 293.25 | 1 | stop | Nvidia |
| nemotron-3-ultra | t08_expense_endpoints | trial_1 | 9977 | 228.75 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_1 | 13435 | 362.9 | 1 | stop | Nvidia |
| gemma-4-31b | t01_flash_sale | trial_1 | None | None | None | None | None |
| gemma-4-31b | t02_on_call | trial_1 | None | None | None | None | None |
| gemma-4-31b | t03_expense_budget | trial_1 | None | None | None | None | None |
| gemma-4-31b | t04_room_booking | trial_1 | None | None | None | None | None |
| gemma-4-31b | t05_wallet_transfer | trial_1 | None | None | None | None | None |
| gemma-4-31b | t06_idempotent_payment | trial_1 | None | None | None | None | None |
| gemma-4-31b | t07_node_drain | trial_1 | None | None | None | None | None |
| gemma-4-31b | t08_expense_endpoints | trial_1 | None | None | None | None | None |
| gemma-4-31b | t09_room_rules | trial_1 | None | None | None | None | None |

spent_usd: 0.0, api_calls: 9, sessions: 1, complete: False
