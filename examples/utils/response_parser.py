import re
import json


# --- Parse Web Search ---
def web_search_parser(final_output):
    match = re.search(r"```(?:json)?\s*(.*?)```", final_output, re.DOTALL)
    if match:
        cleaned = match.group(1).strip()
    else:
        cleaned = final_output.strip()

    candidates = json.loads(cleaned)

    return candidates
