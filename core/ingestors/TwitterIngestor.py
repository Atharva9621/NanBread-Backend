import os
import logging
from typing import List, Dict, Tuple
from apify_client import ApifyClient

from dotenv import load_dotenv
load_dotenv()

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

class TwitterIngestor:

    def __init__(self, use_hardcoded: bool = True):
        self.use_hardcoded = use_hardcoded
        self.actor_id = "61RPP7dywgiy0JPD0"

        if not self.use_hardcoded:
            token = os.getenv("APIFY")
            if not token:
                raise ValueError("APIFY not found in environment")

            self.client = ApifyClient(token)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_origins(self, queries: List[str], cap: int = 3):

        if self.use_hardcoded:
            return self._get_stub(cap)

        search_query = " OR ".join(queries)

        run_input = {
            "searchTerms": [search_query],
            "maxItems": cap,
            "sort": "Latest",
            "tweetLanguage": "en",
        }

        run = self.client.actor(self.actor_id).call(run_input=run_input)

        dataset_id = run["defaultDatasetId"]

        origins = []
        content_map = {}

        for i, item in enumerate(self.client.dataset(dataset_id).iterate_items()):
            idx = f"t{i+1}"

            url = item.get("url")
            text = item.get("text")

            if not url or not text:
                continue

            origins.append({
                "idx": idx,
                "source": "twitter",
                "url": url
            })

            content_map[idx] = text

        return origins, content_map
    
    def get_comments(self, origins: List[Dict], content_map: Dict) -> List[Dict]:
        """
        Tweet text itself is the comment.
        """

        results = []
        for origin in origins:
            if origin["source"] != "twitter":
                continue

            idx = origin["idx"]
            text = content_map.get(idx)

            results.append({
                "idx": idx,
                "comments": [text] if text else []
            })

        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_stub(self, cap: int) -> Tuple[List[Dict], Dict]:
        stub_tweets = [
            {
                "idx": "t1",
                "url": "https://twitter.com/user/status/111",
                "text": "[STUB] Battery life on this phone is absolutely terrible after the update."
            },
            {
                "idx": "t2",
                "url": "https://twitter.com/user/status/222",
                "text": "[STUB] Just picked this up — camera blows everything else out of the water."
            },
            {
                "idx": "t3",
                "url": "https://twitter.com/user/status/333",
                "text": "[STUB] Overheating issues are real. Not happy with this purchase."
            },
        ][:cap]

        origins = [
            {"idx": t["idx"], "source": "twitter", "url": t["url"]}
            for t in stub_tweets
        ]

        content_map = {t["idx"]: t["text"] for t in stub_tweets}

        return origins, content_map