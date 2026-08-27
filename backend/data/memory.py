"""ClickHouse-backed agent memory: past live-research verdicts, reusable
across runs so the pipeline doesn't re-research what it already settled --
the same "don't redo settled work" idea as precleared.py, but built from
the agent's own research history instead of a hand-maintained list.

Every function in this module is best-effort: if ClickHouse credentials
are absent or a call fails, we log and return None / no-op rather than
raise, so the pipeline works identically to today when this is unconfigured.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

MEMORY_FRESHNESS_DAYS = 548  # ~18 months -- matches the Critic's evidence-
# recency bar in agents.py's build_critic_agent() prompt. Keep these in sync.

_client = None
_client_init_attempted = False


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


def _normalize(entity_name: str) -> str:
    return entity_name.strip().lower().strip("\"'")


async def _get_client():
    global _client, _client_init_attempted
    if _client is not None:
        return _client
    if _client_init_attempted:
        return None  # already failed once this process; don't retry every call
    _client_init_attempted = True

    host = os.environ.get("CLICKHOUSE_HOST")
    if not host:
        _log("memory: CLICKHOUSE_HOST not set, agent memory disabled")
        return None
    try:
        import clickhouse_connect

        _client = await clickhouse_connect.get_async_client(
            host=host,
            port=int(os.environ.get("CLICKHOUSE_PORT", "8443")),
            username=os.environ.get("CLICKHOUSE_USER", "default"),
            password=os.environ.get("CLICKHOUSE_PASSWORD", ""),
            database=os.environ.get("CLICKHOUSE_DATABASE", "default"),
            secure=True,
        )
    except Exception as exc:  # noqa: BLE001 -- degrade, never crash the pipeline
        _log(f"memory: failed to connect to ClickHouse ({exc}), disabling agent memory")
        _client = None
    return _client


async def lookup_memory(entity_name: str) -> dict | None:
    """Returns the most recent still-fresh decision for this entity, or
    None if there isn't one / memory is unavailable / it's gone stale.
    """
    client = await _get_client()
    if client is None:
        return None
    key = _normalize(entity_name)
    try:
        result = await client.query(
            """
            SELECT entity_name, category, risk, reasoning, confidence,
                   attempts_json, search_trail_json, resolved_at
            FROM clearance_decisions
            WHERE entity_key = {key:String}
            ORDER BY resolved_at DESC
            LIMIT 1
            """,
            parameters={"key": key},
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"memory: lookup failed for {entity_name!r} ({exc}), falling through to live research")
        return None

    if not result.result_rows:
        return None

    row = result.result_rows[0]
    (
        name,
        category,
        risk,
        reasoning,
        confidence,
        attempts_json,
        search_trail_json,
        resolved_at,
    ) = row

    resolved_at_utc = resolved_at if resolved_at.tzinfo else resolved_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - resolved_at_utc
    if age > timedelta(days=MEMORY_FRESHNESS_DAYS):
        _log(f"memory: {entity_name!r} found but stale ({age.days}d old), falling through to live research")
        return None

    return {
        "name": name,
        "category": category,
        "risk": risk,
        "reasoning": reasoning,
        "confidence": confidence,
        "attempts": json.loads(attempts_json),
        "search_trail": json.loads(search_trail_json),
        "resolved_at": resolved_at_utc.isoformat(),
    }


async def record_decision(entity: dict) -> None:
    """Persists a freshly-resolved (Tier 3) entity for future reuse.
    Never raises -- a failed write should not fail the user-facing request.
    """
    client = await _get_client()
    if client is None:
        return
    try:
        attempts = entity.get("attempts") or []
        await client.insert(
            "clearance_decisions",
            [
                [
                    _normalize(entity["name"]),
                    entity["name"],
                    entity["category"],
                    entity["risk"],
                    entity["reasoning"],
                    attempts[-1]["confidence"] if attempts else 0.0,
                    json.dumps(attempts),
                    json.dumps(entity.get("search_trail") or []),
                    datetime.now(timezone.utc),
                    entity.get("scene_excerpt", ""),
                ]
            ],
            column_names=[
                "entity_key",
                "entity_name",
                "category",
                "risk",
                "reasoning",
                "confidence",
                "attempts_json",
                "search_trail_json",
                "resolved_at",
                "scene_excerpt",
            ],
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"memory: failed to record decision for {entity.get('name')!r} ({exc}); continuing")
