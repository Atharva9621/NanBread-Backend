"""
YouTubeIngestor.py
------------------
get_origins(queries, cap) → [{"idx": "y1", "source": "youtube", "url": "..."}], video_id_map
get_comments(origins, video_id_map) → [{"idx": "y1", "comments": ["...", "..."]}]
"""

import os
import time
import requests
from typing import Optional

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

API_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeIngestor:

    def __init__(self, timeout: int = 10, ratelimit: float = 1.0):
        self.timeout = timeout
        self.ratelimit = ratelimit

        self.api_key = os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise RuntimeError("YOUTUBE_API_KEY environment variable not set")

        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        log.debug("Initialized YouTubeIngestor")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_origins(self, queries: list[str], cap: int = 3) -> tuple[list[dict], dict]:
        """
        Search YouTube for each query, return up to cap unique video origins.

        Returns:
            origins:       [{"idx": "y1", "source": "youtube", "url": "..."}, ...]
            video_id_map:  {"y1": "videoId", ...}
        """
        seen = set()
        origins = []
        idx = 1

        for query in queries:
            if len(origins) >= cap:
                break
            try:
                videos = self._search_videos(query, limit=cap)
                for v in videos:
                    if len(origins) >= cap:
                        break
                    if v["url"] in seen:
                        continue
                    seen.add(v["url"])
                    origins.append({
                        "idx":       f"y{idx}",
                        "source":    "youtube",
                        "url":       v["url"],
                        "_video_id": v["video_id"],
                    })
                    idx += 1
            except Exception as exc:
                log.warning(f"YouTubeIngestor.get_origins failed for {query!r}: {exc}")
                continue

        clean_origins = [{k: v for k, v in o.items() if not k.startswith("_")} for o in origins]
        video_id_map  = {o["idx"]: o["_video_id"] for o in origins}
        return clean_origins, video_id_map

    def get_comments(self, origins: list[dict], video_id_map: dict, max_comments: int = 50) -> list[dict]:
        """
        Fetch flat comment list for each YouTube origin.

        Args:
            origins:       list of origin dicts (idx, source, url)
            video_id_map:  {"y1": "videoId", ...} from get_origins

        Returns:
            [{"idx": "y1", "comments": ["comment text", ...]}, ...]
        """
        results = []

        for origin in origins:
            if origin["source"] != "youtube":
                continue
            idx      = origin["idx"]
            video_id = video_id_map.get(idx)
            if not video_id:
                log.warning(f"No video_id for {idx}, skipping")
                results.append({"idx": idx, "comments": []})
                continue
            try:
                comments = self._fetch_comments(video_id, max_comments)
                results.append({"idx": idx, "comments": comments})
                log.debug(f"  {idx} → {len(comments)} comments")
                time.sleep(self.ratelimit)
            except Exception as exc:
                log.error(f"YouTubeIngestor.get_comments failed for {idx}: {exc}")
                results.append({"idx": idx, "comments": []})

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict) -> Optional[dict]:
        url = f"{API_URL}/{path}"
        attempts = 0
        while attempts < 3:
            attempts += 1
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning(f"network error fetching {url}: {exc}")
                time.sleep(2 ** attempts)
                continue

            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    log.warning(f"malformed json from {url}")
                    return None
            else:
                log.warning(f"{resp.status_code} when GET {url}: {resp.text[:200]}")
                if resp.status_code in (429, 500, 503):
                    time.sleep(2 ** attempts)
                    continue
                return None
        return None

    def _search_videos(self, query: str, limit: int = 5) -> list[dict]:
        params = {
            "part":       "snippet",
            "q":          query,
            "type":       "video",
            "maxResults": limit,
            "key":        self.api_key,
        }
        data = self._get("search", params)
        if not data:
            return []

        results = []
        for item in data.get("items", []):
            vid   = item["id"].get("videoId")
            title = item["snippet"].get("title", "")
            if vid:
                results.append({
                    "video_id": vid,
                    "title":    title,
                    "url":      f"https://www.youtube.com/watch?v={vid}",
                })
        return results[:limit]

    def _fetch_comments(self, video_id: str, max_results: int = 50) -> list[str]:
        comments_raw = []
        params = {
            "part":       "snippet,replies",
            "videoId":    video_id,
            "maxResults": 100,
            "key":        self.api_key,
        }

        while True:
            data = self._get("commentThreads", params)
            if not data:
                break
            comments_raw.extend(data.get("items", []))
            if len(comments_raw) >= max_results or "nextPageToken" not in data:
                break
            params["pageToken"] = data["nextPageToken"]

        comments = []
        for thread in comments_raw[:max_results]:
            top = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            text  = top.get("textDisplay", "").strip()
            likes = top.get("likeCount", 0)
            if len(text) >= 15 and likes >= 1:
                comments.append(text)

            for reply in thread.get("replies", {}).get("comments", []):
                snippet      = reply.get("snippet", {})
                reply_text   = snippet.get("textDisplay", "").strip()
                reply_likes  = snippet.get("likeCount", 0)
                if len(reply_text) >= 15 and reply_likes >= 1:
                    comments.append(reply_text)

        return comments