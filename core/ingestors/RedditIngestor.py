"""
RedditIngestor.py
-----------------
get_origins(queries, cap) → [{"idx": "r1", "source": "reddit", "url": "..."}]
get_comments(origins)     → [{"idx": "r1", "comments": ["...", "..."]}]
"""

import time
import requests

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

BASE_URL = "https://www.reddit.com"
HEADERS  = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class RedditIngestor:

    def __init__(self, timeout: int = 10, ratelimit: float = 1.0):
        self.timeout   = timeout
        self.ratelimit = ratelimit

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_origins(self, queries: list[str], cap: int = 3) -> list[dict]:
        """
        Search reddit for each query, return up to cap unique thread origins.

        Returns:
            [{"idx": "r1", "source": "reddit", "url": "https://reddit.com/r/..."}, ...]
        """
        seen = set()
        origins = []
        idx = 1

        for query in queries:
            if len(origins) >= cap:
                break
            try:
                threads = self._search_threads(query, limit=cap)
                for t in threads:
                    if len(origins) >= cap:
                        break
                    if t["url"] in seen:
                        continue
                    seen.add(t["url"])
                    origins.append({
                        "idx":    f"r{idx}",
                        "source": "reddit",
                        "url":    t["url"],
                        "_permalink": t["permalink"],   # internal, stripped before returning
                    })
                    idx += 1
            except Exception as exc:
                log.warning(f"RedditIngestor.get_origins failed for {query!r}: {exc}")
                continue

        # strip internal keys before returning
        return [{k: v for k, v in o.items() if not k.startswith("_")} for o in origins], \
               {o["idx"]: o["_permalink"] for o in origins}

    def get_comments(self, origins: list[dict], permalink_map: dict) -> list[dict]:
        """
        Fetch flat comment list for each reddit origin.

        Args:
            origins:       list of origin dicts (idx, source, url)
            permalink_map: {"r1": "/r/sub/comments/...", ...} from get_origins

        Returns:
            [{"idx": "r1", "comments": ["comment text", ...]}, ...]
        """
        results = []

        for origin in origins:
            if origin["source"] != "reddit":
                continue
            idx       = origin["idx"]
            permalink = permalink_map.get(idx)
            if not permalink:
                log.warning(f"No permalink for {idx}, skipping")
                results.append({"idx": idx, "comments": []})
                continue
            try:
                comments = self._fetch_comments(permalink)
                results.append({"idx": idx, "comments": comments})
                log.debug(f"  {idx} → {len(comments)} comments")
                time.sleep(self.ratelimit)
            except Exception as exc:
                log.error(f"RedditIngestor.get_comments failed for {idx}: {exc}")
                results.append({"idx": idx, "comments": []})

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _search_threads(self, query: str, limit: int = 5) -> list[dict]:
        params = {"q": query, "sort": "relevance", "limit": limit}
        r = requests.get(
            f"{BASE_URL}/search.json",
            headers=HEADERS,
            params=params,
            timeout=self.timeout,
        )
        r.raise_for_status()
        results = []
        for post in r.json()["data"]["children"]:
            p = post["data"]
            if p["num_comments"] < 10 or p["score"] < 5:
                continue
            results.append({
                "url":       BASE_URL + p["permalink"],
                "permalink": p["permalink"],
            })
        return results[:limit]

    def _fetch_comments(self, permalink: str) -> list[str]:
        url = BASE_URL + permalink.rstrip("/") + ".json?limit=100&sort=top"
        r = requests.get(url, headers=HEADERS, timeout=self.timeout)
        if r.status_code != 200:
            return []

        data = r.json()
        comments = []

        # OP body
        try:
            op = data[0]["data"]["children"][0]["data"]
            body = op.get("selftext", "").strip()
            if body and body not in ("[removed]", "[deleted]") and len(body) > 50:
                comments.append(body)
        except Exception:
            pass

        # top-level comments
        try:
            for child in data[1]["data"]["children"]:
                if child.get("kind") != "t1":
                    continue
                self._extract_comment(child["data"], comments)
        except Exception:
            pass

        return comments

    def _extract_comment(self, comment_data: dict, out: list, depth: int = 0, max_depth: int = 2):
        if depth > max_depth:
            return
        body  = comment_data.get("body", "").strip()
        score = comment_data.get("score", 0)
        if body and body not in ("[removed]", "[deleted]") and len(body) >= 50 and score >= 3:
            out.append(body)
        replies = comment_data.get("replies")
        if replies and isinstance(replies, dict):
            for child in replies["data"]["children"]:
                if child.get("kind") == "t1":
                    self._extract_comment(child["data"], out, depth + 1, max_depth)