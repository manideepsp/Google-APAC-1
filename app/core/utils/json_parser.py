import json
import re


def extract_json(content: str):
    """
    Extracts JSON array/object from LLM output safely.
    """

    if not content:
        return None

    # Strip common markdown fences when models wrap JSON in ```json blocks.
    normalized = content.strip()
    if normalized.startswith("```"):
        normalized = re.sub(r"^```(?:json)?\s*", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s*```$", "", normalized)

    # Try direct parse first
    try:
        return json.loads(normalized)
    except Exception:
        pass

    # Extract JSON block using regex
    match = re.search(r"(\[.*\]|\{.*\})", normalized, re.DOTALL)

    if match:
        json_str = match.group(0)

        try:
            return json.loads(json_str)
        except Exception:
            return None

    return None