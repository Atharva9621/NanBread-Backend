"""
YouTubeIngestor.py
------------------
get_origins(queries, cap) → [{"idx": "y1", "source": "youtube", "url": "..."}]
get_comments(origins)     → [{"idx": "y1", "comments": ["...", "..."]}]

TODO: wire up YouTube Data API v3
"""

import logging

log = logging.getLogger(__name__)


class YouTubeIngestor:

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_origins(self, queries: list[str], cap: int = 3) -> tuple[list[dict], dict]:
        """
        TODO: call YouTube Data API search.list for each query.

        Returns:
            origins:      [{"idx": "y1", "source": "youtube", "url": "..."}]
            video_id_map: {"y1": "video_id_string"}   (internal, used by get_comments)
        """
        log.debug("YouTubeIngestor.get_origins — returning hardcoded stub")

        stub_origins = [
            {"idx": "y1", "source": "youtube", "url": "https://youtube.com/watch?v=stub_vid_1"},
            {"idx": "y2", "source": "youtube", "url": "https://youtube.com/watch?v=stub_vid_2"},
            {"idx": "y3", "source": "youtube", "url": "https://youtube.com/watch?v=stub_vid_3"},
        ][:cap]

        video_id_map = {o["idx"]: o["url"].split("v=")[-1] for o in stub_origins}

        return stub_origins, video_id_map

    def get_comments(self, origins: list[dict], video_id_map: dict) -> list[dict]:
        """
        TODO: call YouTube Data API commentThreads.list per video.

        Returns:
            [{"idx": "y1", "comments": ["comment text", ...]}, ...]
        """
        log.debug("YouTubeIngestor.get_comments — returning hardcoded stub")

        results = []
        for origin in origins:
            if origin["source"] != "youtube":
                continue
            idx = origin["idx"]
            results.append({
                "idx": idx,
                "comments": [
                    f"[STUB] Great video about this product — {idx}",
                    f"[STUB] Really helpful review, covers all the key points — {idx}",
                    f"[STUB] Camera quality looks amazing in these samples — {idx}",
                ]
            })

        return results