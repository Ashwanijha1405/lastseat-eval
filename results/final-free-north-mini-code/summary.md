# Run final-free-north-mini-code (free, 3 trial(s))

## Source: openrouter

| task | north-mini-code |
|---|---|
| t01_flash_sale | trial_1: FAIL [concurrency] 0.75 (sa 0.50 / so 0.25 / li 0.00)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t02_on_call | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: FAIL [concurrency] 0.75 (sa 0.50 / so 0.25 / li 0.00)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t03_expense_budget | trial_1: FAIL [load] (syntax_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: FAIL [concurrency] 0.50 (sa 0.00 / so 0.25 / li 0.25)<br>trial_3: FAIL [concurrency] 0.50 (sa 0.00 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t04_room_booking | trial_1: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t05_wallet_transfer | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t06_idempotent_payment | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: FAIL [load] (syntax_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>**pass^3: no** |
| t07_node_drain | trial_1: FAIL [load] (exec_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: FAIL [load] (no_code) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: FAIL [load] (no_code) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: FAIL [load] (no_code) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: FAIL [spec] 0.75 (sa 0.50 / so 0.00 / li 0.25)<br>**pass^3: no** |
| t10_room_rules_scaled | trial_1: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: FAIL [load] (no_code) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>**pass^3: no** |

- north-mini-code: 14/30 passed, mean score 0.575; failures: concurrency 4, load 11, spec 1

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **spec** = a logic bug that shows without concurrency: a solo check failed, or a serial schedule (one request finished before the next started) broke an invariant or liveness; **concurrency** = correct alone and in every serial order, but an interleaved schedule broke an invariant or liveness; **harness** = the grader failed.

## Failures

### north-mini-code / t01_flash_sale / trial_1: concurrency
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 6322
- scenario `two buyers, both fit`: status ok, safe=True (0 unsafe), live=False (24 unlive) of 36 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- counterexample: `results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/counterexample_1.txt`
- counterexample: `results/final-free-north-mini-code/north-mini-code/t01_flash_sale/trial_1/counterexample_2.txt`

### north-mini-code / t02_on_call / trial_2: concurrency
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 8898
- scenario `three on call, two ask to leave`: status ok, safe=True (0 unsafe), live=False (80 unlive) of 92 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- scenario `one leaves from each of two shifts`: status ok, safe=True (0 unsafe), live=False (240 unlive) of 252 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- counterexample: `results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_1.txt`
- counterexample: `results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_2.txt`
- counterexample: `results/final-free-north-mini-code/north-mini-code/t02_on_call/trial_2/counterexample_3.txt`

### north-mini-code / t03_expense_budget / trial_1: load
- status `load_error`, load_error `syntax_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 14998
- load_detail: `line 65: '[' was never closed`

### north-mini-code / t03_expense_budget / trial_2: concurrency
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 11854
- scenario `nothing approved yet, two approvals that do not both fit`: status ok, safe=False (134 unsafe), live=True (0 unlive) of 148 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- scenario `one already approved, two approvals that do not both fit`: status ok, safe=False (134 unsafe), live=True (0 unlive) of 148 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- counterexample: `results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/counterexample_1.txt`
- counterexample: `results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_2/counterexample_2.txt`

### north-mini-code / t03_expense_budget / trial_3: concurrency
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 13326
- scenario `nothing approved yet, two approvals that do not both fit`: status ok, safe=False (24 unsafe), live=True (0 unlive) of 36 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- scenario `one already approved, two approvals that do not both fit`: status ok, safe=False (24 unsafe), live=True (0 unlive) of 36 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 0 unlive of 2
- counterexample: `results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/counterexample_1.txt`
- counterexample: `results/final-free-north-mini-code/north-mini-code/t03_expense_budget/trial_3/counterexample_2.txt`

### north-mini-code / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 10054
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 4:     EXCLUDE USING GIST (room_id WITH =, tsrange(starts_at, e...
                                                ^
HINT:  No function matches the given name and argument types. You might nee`

### north-mini-code / t06_idempotent_payment / trial_2: load
- status `load_error`, load_error `syntax_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 13955
- load_detail: `line 9: expected ':'`

### north-mini-code / t06_idempotent_payment / trial_3: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 25883
- load_detail: `ActiveSqlTransaction: CREATE INDEX CONCURRENTLY cannot run inside a transaction block`

### north-mini-code / t07_node_drain / trial_1: load
- status `load_error`, load_error `exec_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 20085
- load_detail: `SyntaxError: from __future__ imports must occur at the beginning of the file (solution.py, line 3)`

### north-mini-code / t07_node_drain / trial_2: load
- status `load_error`, load_error `no_code`, safety_reason `None`, liveness_reason `None`, finish_reason `length`, completion_tokens 31999

### north-mini-code / t09_room_rules / trial_1: load
- status `load_error`, load_error `no_code`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 22522

### north-mini-code / t09_room_rules / trial_2: load
- status `load_error`, load_error `no_code`, safety_reason `None`, liveness_reason `None`, finish_reason `length`, completion_tokens 32001

### north-mini-code / t09_room_rules / trial_3: spec
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 17834
- solo FAIL: the day is the UTC day, whatever offset the time is given in: returned True, expected False; violated: no room has more than 3 bookings on a UTC day (got [(False,)]); violated: expected state: SELECT count(*) = 3 FROM bookings (got [(False,)])
- counterexample: `results/final-free-north-mini-code/north-mini-code/t09_room_rules/trial_3/counterexample_1.txt`

### north-mini-code / t10_room_rules_scaled / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 29556
- load_detail: `SyntaxError: syntax error at or near "EXCLUSION"
LINE 4:         EXCLUSION USING GIST (
                ^`

### north-mini-code / t10_room_rules_scaled / trial_2: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 21456
- load_detail: `SyntaxError: syntax error at or near ")"
LINE 4: ...NG GIST (room_id WITH =, tsrange(starts_at, ends_at, '[)'));
                                                                     ^`

### north-mini-code / t10_room_rules_scaled / trial_3: load
- status `load_error`, load_error `no_code`, safety_reason `None`, liveness_reason `None`, finish_reason `length`, completion_tokens 32000

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| north-mini-code | t01_flash_sale | trial_1 | 6322 | 52.19 | 1 | stop | Cohere |
| north-mini-code | t01_flash_sale | trial_2 | 10375 | 64.36 | 1 | stop | Cohere |
| north-mini-code | t01_flash_sale | trial_3 | 13187 | 73.71 | 1 | stop | Cohere |
| north-mini-code | t02_on_call | trial_1 | 23013 | 144.09 | 1 | stop | Cohere |
| north-mini-code | t02_on_call | trial_2 | 8898 | 47.94 | 1 | stop | Cohere |
| north-mini-code | t02_on_call | trial_3 | 13585 | 79.44 | 1 | stop | Cohere |
| north-mini-code | t03_expense_budget | trial_1 | 14998 | 109.08 | 1 | stop | Cohere |
| north-mini-code | t03_expense_budget | trial_2 | 11854 | 93.33 | 1 | stop | Cohere |
| north-mini-code | t03_expense_budget | trial_3 | 13326 | 69.62 | 1 | stop | Cohere |
| north-mini-code | t04_room_booking | trial_1 | 10054 | 81.98 | 1 | stop | Cohere |
| north-mini-code | t04_room_booking | trial_2 | 15322 | 127.61 | 1 | stop | Cohere |
| north-mini-code | t04_room_booking | trial_3 | 23238 | 123.61 | 1 | stop | Cohere |
| north-mini-code | t05_wallet_transfer | trial_1 | 18732 | 100.63 | 1 | stop | Cohere |
| north-mini-code | t05_wallet_transfer | trial_2 | 15211 | 150.99 | 1 | stop | Cohere |
| north-mini-code | t05_wallet_transfer | trial_3 | 13977 | 89.31 | 1 | stop | Cohere |
| north-mini-code | t06_idempotent_payment | trial_1 | 14468 | 85.72 | 1 | stop | Cohere |
| north-mini-code | t06_idempotent_payment | trial_2 | 13955 | 91.52 | 1 | stop | Cohere |
| north-mini-code | t06_idempotent_payment | trial_3 | 25883 | 161.34 | 1 | stop | Cohere |
| north-mini-code | t07_node_drain | trial_1 | 20085 | 131.83 | 1 | stop | Cohere |
| north-mini-code | t07_node_drain | trial_2 | 31999 | 176.57 | 1 | length | Cohere |
| north-mini-code | t07_node_drain | trial_3 | 12739 | 56.74 | 1 | stop | Cohere |
| north-mini-code | t08_expense_endpoints | trial_1 | 16181 | 76.27 | 1 | stop | Cohere |
| north-mini-code | t08_expense_endpoints | trial_2 | 23875 | 118.71 | 1 | stop | Cohere |
| north-mini-code | t08_expense_endpoints | trial_3 | 23761 | 87.87 | 1 | stop | Cohere |
| north-mini-code | t09_room_rules | trial_1 | 22522 | 143.62 | 1 | stop | Cohere |
| north-mini-code | t09_room_rules | trial_2 | 32001 | 173.41 | 1 | length | Cohere |
| north-mini-code | t09_room_rules | trial_3 | 17834 | 103.93 | 1 | stop | Cohere |
| north-mini-code | t10_room_rules_scaled | trial_1 | 29556 | 201.07 | 1 | stop | Cohere |
| north-mini-code | t10_room_rules_scaled | trial_2 | 21456 | 121.2 | 1 | stop | Cohere |
| north-mini-code | t10_room_rules_scaled | trial_3 | 32000 | 107.87 | 1 | length | Cohere |

spent_usd: 0.0, api_calls: 30, sessions: 2, complete: True
