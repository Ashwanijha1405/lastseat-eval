import itertools
import os

import pytest

from lastseat.scheduler import Explorer, build_template, drop_database

COUNTER_SETUP = "CREATE TABLE counter (id int PRIMARY KEY, n int NOT NULL);"
COUNTER_SEED = "INSERT INTO counter VALUES (1, 0);"

_ids = itertools.count()


@pytest.fixture
def explorer():
    """Factory: build a template database, return an Explorer over it, clean up after."""
    made: list[Explorer] = []

    def make(requests, invariants, *, setup=COUNTER_SETUP, seed=COUNTER_SEED, **kwargs) -> Explorer:
        name = f"lastseat_test_{os.getpid()}_{next(_ids)}"
        build_template(name, setup, seed_sql=seed)
        ex = Explorer(name, requests, invariants, **kwargs)
        made.append(ex)
        return ex

    yield make
    for ex in made:
        ex.close()
        drop_database(ex.template)
