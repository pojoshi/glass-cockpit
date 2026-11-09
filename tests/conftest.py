import os

import pytest
from countersigned.seed import seed_demo
from countersigned.service import Gate

from glasscockpit.db import open_db, reset_control_plane
from glasscockpit import fleet


@pytest.fixture
def db():
    dsn = os.environ.get("GLASSCOCKPIT_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("set GLASSCOCKPIT_TEST_DATABASE_URL to run the Postgres tests")
    database = open_db(dsn)
    database.reset_all()
    reset_control_plane(dsn)
    yield database
    database.close()


@pytest.fixture
def gate(db):
    g = Gate(db)
    seed_demo(g)
    fleet.register_fleet(db)
    fleet.ensure_operator(g)
    return g
