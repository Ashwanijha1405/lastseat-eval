# Run 20261106T123821Z (free, 1 trial(s))

| task | nemotron-3-ultra | gemma-4-31b |
|---|---|---|
| t01_flash_sale | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing (api error) |
| t02_on_call | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t03_expense_budget | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t04_room_booking | FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) | missing |
| t05_wallet_transfer | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t06_idempotent_payment | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | missing |
| t07_node_drain | FAIL [spec] (vacuous_safety) 0.00 (sa 0.00 / so 0.00 / li 0.00) | missing |

- nemotron-3-ultra: 5/7 passed, mean score 0.714; failures: load 1, spec 1
- gemma-4-31b: 0/7 passed, mean score 0.000; failures: none

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **concurrency** = an invariant broke in some schedule, or a request that fits failed (liveness); **spec** = wrong when run alone (a solo check failed), with no unsafe schedule; **harness** = the grader failed.

## Failures

### nemotron-3-ultra / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, finish_reason `stop`, completion_tokens 5142
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 1: ...ping_bookings EXCLUDE USING GIST (room_id WITH =, tsrange(st...
                                                             ^
HINT:  No function matches the given name and argument type`

### nemotron-3-ultra / t07_node_drain / trial_1: spec
- status `graded`, load_error `None`, safety_reason `vacuous_safety`, finish_reason `stop`, completion_tokens 9467
- solo FAIL: drain succeeds when every shard keeps a replica: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- solo FAIL: drain is refused if any shard would lose its last replica, and nothing changes: raised SyntaxError (42601): syntax error at or near "ORDER"
- solo FAIL: shards without an active replica on the node do not block it: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- scenario `two drains of nodes sharing several shards, both fit`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True
- scenario `two drains of nodes with no shared shard`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_1.txt`
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_2.txt`
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_3.txt`

## API

| model | task | trial | tokens out | seconds | attempts | finish | provider |
|---|---|---|---|---|---|---|---|
| nemotron-3-ultra | t01_flash_sale | trial_1 | 5700 | 184.32 | 1 | stop | Nvidia |
| nemotron-3-ultra | t02_on_call | trial_1 | 10321 | 289.64 | 1 | stop | Nvidia |
| nemotron-3-ultra | t03_expense_budget | trial_1 | 7934 | 357.64 | 1 | stop | Nvidia |
| nemotron-3-ultra | t04_room_booking | trial_1 | 5142 | 179.68 | 1 | stop | Nvidia |
| nemotron-3-ultra | t05_wallet_transfer | trial_1 | 25360 | 926.71 | 1 | stop | Nvidia |
| nemotron-3-ultra | t06_idempotent_payment | trial_1 | 4338 | 231.46 | 1 | stop | Nvidia |
| nemotron-3-ultra | t07_node_drain | trial_1 | 9467 | 400.48 | 1 | stop | Nvidia |
| gemma-4-31b | t01_flash_sale | trial_1 | None | None | None | None | None |
| gemma-4-31b | t02_on_call | trial_1 | None | None | None | None | None |
| gemma-4-31b | t03_expense_budget | trial_1 | None | None | None | None | None |
| gemma-4-31b | t04_room_booking | trial_1 | None | None | None | None | None |
| gemma-4-31b | t05_wallet_transfer | trial_1 | None | None | None | None | None |
| gemma-4-31b | t06_idempotent_payment | trial_1 | None | None | None | None | None |
| gemma-4-31b | t07_node_drain | trial_1 | None | None | None | None | None |

spent_usd: 0.0, api_calls: 7, sessions: 3, complete: False
