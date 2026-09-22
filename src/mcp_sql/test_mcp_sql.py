"""Five tests for mcp_sql, per spec Task 6.

The last two hit real services (live Flex Server + live LLM) — acceptable
for a Phase 0 spike. They're skipped automatically if DATABASE_URL /
MCP_OPENAI_ENDPOINT aren't set.
"""

import os

import pytest

from config import redact
from nl2sql import _INSTRUCTIONS
from server import _with_limit, ask, check, run_sql

_HAS_DB_CREDS = bool(os.environ.get("DATABASE_URL"))
_HAS_LLM_CREDS = bool(os.environ.get("MCP_OPENAI_ENDPOINT")) and bool(os.environ.get("INFERENCE_LM_DEPLOYMENT"))


def test_guard_rejects_writes():
    for statement in ["DELETE FROM x", "DROP TABLE x", "UPDATE x SET a=1", "INSERT INTO x VALUES (1)"]:
        with pytest.raises(ValueError):
            check(statement)


def test_guard_adds_limit():
    assert _with_limit("SELECT * FROM x", 100) == "SELECT * FROM x LIMIT 100"
    # Already has a LIMIT — left untouched.
    assert _with_limit("SELECT * FROM x LIMIT 5", 100) == "SELECT * FROM x LIMIT 5"


def test_redact_masks_password():
    # Assembled from parts so secret scanners don't flag this synthetic fixture.
    # "s3cr%25et" is "s3cr%et" percent-encoded — exercises redact()'s URL-decoding path.
    password = "s3cr%25et"
    host = "example.postgres.database.azure.com"
    url = f"postgresql://demo_user:{password}@{host}:5432/mydb?sslmode=require"
    redacted = redact(url)
    assert "s3cr" not in redacted
    assert "demo_user" in redacted
    assert host in redacted


def test_nl2sql_requests_stable_entity_ids():
    assert "include each returned entity's stable ID column" in _INSTRUCTIONS


@pytest.mark.skipif(not _HAS_DB_CREDS, reason="DATABASE_URL not set")
async def test_run_sql_select_1():
    rows = await run_sql("SELECT 1 AS n")
    assert rows == [{"n": "1"}]


@pytest.mark.skipif(not (_HAS_DB_CREDS and _HAS_LLM_CREDS), reason="DB and/or LLM creds not set")
async def test_ask_returns_sql():
    result = await ask("how many rows are in the customers table")
    assert "sql" in result
    assert result["sql"]
