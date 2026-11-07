# Run 20261106T123821Z (free, 1 trial(s))

## Source: openrouter

| task | nemotron-3-ultra | north-mini-code |
|---|---|---|
| t01_flash_sale | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |
| t02_on_call | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | FAIL [load] (syntax_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) |
| t03_expense_budget | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | FAIL [spec] 0.50 (sa 0.50 / so 0.00 / li 0.00) |
| t04_room_booking | FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) | FAIL [load] (migrate_error) 0.00 (sa 0.00 / so 0.00 / li 0.00) |
| t05_wallet_transfer | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |
| t06_idempotent_payment | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) | PASS 1.00 (sa 0.50 / so 0.25 / li 0.25) |
| t07_node_drain | FAIL [spec] (vacuous_safety) 0.00 (sa 0.00 / so 0.00 / li 0.00) | FAIL [spec] (vacuous_safety) 0.00 (sa 0.00 / so 0.00 / li 0.00) |

- nemotron-3-ultra: 5/7 passed, mean score 0.714; failures: load 1, spec 1
- north-mini-code: 3/7 passed, mean score 0.500; failures: load 2, spec 2

Failure categories: **load** = never graded (syntax, import, missing function, migrate_error, forbidden_migrate, no_code); **spec** = a logic bug that shows without concurrency: a solo check failed, or a serial schedule (one request finished before the next started) broke an invariant or liveness; **concurrency** = correct alone and in every serial order, but an interleaved schedule broke an invariant or liveness; **harness** = the grader failed.

## Failures

### nemotron-3-ultra / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 5142
- load_detail: `UndefinedFunction: function tsrange(timestamp with time zone, timestamp with time zone) does not exist
LINE 1: ...ping_bookings EXCLUDE USING GIST (room_id WITH =, tsrange(st...
                                                             ^
HINT:  No function matches the given name and argument type`

### nemotron-3-ultra / t07_node_drain / trial_1: spec
- status `graded`, load_error `None`, safety_reason `vacuous_safety`, liveness_reason `None`, finish_reason `stop`, completion_tokens 9467
- solo FAIL: drain succeeds when every shard keeps a replica: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- solo FAIL: drain is refused if any shard would lose its last replica, and nothing changes: raised SyntaxError (42601): syntax error at or near "ORDER"
- solo FAIL: shards without an active replica on the node do not block it: raised SyntaxError (42601): syntax error at or near "ORDER"; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- scenario `two drains of nodes sharing several shards, both fit`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 2 unlive of 2
- scenario `two drains of nodes with no shared shard`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 2 unlive of 2
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_1.txt`
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_2.txt`
- counterexample: `results/20261106T123821Z/nemotron-3-ultra/t07_node_drain/trial_1/counterexample_3.txt`

### north-mini-code / t02_on_call / trial_1: load
- status `load_error`, load_error `syntax_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 17303
- load_detail: `line 43: unterminated string literal (detected at line 43)`

### north-mini-code / t03_expense_budget / trial_1: spec
- status `graded`, load_error `None`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 20011
- solo FAIL: other departments' approvals do not count: returned False, expected True; violated: expected state: SELECT status = 'approved' FROM expenses WHERE id = 2 (got [(False,)])
- scenario `approvals in two different departments`: status ok, safe=True (0 unsafe), live=False (20 unlive) of 20 schedules, exhaustive=True, reproduced=True; serial: 0 unsafe, 2 unlive of 2
- counterexample: `results/20261106T123821Z/north-mini-code/t03_expense_budget/trial_1/counterexample_1.txt`
- counterexample: `results/20261106T123821Z/north-mini-code/t03_expense_budget/trial_1/counterexample_2.txt`
- counterexample: `results/20261106T123821Z/north-mini-code/t03_expense_budget/trial_1/counterexample_3.txt`

### north-mini-code / t04_room_booking / trial_1: load
- status `load_error`, load_error `migrate_error`, safety_reason `None`, liveness_reason `None`, finish_reason `stop`, completion_tokens 10722
- load_detail: `UndefinedObject: data type integer has no default operator class for access method "gist"
HINT:  You must specify an operator class for the index or define a default operator class for the data type.`

### north-mini-code / t07_node_drain / trial_1: spec
- status `graded`, load_error `None`, safety_reason `vacuous_safety`, liveness_reason `None`, finish_reason `stop`, completion_tokens 26961
- solo FAIL: drain succeeds when every shard keeps a replica: raised RuntimeError: Failed to drain node after retries; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- solo FAIL: drain is refused if any shard would lose its last replica, and nothing changes: raised RuntimeError: Failed to drain node after retries
- solo FAIL: shards without an active replica on the node do not block it: raised RuntimeError: Failed to drain node after retries; violated: expected state: SELECT array_agg(active ORDER BY shard_id, node_id) = '{f,t,f,t}' FROM replicas
 (got [(False,)])
- scenario `two drains of nodes sharing several shards, both fit`: status ok, safe=True (0 unsafe), live=False (2200 unlive) of 2200 schedules, exhaustive=False, reproduced=True; serial: 0 unsafe, 2 unlive of 2
- scenario `two drains of nodes with no shared shard`: status ok, safe=True (0 unsafe), live=False (2200 unlive) of 2200 schedules, exhaustive=False, reproduced=True; serial: 0 unsafe, 2 unlive of 2
- counterexample: `results/20261106T123821Z/north-mini-code/t07_node_drain/trial_1/counterexample_1.txt`
- counterexample: `results/20261106T123821Z/north-mini-code/t07_node_drain/trial_1/counterexample_2.txt`
- counterexample: `results/20261106T123821Z/north-mini-code/t07_node_drain/trial_1/counterexample_3.txt`

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
| north-mini-code | t01_flash_sale | trial_1 | 14980 | 79.92 | 1 | stop | Cohere |
| north-mini-code | t02_on_call | trial_1 | 17303 | 103.71 | 1 | stop | Cohere |
| north-mini-code | t03_expense_budget | trial_1 | 20011 | 158.14 | 1 | stop | Cohere |
| north-mini-code | t04_room_booking | trial_1 | 10722 | 69.61 | 1 | stop | Cohere |
| north-mini-code | t05_wallet_transfer | trial_1 | 12518 | 93.95 | 1 | stop | Cohere |
| north-mini-code | t06_idempotent_payment | trial_1 | 14579 | 84.12 | 1 | stop | Cohere |
| north-mini-code | t07_node_drain | trial_1 | 26961 | 129.24 | 1 | stop | Cohere |

spent_usd: 0.0, api_calls: 14, sessions: 4, complete: True
