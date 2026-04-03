import json
import re


def extract_json(content: str):
    """
    Extracts JSON array/object from LLM output safely.
    """

    if not content:
        return None

    # Try direct parse first
    try:
        return json.loads(content)
    except Exception:
        pass

    # Extract JSON block using regex
    match = re.search(r"(\[.*\]|\{.*\})", content, re.DOTALL)

    if match:
        json_str = match.group(0)

        try:
            return json.loads(json_str)
        except Exception:
            print("❌ JSON extraction failed after regex")

    print("❌ No valid JSON found")
    return None