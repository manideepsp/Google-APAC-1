from dataclasses import dataclass

from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

from app.core.vertex_runtime import configure_vertex_runtime

load_dotenv(override=False)


_DEFAULT_MODEL = "gemini-2.5-flash"
_DEFAULT_LOCATION = "us-central1"


def _init_vertex_ai() -> None:
    project, location = configure_vertex_runtime(default_location=_DEFAULT_LOCATION)
    vertexai.init(project=project, location=location)


def _extract_text(response) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    chunks: list[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            part_text = getattr(part, "text", None)
            if part_text:
                chunks.append(part_text)

    return "\n".join(chunks).strip()


@dataclass
class VertexLLMResponse:
    text: str

    @property
    def content(self) -> str:
        return self.text


class VertexLLM:
    def __init__(self, *, model: str, temperature: float):
        self._model = GenerativeModel(model)
        self._generation_config = GenerationConfig(temperature=temperature)

    def invoke(self, prompt: str) -> VertexLLMResponse:
        response = self._model.generate_content(prompt, generation_config=self._generation_config)
        return VertexLLMResponse(text=_extract_text(response))


def get_llm():
    _init_vertex_ai()
    return VertexLLM(model=_DEFAULT_MODEL, temperature=0.3)