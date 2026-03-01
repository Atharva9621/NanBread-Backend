"""
GoogleSerpIngestor.py
---------------------
get_origins(queries, cap) → [{"idx": "g1", "source": "google", "url": "..."}], product_map
get_comments(origins, product_map) → [{"idx": "g1", "comments": ["...", "..."]}]
"""

import os
import time
import requests
from typing import Optional

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

SEARCH_URL = "https://serpapi.com/search.json"


class GoogleSerpIngestor:

    def __init__(self, timeout: int = 10, ratelimit: float = 1.0):
        self.timeout   = timeout
        self.ratelimit = ratelimit

        self.api_key = os.environ.get("SERPAPI_KEY")
        if not self.api_key:
            raise RuntimeError("SERPAPI_KEY environment variable not set")

        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        log.debug("Initialized GoogleSerpIngestor")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_origins(self, queries: list[str], cap: int = 3) -> tuple[list[dict], dict]:
        """
        Search Google Shopping for each query, return up to cap unique product origins.

        Returns:
            origins:      [{"idx": "g1", "source": "google", "url": "..."}, ...]
            product_map:  {"g1": {"title": "...", "reviews": [...]}, ...}
        """
        seen = set()
        origins = []
        idx = 1

        for query in queries:
            if len(origins) >= cap:
                break
            try:
                products = self._search_products(query, limit=cap)
                for p in products:
                    if len(origins) >= cap:
                        break
                    url = p.get("url") or p.get("title", "")
                    if url in seen:
                        continue
                    seen.add(url)
                    origins.append({
                        "idx":       f"g{idx}",
                        "source":    "google",
                        "url":       url,
                        "_title":    p.get("title", ""),
                        "_reviews":  p.get("reviews", []),
                    })
                    idx += 1
            except Exception as exc:
                log.warning(f"GoogleSerpIngestor.get_origins failed for {query!r}: {exc}")
                continue

        clean_origins = [{k: v for k, v in o.items() if not k.startswith("_")} for o in origins]
        product_map   = {o["idx"]: {"title": o["_title"], "reviews": o["_reviews"]} for o in origins}
        return clean_origins, product_map

    def get_comments(self, origins: list[dict], product_map: dict, max_reviews: int = 50) -> list[dict]:
        """
        Extract reviews for each Google Shopping origin.

        Args:
            origins:     list of origin dicts (idx, source, url)
            product_map: {"g1": {"title": "...", "reviews": [...]}, ...} from get_origins

        Returns:
            [{"idx": "g1", "comments": ["review text", ...]}, ...]
        """
        results = []

        for origin in origins:
            if origin["source"] != "google":
                continue
            idx     = origin["idx"]
            product = product_map.get(idx)
            if not product:
                log.warning(f"No product data for {idx}, skipping")
                results.append({"idx": idx, "comments": []})
                continue
            try:
                comments = self._extract_reviews(product["reviews"], max_reviews)
                results.append({"idx": idx, "comments": comments})
                log.debug(f"  {idx} → {len(comments)} reviews")
                time.sleep(self.ratelimit)
            except Exception as exc:
                log.error(f"GoogleSerpIngestor.get_comments failed for {idx}: {exc}")
                results.append({"idx": idx, "comments": []})

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get(self, params: dict) -> Optional[dict]:
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                resp = self.session.get(SEARCH_URL, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning(f"network error fetching serpapi: {exc}")
                time.sleep(2 ** attempts)
                continue

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    log.warning("malformed json from serpapi")
                    return None
            else:
                log.warning(f"{resp.status_code} from serpapi: {resp.text[:200]}")
                if resp.status_code in (429, 500, 503):
                    time.sleep(2 ** attempts)
                    continue
                return None
        return None

    def _search_products(self, query: str, limit: int = 5) -> list[dict]:
        params = {
            "engine":  "google",
            "q":       query,
            "tbm":     "shop",
            "num":     limit,
            "api_key": self.api_key,
        }
        data = self._get(params)
        if not data:
            return []

        results = []
        for item in data.get("shopping_results", [])[:limit]:
            results.append({
                "title":   item.get("title") or item.get("product_title") or item.get("name", ""),
                "url":     item.get("link") or item.get("product_url") or item.get("source", ""),
                "reviews": item.get("reviews") or item.get("reviews_data") or [],
            })
        return results

    def _extract_reviews(self, reviews_json: list, max_reviews: int = 50) -> list[str]:
        comments = []
        for rev in reviews_json[:max_reviews]:
            text = rev.get("snippet") or rev.get("text") or rev.get("review") or ""
            text = text.strip()
            if len(text) >= 15:
                comments.append(text)
        return comments