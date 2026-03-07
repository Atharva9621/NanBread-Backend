def prep_references(url_map: dict[str, str]) -> dict[str, dict]:
    """
    Converts flat url_map to the frontend reference format.

    Input:  {"r1": "https://reddit.com/...", "y1": "https://youtube.com/..."}
    Output: {"r1": {"platform": "reddit", "url": "...", "thread_title": "..."}}

    Platform guessed from idx prefix:
        r → reddit
        y → youtube
        t → twitter
        g → google
    """
    _PLATFORM_MAP = {
        "r": "reddit",
        "y": "youtube",
        "t": "twitter",
        "g": "google",
    }

    references = {}

    for idx, url in url_map.items():
        prefix   = idx[0].lower()
        platform = _PLATFORM_MAP.get(prefix, "unknown")
        title    = _extract_title(url)

        references[idx] = {
            "platform":     platform,
            "url":          url,
            "thread_title": title,
        }

    return references


def _extract_title(url: str) -> str:
    """
    Grabs the last meaningful path segment of a URL as a readable title.
    Strips query params, fragments, and cleans up slugs.

    https://reddit.com/r/android/comments/abc/this_is_the_title/ → "This Is The Title"
    https://youtube.com/watch?v=abc123                           → "abc123"
    https://twitter.com/user/status/123456789                   → "123456789"
    "Best Buy"  (not a URL)                                      → "Best Buy"
    """
    # not a URL — return as-is
    if not url.startswith("http"):
        return url

    # youtube: pull video ID from ?v= param before stripping query string
    if "youtube.com/watch" in url:
        for part in url.split("?")[-1].split("&"):
            if part.startswith("v="):
                return part[2:]

    # strip query string and fragment
    clean = url.split("?")[0].split("#")[0].rstrip("/")

    # grab last non-empty path segment
    parts = [p for p in clean.split("/") if p]
    if not parts:
        return url

    last = parts[-1]

    # skip bare IDs that look like watch?v= was stripped (youtube)
    # in that case the last segment is the video id — fine to return as-is

    # replace slugs (underscores/hyphens) with spaces and title-case
    readable = last.replace("_", " ").replace("-", " ")

    # only title-case if it looks like a slug (has spaces now, not a raw ID)
    if " " in readable:
        return readable.title()

    return readable
