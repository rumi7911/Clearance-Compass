"""Agent definitions for Clearance Compass.

Three roles map directly to the hackathon's required plan -> act ->
evaluate -> iterate loop:

  Extractor (PLAN)   - structured-output LlmAgent, no tools. Reads a scene
                        and lists the real-world entities worth clearing.
  Researcher (ACT)   - LlmAgent with the Parallel Search MCP toolset
                        attached. Calls web_search / web_fetch live.
  Critic (EVALUATE)  - LlmAgent with a single custom tool, submit_verdict,
                        that records a confidence-scored verdict and either
                        stops the loop (tool_context.actions.escalate) or
                        hands back a reformulated query for another pass.

output_schema and tools cannot be combined reliably across models (per ADK
docs), so only the tool-free Extractor uses output_schema. Researcher and
Critic report structured results by calling a tool instead.
"""

from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.tool_context import ToolContext

MODEL = os.environ.get("CLEARANCE_COMPASS_MODEL", "gemini-2.5-flash")
CONFIDENCE_THRESHOLD = 0.7

EntityCategory = Literal["brand", "person", "song", "archival", "location", "other"]


class EntityCandidate(BaseModel):
    name: str = Field(description="The specific real-world name, e.g. 'Coca-Cola'.")
    category: EntityCategory


class ExtractedEntities(BaseModel):
    entities: list[EntityCandidate]


def _parallel_toolset() -> McpToolset:
    api_key = os.environ.get("PARALLEL_API_KEY", "")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url="https://search.parallel.ai/mcp",
            headers=headers,
        ),
    )


def build_extractor_agent() -> LlmAgent:
    return LlmAgent(
        model=MODEL,
        name="extractor",
        description="Extracts clearance-relevant entities from a scene of screenplay text.",
        instruction=(
            "You are a production clearance coordinator. Read the scene text below "
            "and list every real-world brand, trademark, public figure, song or "
            "composition, archival footage/photo reference, and real named location "
            "that a production would need to research before using this scene as "
            "written. Ignore invented character names and generic, non-branded "
            "props. Be precise: use the specific real-world name (e.g. 'Coca-Cola', "
            "not 'a soda can').\n\nSCENE:\n{scene_text}"
        ),
        output_schema=ExtractedEntities,
        output_key="extracted_entities",
    )


def build_researcher_agent() -> LlmAgent:
    return LlmAgent(
        model=MODEL,
        name="researcher",
        description="Researches a single clearance-relevant entity using live web search.",
        instruction=(
            "You are a rights-clearance researcher. Investigate the following "
            "entity so a producer can assess clearance risk.\n\n"
            "Entity: {entity_name}\n"
            "Category: {entity_category}\n"
            "Appears in this scene: {scene_text}\n\n"
            "Refined search angle to prioritize, if provided: {retry_query?}\n\n"
            "Use web_search to find who currently holds the rights, any licensing "
            "precedent, and any recent disputes or cease-and-desist history. Use "
            "web_fetch on the one or two strongest results to pull full context. "
            "Finish with a concise plain-text research summary: what you found, "
            "how many independent sources agree, the exact source URLs you used, "
            "and -- explicitly, for each source -- its publication or last-updated "
            "date if you can determine one. If you cannot determine a date for a "
            "source, say so plainly rather than omitting the point; do not imply "
            "recency you haven't confirmed."
        ),
        tools=[_parallel_toolset()],
        output_key="research_notes",
    )


def submit_verdict(
    confidence: float,
    risk_level: Literal["green", "yellow", "red"],
    reasoning: str,
    retry_query: str,
    tool_context: ToolContext,
) -> dict:
    """Record this round's clearance assessment and decide whether to stop or retry.

    Args:
        confidence: 0.0-1.0 confidence that the gathered evidence is strong
            enough to make the clearance risk call.
        risk_level: overall clearance risk if we stopped here.
        reasoning: one or two sentences explaining the call.
        retry_query: if confidence is below 0.7, a genuinely different search
            angle to try next; empty string if not retrying.
    """
    attempts = list(tool_context.state.get("attempts", []))
    attempts.append(
        {
            "confidence": confidence,
            "risk_level": risk_level,
            "reasoning": reasoning,
            "retry_query": retry_query,
            "research_notes": tool_context.state.get("research_notes", ""),
        }
    )
    tool_context.state["attempts"] = attempts

    should_stop = confidence >= CONFIDENCE_THRESHOLD or not retry_query
    if should_stop:
        tool_context.actions.escalate = True
    else:
        tool_context.state["retry_query"] = retry_query
    return {"recorded": True, "stopping": should_stop}


def build_critic_agent() -> LlmAgent:
    return LlmAgent(
        model=MODEL,
        name="critic",
        description="Evaluates whether the research gathered is strong enough to close a clearance item.",
        instruction=(
            "You are a skeptical clearance reviewer, separate from the "
            "researcher. Read the research notes below and judge whether they "
            "are strong enough to make a clearance risk call for this entity.\n\n"
            "Entity: {entity_name} ({entity_category})\n"
            "Research notes:\n{research_notes}\n\n"
            f"Before calling confidence {CONFIDENCE_THRESHOLD} or higher, the "
            "notes must clearly establish BOTH: (1) at least two independent "
            "sources that agree, AND (2) at least one of those sources has a "
            "confirmed publication or last-updated date within roughly the "
            "last 18 months. A source with no stated date does not count "
            "toward recency -- treat undated evidence as unconfirmed, not as "
            "presumed current, since rights holders and licensing status can "
            "change. If either condition isn't clearly met, set confidence "
            f"below {CONFIDENCE_THRESHOLD} and propose a genuinely different "
            "search angle (not a rephrasing) in retry_query -- for example, "
            "add a recent year, ask about a specific recent event, or search "
            "a different source type (news vs. official registry vs. trade "
            "press). Call submit_verdict exactly once with your assessment."
        ),
        tools=[submit_verdict],
    )


def build_research_loop(max_iterations: int = 2) -> LoopAgent:
    return LoopAgent(
        name="research_loop",
        sub_agents=[build_researcher_agent(), build_critic_agent()],
        max_iterations=max_iterations,
    )
