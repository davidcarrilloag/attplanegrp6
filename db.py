from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import quote_plus

import polars as pl
from sqlalchemy import Engine, create_engine, text


_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DBConfig:
    host: str = "52.211.123.34"
    port: int = 25010
    database: str = "ATTPLANE"
    username: str = "attgrp6"
    password: str = "bigdata"
    schema: str = "ATTGRP6"

    @classmethod
    def from_env(cls) -> "DBConfig":
        username = os.getenv("DB_USERNAME", cls.username)
        return cls(
            host=os.getenv("DB_HOST", cls.host),
            port=int(os.getenv("DB_PORT", str(cls.port))),
            database=os.getenv("DB_NAME", cls.database),
            username=username,
            password=os.getenv("DB_PASSWORD", cls.password),
            schema=os.getenv("DB_SCHEMA", username.upper()),
        )

    @property
    def sqlalchemy_url(self) -> str:
        user = quote_plus(self.username)
        password = quote_plus(self.password)
        return f"db2+ibm_db://{user}:{password}@{self.host}:{self.port}/{self.database}"


def make_engine(config: DBConfig | None = None) -> Engine:
    config = config or DBConfig.from_env()
    return create_engine(config.sqlalchemy_url, pool_pre_ping=True)


def quote_identifier(identifier: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")
    return identifier.upper()


def table_name(table: str, config: DBConfig | None = None) -> str:
    config = config or DBConfig.from_env()
    return f"{quote_identifier(config.schema)}.{quote_identifier(table)}"


def read_sql(engine: Engine, query: str) -> pl.DataFrame:
    return pl.read_database(query=query, connection=engine)


def table_row_counts(engine: Engine, config: DBConfig | None = None) -> pl.DataFrame:
    config = config or DBConfig.from_env()
    query = text(
        """
        SELECT RTRIM(tabname) AS table_name, card AS estimated_rows
        FROM syscat.tables
        WHERE tabschema = :schema
          AND type = 'T'
        ORDER BY tabname
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"schema": config.schema.upper()}).mappings().all()
    return pl.DataFrame(rows)
