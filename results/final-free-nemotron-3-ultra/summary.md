# Run final-free-nemotron-3-ultra (free, 3 trial(s))

## Source: openrouter

| task | nemotron-3-ultra |
|---|---|
| t01_flash_sale | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t02_on_call | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t03_expense_budget | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t04_room_booking | trial_1: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>**pass^3: no** |
| t05_wallet_transfer | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t06_idempotent_payment | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t07_node_drain | trial_1: FAIL [load] (forbidden_import) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: FAIL [spec] (vacuous_safety) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>**pass^3: no** |
| t08_expense_endpoints | trial_1: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: yes** |
| t09_room_rules | trial_1: FAIL [spec] 0.75 (sa 0.50 / so 0.00 / li 0.25)<br>trial_2: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_3: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>**pass^3: no** |
| t10_room_rules_scaled | trial_1: FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00)<br>trial_2: PASS 1.00 (sa 0.50 / so 0.25 / li 0.25)<br>trial_3: FAIL [concurrency] 0.25 (sa 0.00 / so 0.00 / li 0.25)<br>**pass^3: no** |

- nemotron-3-ultra: 20/30 passed, mean score 0.700; failures: load 7, spec 2, concurrency 1

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### nemotron-3-ultra / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 4258
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 6:             tsrange(starts_at, ends_at) WITH &&
                    ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts.`

### nemotron-3-ultra / t04_room_booking / trial_2: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 3254
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 6:             tsrange(starts_at, ends_at) WITH &&
                    ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts.`

