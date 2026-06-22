"""Optional Google Custom Search JSON API client."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# TODO: remove this module once Google search is implemented
GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"
GOOGLE_CSE_ID_ENV = "GOOGLE_CSE_ID"
GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

# TODO: remove this error once Google search is implemented
class GoogleSearchConfigError(ValueError):
    """Raised when Google search credentials are missing or invalid."""

# TODO: remove this function once Google search is implemented
def get_google_search_config() -> tuple[str, str]:
    """Return (api_key, cse_id) or raise with a clear message."""
    api_key = os.environ.get(GOOGLE_API_KEY_ENV, "").strip()
    cse_id = os.environ.get(GOOGLE_CSE_ID_ENV, "").strip()

    missing = []
    if not api_key:
        missing.append(GOOGLE_API_KEY_ENV)
    if not cse_id:
        missing.append(GOOGLE_CSE_ID_ENV)

    if missing:
        joined = ", ".join(missing)
        raise GoogleSearchConfigError(
            f"Missing required environment variable(s): {joined}. "
            "Set them to run a live Google JSON search, or use --dry-run / --fixture."
        )

    return api_key, cse_id


# TODO: remove this function once Google search is implemented
def google_search_configured() -> bool:
    try:
        get_google_search_config()
    except GoogleSearchConfigError:
        return False
    return True


# TODO: remove this function once Google search is implemented
def fetch_google_search(
    query: str,
    *,
    api_key: str,
    cse_id: str,
    num: int = 10,
) -> dict:
    """Execute one Google Custom Search JSON API request."""
    params = urllib.parse.urlencode(
        {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": min(max(num, 1), 10),
        }
    )
    url = f"{GOOGLE_SEARCH_ENDPOINT}?{params}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google search request failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Google search request failed: {exc.reason}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Google search response must be a JSON object")

    return payload


# TODO: remove this function once Google search is implemented
def load_google_search_fixture(path: str) -> dict:
    """Load a saved Google Custom Search JSON API response."""
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Google search fixture must be a JSON object")
    return payload
