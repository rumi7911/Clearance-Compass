"""Driver: deterministic loop over scenes/entities, autonomous work inside each.

The fan-out over scenes and entities below is plain Python, not an LLM
decision -- and that's intentional, not a shortcut. The required autonomy
(plan -> act -> evaluate -> iterate, the agent judging its own progress)
lives entirely inside each entity's research_loop run: whether to retry,
with what query, and when to stop is decided by the Critic agent via
submit_verdict, not by this driver.
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import time


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .agents import CONFIDENCE_THRESHOLD, build_extractor_agent, build_research_loop
from .data import memory
from .data.precleared import lookup as precleared_lookup
from .data.scenes import SCENES

# Bounds worst-case entity count per scene: an adversarial or pathological
# script (e.g. a wall of brand names) could otherwise make the Extractor
# fan out into dozens of paid Parallel/Vertex calls from one request.
MAX_ENTITIES_PER_SCENE = 8

# Holds references to fire-and-forget memory.record_decision() tasks so they
# can't be garbage-collected before completing (a well-known asyncio gotcha
# with bare asyncio.create_task calls).
_background_tasks: set[asyncio.Task] = set()

APP_NAME = "clearance-compass"
USER_ID = "demo"

# Brand-new GCP projects start with very low default per-minute quota on
# Vertex AI's generative models -- low enough that even 2 concurrent entity
# pipelines reliably triggered 429 RESOURCE_EXHAUSTED in testing. Serializing
# is slower but reliable without requesting a quota increase before the demo;
# raise this once a increase is granted (Vertex AI console > Quotas).
_GEMINI_CONCURRENCY = asyncio.Semaphore(1)
_MAX_RETRIES = 5
_RETRYABLE_MARKERS = (
    "RESOURCE_EXHAUSTED",
    "429",
    # Transient MCP/session hiccups observed in production logs that
    # self-recovered elsewhere in the same run when retried -- not a
    # logic bug, just flaky infra worth one more attempt.
    "Tool 'submit_verdict' not found",
    "Failed to create MCP session",
    "BrokenResourceError",
)


async def _run_agent(agent, *, state: dict, trigger_text: str) -> tuple[dict, list]:
    """Runs `agent` in a fresh in-memory session; returns (final_state, events).

    Rate-limited (see _GEMINI_CONCURRENCY) and retried with backoff on
    transient quota errors.
    """
    async with _GEMINI_CONCURRENCY:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                session_service = InMemorySessionService()
                # Deep-copy so a mid-loop failure (which mutates `state` by
                # reference via tool_context.state) can't leak partial
                # progress into the next retry -- each attempt gets the
                # loop's own fresh iteration budget.
                session = await session_service.create_session(
                    app_name=APP_NAME, user_id=USER_ID, state=copy.deepcopy(state),
                )
                runner = Runner(
                    agent=agent, app_name=APP_NAME, session_service=session_service
                )
                content = types.Content(role="user", parts=[types.Part(text=trigger_text)])

                events = []
                async for event in runner.run_async(
                    user_id=USER_ID, session_id=session.id, new_message=content
                ):
                    events.append(event)

                final_session = await session_service.get_session(
                    app_name=APP_NAME, user_id=USER_ID, session_id=session.id
                )
                return final_session.state, events
            except Exception as exc:  # noqa: BLE001 -- see _RETRYABLE_MARKERS below
                retryable = any(marker in str(exc) for marker in _RETRYABLE_MARKERS)
                if not retryable or attempt == _MAX_RETRIES:
                    raise
                wait_s = min(60, 5 * (2 ** (attempt - 1)))
                _log(
                    f"  quota hit (attempt {attempt}/{_MAX_RETRIES}), "
                    f"backing off {wait_s}s"
                )
                await asyncio.sleep(wait_s)
        raise RuntimeError("unreachable")  # pragma: no cover


def _extract_search_trail(events: list) -> list[dict]:
    """Pulls the actual web_search / web_fetch calls out of the raw event stream --
    this is what lets the UI show real queries and URLs, not a paraphrase."""
    trail = []
    for event in events:
        for call in event.get_function_calls() or []:
            if call.name in ("web_search", "web_fetch"):
                trail.append({"tool": call.name, "args": dict(call.args or {})})
    return trail


async def _extract_entities(scene_text: str) -> list[dict]:
    state, _events = await _run_agent(
        build_extractor_agent(),
        state={"scene_text": scene_text},
        trigger_text="Extract the clearance-relevant entities from this scene.",
    )
    extracted = state.get("extracted_entities") or {}
    entities = extracted.get("entities", [])
    return entities[:MAX_ENTITIES_PER_SCENE]


async def _clear_entity(
    entity_name: str,
    entity_category: str,
    scene_text: str,
    *,
    force_fresh: bool = False,
) -> dict:
    precleared = precleared_lookup(entity_name)
    if precleared:
        _log(f"  {entity_name}: precleared, skipping research")
        return {
            "name": entity_name,
            "category": entity_category,
            "risk": "green",
            "resolved": True,
            "attempts": [],
            "search_trail": [],
            "reasoning": precleared["note"],
            "source": "internal-release-repository",
            "license_ref": precleared["license_ref"],
        }

    if not force_fresh:
        remembered = await memory.lookup_memory(entity_name, entity_category)
        if remembered:
            _log(f"  {entity_name}: found fresh agent-memory record, skipping live research")
            return {
                "name": entity_name,
                "category": entity_category,
                "risk": remembered["risk"],
                "resolved": True,
                "attempts": remembered["attempts"],
                "search_trail": remembered["search_trail"],
                "reasoning": remembered["reasoning"],
                "source": "agent-memory",
                "resolved_at": remembered["resolved_at"],
            }

    _log(f"  {entity_name}: starting research loop")
    try:
        state, events = await _run_agent(
            build_research_loop(),
            state={
                "entity_name": entity_name,
                "entity_category": entity_category,
                "scene_text": scene_text,
                "retry_query": "",
                "attempts": [],
            },
            trigger_text="Begin the research and evaluation loop for this entity.",
        )
    except Exception as exc:  # noqa: BLE001 -- one entity's failure shouldn't 500 the whole request
        _log(f"  {entity_name}: research loop failed ({exc}), reporting as unresolved")
        return {
            "name": entity_name,
            "category": entity_category,
            "risk": "red",
            "resolved": False,
            "attempts": [],
            "search_trail": [],
            "reasoning": f"Research failed and needs manual review: {exc}",
            "source": "error",
        }
    _log(f"  {entity_name}: research loop done ({len(state.get('attempts', []))} round(s))")

    attempts = state.get("attempts", [])
    latest = attempts[-1] if attempts else {
        "risk_level": "red",
        "confidence": 0.0,
        "reasoning": "No verdict was recorded -- treat as unresolved and escalate manually.",
    }
    # The loop can stop either because the Critic was satisfied (confidence
    # met CONFIDENCE_THRESHOLD) or because it simply ran out of the 2-round
    # cap while still unsure. Those aren't the same thing: an exhausted,
    # still-low-confidence guess must not be presented -- or cached -- as a
    # settled verdict.
    resolved = latest.get("confidence", 0.0) >= CONFIDENCE_THRESHOLD
    result = {
        "name": entity_name,
        "category": entity_category,
        "risk": latest["risk_level"],
        "resolved": resolved,
        "attempts": attempts,
        "search_trail": _extract_search_trail(events),
        "reasoning": latest["reasoning"]
        if resolved
        else (
            f"{latest['reasoning']} (Research exhausted its retry budget "
            "without reaching confidence -- treat this as unresolved and "
            "needing manual review, not a settled clearance.)"
        ),
        "source": "parallel-mcp",
    }
    if resolved:
        task = asyncio.create_task(memory.record_decision(result))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return result


async def run_pipeline(scenes: list[dict] | None = None, *, force_fresh: bool = False) -> dict:
    scenes = scenes if scenes is not None else SCENES
    graph = {"scenes": []}
    for scene in scenes:
        _log(f"Scene {scene['id']}: extracting entities")
        try:
            entities = await _extract_entities(scene["text"])
        except Exception as exc:  # noqa: BLE001 -- one scene's extractor failure shouldn't sink the whole run
            _log(f"Scene {scene['id']}: entity extraction failed ({exc}), skipping scene")
            graph["scenes"].append(
                {
                    "id": scene["id"],
                    "heading": scene["heading"],
                    "text": scene["text"],
                    "entities": [],
                    "error": f"Entity extraction failed for this scene: {exc}",
                }
            )
            continue
        _log(f"Scene {scene['id']}: found {[e['name'] for e in entities]}")
        entity_results = await asyncio.gather(
            *[
                _clear_entity(e["name"], e["category"], scene["text"], force_fresh=force_fresh)
                for e in entities
            ]
        )
        graph["scenes"].append(
            {
                "id": scene["id"],
                "heading": scene["heading"],
                "text": scene["text"],
                "entities": list(entity_results),
            }
        )
    return graph


if __name__ == "__main__":
    result = asyncio.run(run_pipeline())
    print(json.dumps(result, indent=2))
