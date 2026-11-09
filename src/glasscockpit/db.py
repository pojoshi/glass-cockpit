"""Applies this project's schema on top of countersigned's. Same database, same pool."""

from importlib import resources

import psycopg
from countersigned.db import Database


def open_db(dsn: str) -> Database:
    db = Database(dsn)  # bootstraps countersigned's own tables first
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute(resources.files("glasscockpit").joinpath("schema.sql").read_text())
    return db


def reset_control_plane(dsn: str) -> None:
    """Wipe this project's own tables. Tests and demos only."""
    with psycopg.connect(dsn, autocommit=True) as c:
        c.execute("TRUNCATE fleet_agents, events RESTART IDENTITY")
