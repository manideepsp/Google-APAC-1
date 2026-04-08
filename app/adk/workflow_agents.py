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

from app.core.vertex_runtime import configure_vertex_runtime
from app.core.utils.json_parser import extract_json
from app.db.sqlite import insert_task
from app.services.sheets_sync import sync_tasks_to_sheets

_APP_NAME = "google-apac-1-workflow"
_DEFAULT_MODEL = "gemini-2.5-flash"
_DEFAULT_LOCATION = "us-central1"

load_dotenv(override=False)


def _configure_adk_runtime() -> None:
    configure_vertex_runtime(default_location=_DEFAULT_LOCATION)


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
                continue

            # Some model/tool paths emit structured parts instead of plain text.
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                args = getattr(function_call, "args", None)
                if args is not None:
                    if isinstance(args, str):
                        chunks.append(args)
                    else:
                        chunks.append(json.dumps(args))
                continue

            function_response = getattr(part, "function_response", None)
            if function_response is not None:
                response = getattr(function_response, "response", None)
                if response is not None:
                    if isinstance(response, str):
                        chunks.append(response)
                    else:
                        chunks.append(json.dumps(response))

    return "\n".join(chunks).strip()


def _is_transient_model_error(exc: Exception) -> bool:
    text = str(exc).upper()
    return (
        "RESOURCE_EXHAUSTED" in text
        or "UNAVAILABLE" in text
        or "429" in text
        or "503" in text
    )


def _run_text_agent(
    *,
    instruction: str,
    prompt: str,
    tools: list[Callable[..., Any]] | None = None,
    model: str = _DEFAULT_MODEL,
    user_id: str = "workflow-user",
    json_response: bool = False,
) -> str:
    _configure_adk_runtime()

    async def _run_async() -> str:
        max_attempts = max(1, int(os.getenv("ADK_TRANSIENT_RETRIES", "3")))
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            session_service = InMemorySessionService()
            session_id = str(uuid.uuid4())

            await session_service.create_session(
                app_name=_APP_NAME,
                user_id=user_id,
                session_id=session_id,
            )

            agent_tools = [FunctionTool(tool) for tool in (tools or [])]
            agent_kwargs: dict[str, Any] = {
                "name": f"adk_{uuid.uuid4().hex[:8]}",
                "model": model,
                "instruction": instruction,
                "tools": agent_tools,
            }
            if json_response:
                agent_kwargs["generate_content_config"] = types.GenerateContentConfig(
                    response_mime_type="application/json"
                )

            agent = Agent(**agent_kwargs)

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
            except Exception as exc:
                last_exc = exc
                if attempt >= max_attempts or not _is_transient_model_error(exc):
                    raise
                await asyncio.sleep(min(2 * attempt, 8))
            finally:
                close_result = runner.close()
                if inspect.isawaitable(close_result):
                    await close_result

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("ADK run failed without an explicit exception")

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
        json_response=True,
    )
    parsed = extract_json(text)
    if not isinstance(parsed, list):
        raise RuntimeError("ADK did not return a JSON list")

    result = [item for item in parsed if isinstance(item, dict)]
    if not result:
        raise RuntimeError("ADK returned an empty JSON task list")
    return result


def plan_tasks_with_adk(
    *,
    goal: str,
    titles: list[str],
    insights: Any,
    related_tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    related_context = json.dumps((related_tasks or [])[:12], ensure_ascii=False)

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

Relevant Tasks From Previous Generations (AlloyDB Memory):
{related_context}

Generate actionable tasks.
Rules:
- Reuse useful prior task patterns when relevant.
- Avoid direct duplicates from memory.
- Keep task sequence practical and incremental.

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


def reflect_tasks_with_adk(
    *,
    kpis: dict[str, Any],
    current_tasks: list[dict[str, Any]],
    related_tasks: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    related_context = json.dumps((related_tasks or [])[:12], ensure_ascii=False)

    instruction = (
        "You are a YouTube growth strategist optimizing a task plan based on performance. "
        "Return only a JSON array with fields task, priority, day."
    )
    prompt = f"""
Channel Performance KPIs:
{kpis}

Previous Tasks:
{current_tasks}

Relevant Tasks From Previous Generations (AlloyDB Memory):
{related_context}

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


def _persist_and_sync_tasks(
    user_id: str,
    tasks_json: str,
    channel_id: str | None = None,
    run_id: str | None = None,
    goal_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
            channel_id=channel_id,
            run_id=run_id,
            goal_params=goal_params or {},
            origin_run_id=run_id,
            origin_context={"source": "goal_workflow"},
        )
        inserted += 1

    sync_tasks_to_sheets(user_id=user_id or None)
    if inserted == 0:
        raise RuntimeError("No tasks were inserted by ADK execution tool")
    return {"inserted": inserted, "synced": True}


def execute_tasks_with_adk(
    *,
    tasks: list[dict[str, Any]],
    user_id: str | None,
    channel_id: str | None = None,
    run_id: str | None = None,
    goal_params: dict[str, Any] | None = None,
) -> str:
    payload = json.dumps(tasks)
    safe_user_id = user_id or ""

    # Execution is deterministic once tasks are produced; persist without another model hop.
    result = _persist_and_sync_tasks(
        user_id=safe_user_id,
        tasks_json=payload,
        channel_id=channel_id,
        run_id=run_id,
        goal_params=goal_params,
    )
    return json.dumps(result)