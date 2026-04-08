import json
import os
from pathlib import Path

import google.auth


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _credentials_candidates() -> list[Path]:
    candidates: list[Path] = []

    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.append(_repo_root() / "keys" / "credentials.json")

    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resolved)

    return deduped


def _project_from_credentials_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    project = str(payload.get("project_id", "")).strip()
    if not project:
        return None
    return project


def _bootstrap_adc_credentials() -> None:
    env_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and Path(env_path).expanduser().exists():
        return

    for candidate in _credentials_candidates():
        if candidate.exists() and candidate.is_file():
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate)
            return


def _project_from_adc() -> str | None:
    _bootstrap_adc_credentials()

    try:
        _, project = google.auth.default()
    except Exception:
        return None

    project_id = str(project or "").strip()
    return project_id or None


def resolve_vertex_project() -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID")
    if project:
        project = project.strip()
        if project:
            _bootstrap_adc_credentials()
            os.environ.setdefault("VERTEX_PROJECT_ID", project)
            return project

    for candidate in _credentials_candidates():
        project_from_file = _project_from_credentials_file(candidate)
        if project_from_file:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(candidate)
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_from_file)
            os.environ.setdefault("VERTEX_PROJECT_ID", project_from_file)
            return project_from_file

    project_from_adc = _project_from_adc()
    if project_from_adc:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_from_adc)
        os.environ.setdefault("VERTEX_PROJECT_ID", project_from_adc)
        return project_from_adc

    raise RuntimeError(
        "Vertex AI is not configured. Set GOOGLE_CLOUD_PROJECT (or VERTEX_PROJECT_ID), "
        "or provide GOOGLE_APPLICATION_CREDENTIALS / keys/credentials.json with project_id."
    )


def resolve_vertex_location(default_location: str = "us-central1") -> str:
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("VERTEX_LOCATION") or default_location
    location = str(location).strip() or default_location

    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)
    os.environ.setdefault("VERTEX_LOCATION", location)

    return location


def configure_vertex_runtime(default_location: str = "us-central1") -> tuple[str, str]:
    project = resolve_vertex_project()
    location = resolve_vertex_location(default_location)

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project)
    os.environ.setdefault("VERTEX_PROJECT_ID", project)
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", location)
    os.environ.setdefault("VERTEX_LOCATION", location)

    return project, location