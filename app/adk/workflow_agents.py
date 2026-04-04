import asyncio
import inspect
import json
import os
import uuid
from typing import Any, Callable, Iterable

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.genai import types

from app.core.utils.json_parser import extract_json
from app.db.sqlite import insert_task
from app.services.sheets_sync import sync_tasks_to_sheets

_APP_NAME = "google-apac-1-workflow"
_DEFAULT_MODEL = "gemini-2.5-flash"

load_dotenv(override=False)


def _collect_text(events: Iterable[Any]) -> str:
    chunks: list[str] = []
    for event in events:
        error_message = getattr(event, "error_message", None)
        if error_message:
            raise RuntimeError(str(error_message))

        content = getattr(event, "content", None)
        if not content or not content.parts:
            continue

        for part in content.parts:
            text = getattr(part, "text", None)
            if text:
                chunks.append(text)

    return "\n".join(chunks).strip()


def _run_text_agent(
    *,
    instruction: str,
    prompt: str,
    tools: list[Callable[..., Any]] | None = None,
    model: str = _DEFAULT_MODEL,
    user_id: str = "workflow-user",
) -> str:
    if not os.getenv("GOOGLE_API_KEY"):
        raise RuntimeError("GOOGLE_API_KEY is not configured for ADK runtime")

    async def _run_async() -> str:
        session_service = InMemorySessionService()
        session_id = str(uuid.uuid4())

        await session_service.create_session(
            app_name=_APP_NAME,
            user_id=user_id,
            session_id=session_id,
        )

        agent_tools = [FunctionTool(tool) for tool in (tools or [])]
        agent = Agent(
            name=f"adk_{uuid.uuid4().hex[:8]}",
            model=model,
            instruction=instruction,
            tools=agent_tools,
        )

        runner = Runner(
            app_name=_APP_NAME,
            agent=agent,
            session_service=session_service,
        )

        try:
            message = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            events: list[Any] = []
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=message):
                events.append(event)

            text = _collect_text(events)
            if not text.strip():
                raise RuntimeError("ADK returned empty text response")
            return text
        finally:
            close_result = runner.close()
            if inspect.isawaitable(close_result):
                await close_result

    return asyncio.run(_run_async())


def _run_json_agent(
    *,
    instruction: str,
    prompt: str,
    model: str = _DEFAULT_MODEL,
    user_id: str = "workflow-user",
) -> list[dict[str, Any]]:
    text = _run_text_agent(
        instruction=instruction,
        prompt=prompt,
        tools=None,
        model=model,
        user_id=user_id,
    )
    parsed = extract_json(text)
    if not isinstance(parsed, list):
        raise RuntimeError("ADK did not return a JSON list")

    result = [item for item in parsed if isinstance(item, dict)]
    if not result:
        raise RuntimeError("ADK returned an empty JSON task list")
    return result


def plan_tasks_with_adk(*, goal: str, titles: list[str], insights: Any) -> list[dict[str, Any]]:
    instruction = (
        "You are an expert YouTube growth strategist. "
        "Always return only a JSON array of tasks with fields task, priority, day."
    )
    prompt = f"""
Goal:
{goal}

Trending Signals:
{titles}

Strategic Insights:
{insights}

Generate actionable tasks.
Return ONLY JSON:
[
  {{
    "task": "...",
    "priority": "High/Medium/Low",
    "day": "Day X"
  }}
]
"""
    return _run_json_agent(instruction=instruction, prompt=prompt)


def summarize_research_with_adk(
    *,
    goal: str,
    titles: list[str],
    analytics_data: Any,
    web_insights: list[dict[str, Any]],
    kpis: dict[str, Any],
) -> str:
    instruction = (
        "You are a YouTube growth strategist. "
        "Return concise, actionable, data-driven strategy insights as plain text."
    )
    prompt = f"""
Goal:
{goal}

Trending YouTube Titles:
{titles}

Channel Performance Insights:
{analytics_data}

Web Insights:
{web_insights}

KPIs:
{kpis}

Provide:
1. Emerging Trends
2. Winning Patterns
3. Strategic Recommendations
4. Content Opportunities
"""
    return _run_text_agent(instruction=instruction, prompt=prompt)


def reflect_tasks_with_adk(*, kpis: dict[str, Any], current_tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    instruction = (
        "You are a YouTube growth strategist optimizing a task plan based on performance. "
        "Return only a JSON array with fields task, priority, day."
    )
    prompt = f"""
Channel Performance KPIs:
{kpis}

Previous Tasks:
{current_tasks}

Based on performance:
- What is working?
- What should change?
- Generate improved tasks

Return ONLY JSON:
[
  {{
    "task": "...",
    "priority": "High/Medium/Low",
    "day": "Day X"
  }}
]
"""
    return _run_json_agent(instruction=instruction, prompt=prompt)


def _persist_and_sync_tasks(user_id: str, tasks_json: str) -> dict[str, Any]:
    parsed = extract_json(tasks_json)
    tasks = parsed if isinstance(parsed, list) else []

    inserted = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        insert_task(
            task=str(task.get("task", "")),
            priority=str(task.get("priority", "Medium")),
            day=str(task.get("day", "Day 1")),
            user_id=user_id or None,
        )
        inserted += 1

    sync_tasks_to_sheets(user_id=user_id or None)
    if inserted == 0:
        raise RuntimeError("No tasks were inserted by ADK execution tool")
    return {"inserted": inserted, "synced": True}


def execute_tasks_with_adk(*, tasks: list[dict[str, Any]], user_id: str | None) -> str:
    payload = json.dumps(tasks)
    safe_user_id = user_id or ""

    instruction = (
        "You are an execution agent for workflow operations. "
        "Always call the provided tool exactly once with the user_id and tasks_json, then respond DONE."
    )
    prompt = (
        "Persist and sync the tasks now. "
        f"user_id={safe_user_id}\n"
        f"tasks_json={payload}"
    )

    return _run_text_agent(
        instruction=instruction,
        prompt=prompt,
        tools=[_persist_and_sync_tasks],
        user_id=safe_user_id or "workflow-user",
    )