### nemotron-3-ultra / t04_room_booking / trial_3: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 6639
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 4:             EXCLUDE USING gist (room_id WITH =, tsrange(star...
                                                        ^
HINT:  No function matches the given name and argument types. You m`

### nemotron-3-ultra / t06_idempotent_payment / trial_2: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 3088
- load_detail: `SyntaxError: syntax error at or near "NOT"
LINE 1: ALTER TABLE payments ADD CONSTRAINT IF NOT EXISTS payments_i...
                                               ^`

### nemotron-3-ultra / t07_node_drain / trial_1: load
- status `load_error`, load_error `forbidden_import`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 10339
- load_detail: `collections`

### nemotron-3-ultra / t07_node_drain / trial_3: spec
- status `graded`, load_error `None`, safety_reason `vacuous_safety`, liveness_reason `None`, finish_reason `stop`, completion_tokens 11491
- solo FAIL: drain succeeds when every shard keeps a replica: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- solo FAIL: drain is refused if any shard would lose its last replica, and nothing changes: raised SyntaxError (42601): syntax error at or near "ORDER"
- solo FAIL: shards without an active replica on the node do not block it: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- scenario `two drains of nodes sharing several shards, both fit`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True
- scenario `two drains of nodes with no shared shard`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_1.txt`
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_2.txt`
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t07_node_drain/trial_3/counterexample_3.txt`

### nemotron-3-ultra / t09_room_rules / trial_1: spec
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 13313
- solo FAIL: the day is the UTC day, whatever offset the time is given in: returned True, expected False; violated: no room has more than 3 bookings on a UTC day (got [(False,)]); violated: expected state: SELECT count(*) = 3 FROM bookings (got [(False,)])
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t09_room_rules/trial_1/counterexample_1.txt`

### nemotron-3-ultra / t09_room_rules / trial_2: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 10470
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone, unknown) does not exist
LINE 6:             tsrange(starts_at, ends_at, '[)') WITH &&
                    ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts.`

### nemotron-3-ultra / t10_room_rules_scaled / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 12097
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 6:             tsrange(starts_at, ends_at) WITH &&
                    ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts.`

### nemotron-3-ultra / t10_room_rules_scaled / trial_3: concurrency
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 8006
- solo FAIL: a fourth booking on the same day is refused cleanly: returned True, expected False; violated: no room has more than 3 bookings on a UTC day (got [(False,)]); violated: expected state: SELECT count(*) = 3 FROM bookings (got [(False,)])
- solo FAIL: the day is the UTC day, whatever offset the time is given in: returned True, expected False; violated: no room has more than 3 bookings on a UTC day (got [(False,)]); violated: expected state: SELECT count(*) = 3 FROM bookings (got [(False,)])
- solo FAIL: a move into a full day is refused cleanly: returned True, expected False; violated: no room has more than 3 bookings on a UTC day (got [(False,)]); violated: expected state: SELECT starts_at = '2026-11-09T09:00:00Z' FROM bookings WHERE id = 1 (got [(False,)])
- scenario `two bookings for the last place of a day`: status ok, safe=False (84 unsafe), live=True (0 unlive) of 84 schedules, exhaustive=True, reproduced=True
- scenario `a move from another day and a booking, for the last place of a day`: status ok, safe=False (571 unsafe), live=True (0 unlive) of 571 schedules, exhaustive=True, reproduced=True
- scenario `two moves from different days, for the last place of a day`: status ok, safe=False (2200 unsafe), live=True (0 unlive) of 2200 schedules, exhaustive=False, reproduced=True
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_1.txt`
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_2.txt`
- counterexample: `results/final-free-nemotron-3-ultra/nemotron-3-ultra/t10_room_rules_scaled/trial_3/counterexample_3.txt`

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| nemotron-3-ultra | t01_flash_sale | trial_1 | 7427 | 87.26 | 1 | stop | Nvidia |
| nemotron-3-ultra | t01_flash_sale | trial_2 | 3323 | 46.99 | 1 | stop | Nvidia |
| nemotron-3-ultra | t01_flash_sale | trial_3 | 3036 | 109.23 | 1 | stop | Nvidia |
| nemotron-3-ultra | t02_on_call | trial_1 | 10786 | 156.54 | 1 | stop | Nvidia |
| nemotron-3-ultra | t02_on_call | trial_2 | 5309 | 97.15 | 1 | stop | Nvidia |
| nemotron-3-ultra | t02_on_call | trial_3 | 8580 | 209.84 | 1 | stop | Nvidia |
| nemotron-3-ultra | t03_expense_budget | trial_1 | 8934 | 118.62 | 1 | stop | Nvidia |
| nemotron-3-ultra | t03_expense_budget | trial_2 | 5690 | 79.24 | 1 | stop | Nvidia |
| nemotron-3-ultra | t03_expense_budget | trial_3 | 5412 | 89.81 | 1 | stop | Nvidia |
| nemotron-3-ultra | t04_room_booking | trial_1 | 4258 | 54.5 | 1 | stop | Nvidia |
| nemotron-3-ultra | t04_room_booking | trial_2 | 3254 | 50.21 | 1 | stop | Nvidia |
| nemotron-3-ultra | t04_room_booking | trial_3 | 6639 | 157.13 | 1 | stop | Nvidia |
| nemotron-3-ultra | t05_wallet_transfer | trial_1 | 26189 | 363.53 | 1 | stop | Nvidia |
| nemotron-3-ultra | t05_wallet_transfer | trial_2 | 29833 | 505.65 | 1 | stop | Nvidia |
| nemotron-3-ultra | t05_wallet_transfer | trial_3 | 30003 | 521.99 | 1 | stop | Nvidia |
| nemotron-3-ultra | t06_idempotent_payment | trial_1 | 5154 | 76.87 | 1 | stop | Nvidia |
| nemotron-3-ultra | t06_idempotent_payment | trial_2 | 3088 | 84.67 | 1 | stop | Nvidia |
| nemotron-3-ultra | t06_idempotent_payment | trial_3 | 2881 | 46.78 | 1 | stop | Nvidia |
| nemotron-3-ultra | t07_node_drain | trial_1 | 10339 | 119.02 | 1 | stop | Nvidia |
| nemotron-3-ultra | t07_node_drain | trial_2 | 12105 | 172.98 | 1 | stop | Nvidia |
| nemotron-3-ultra | t07_node_drain | trial_3 | 11491 | 182.17 | 1 | stop | Nvidia |
| nemotron-3-ultra | t08_expense_endpoints | trial_1 | 6955 | 114.81 | 1 | stop | Nvidia |
| nemotron-3-ultra | t08_expense_endpoints | trial_2 | 9658 | 117.42 | 1 | stop | Nvidia |
| nemotron-3-ultra | t08_expense_endpoints | trial_3 | 10271 | 137.63 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_1 | 13313 | 166.09 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_2 | 10470 | 155.77 | 1 | stop | Nvidia |
| nemotron-3-ultra | t09_room_rules | trial_3 | 17086 | 287.79 | 1 | stop | Nvidia |
| nemotron-3-ultra | t10_room_rules_scaled | trial_1 | 12097 | 192.12 | 1 | stop | Nvidia |
| nemotron-3-ultra | t10_room_rules_scaled | trial_2 | 14528 | 291.76 | 1 | stop | Nvidia |
| nemotron-3-ultra | t10_room_rules_scaled | trial_3 | 8006 | 102.51 | 1 | stop | Nvidia |

spent_usd: 0.0, api_calls: 30, sessions: 1, complete: True
