"""
MainIngestor.py
---------------
Single entry point for all ingestion.
Holds rig, yig, tig and exposes:

    get_origins(queries, caps)  → origins, url_map
    get_comments(origins)       → comments list

Each source runs independently — one failure never blocks others.
Sequential or parallel per source controlled by the `parallel` flag.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed

from core.ingestors.RedditIngestor  import RedditIngestor
from core.ingestors.YoutubeIngestor import YouTubeIngestor
from core.ingestors.TwitterIngestor import TwitterIngestor
from core.ingestors.GoogleSerpIngestor import GoogleSerpIngestor

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

DEFAULT_CAPS = {"reddit": 3, "youtube": 3, "google": 3, "twitter": 3}

class MainIngestor:

    def __init__(
        self,
        reddit_ingestor:  RedditIngestor  = None,
        youtube_ingestor: YouTubeIngestor = None,
        google_ingestor:  GoogleSerpIngestor = None,
        twitter_ingestor: TwitterIngestor = None,
        parallel: bool = False,
    ):
        self.rig = reddit_ingestor  or RedditIngestor()
        self.yig = youtube_ingestor or YouTubeIngestor()
        self.gig = google_ingestor  or GoogleSerpIngestor()
        self.tig = twitter_ingestor or TwitterIngestor()
        self.parallel = parallel

        # internal maps populated during get_origins, consumed in get_comments
        self._permalink_map = {}   # reddit:  {idx → permalink}
        self._video_id_map  = {}   # youtube: {idx → video_id}
        self._product_map   = {}   # google:  {idx → {...}}
        self._tweet_map     = {}   # twitter: {idx → tweet text}

    # ------------------------------------------------------------------
    # get_origins
    # ------------------------------------------------------------------

    def get_origins(
        self,
        queries: list[str],
        caps: dict = DEFAULT_CAPS,
    ) -> tuple[list[dict], dict]:
        """
        Run all three ingestors for the given queries.

        Returns:
            origins: flat list of {"idx", "source", "url"}
            url_map: {"r1": "url", "y1": "url", ...}
        """
        tasks = {
            "reddit":  (self.rig.get_origins, queries, caps.get("reddit",  3)),
            "youtube": (self.yig.get_origins, queries, caps.get("youtube", 3)),
            "google":  (self.gig.get_origins,  queries, caps.get("google",  3)),
            "twitter": (self.tig.get_origins, queries, caps.get("twitter", 3)),
        }

        if self.parallel:
            all_origins = self._run_parallel_origins(tasks)
        else:
            all_origins = self._run_sequential_origins(tasks)

        url_map = {o["idx"]: o["url"] for o in all_origins}
        return all_origins, url_map

    # ------------------------------------------------------------------
    # get_comments
    # ------------------------------------------------------------------

    def get_comments(self, origins: list[dict]) -> list[dict]:
        """
        Fetch comments for each origin using the appropriate ingestor.
        Uses internal maps populated during get_origins.

        Returns:
            [{"idx": "r1", "comments": ["...", ...]}, ...]
        """
        reddit_origins  = [o for o in origins if o["source"] == "reddit"]
        youtube_origins = [o for o in origins if o["source"] == "youtube"]
        google_origins  = [o for o in origins if o["source"] == "google"]
        twitter_origins = [o for o in origins if o["source"] == "twitter"]

        tasks = {
            "reddit":  (self.rig.get_comments, reddit_origins,  self._permalink_map),
            "youtube": (self.yig.get_comments, youtube_origins, self._video_id_map),
            "google":  (self.gig.get_comments,  google_origins,  self._product_map),
            "twitter": (self.tig.get_comments, twitter_origins, self._tweet_map),
        }

        if self.parallel:
            return self._run_parallel_comments(tasks)
        else:
            return self._run_sequential_comments(tasks)

    # ------------------------------------------------------------------
    # Sequential runners
    # ------------------------------------------------------------------

    def _run_sequential_origins(self, tasks: dict) -> list[dict]:
        all_origins = []
        for source, (fn, queries, cap) in tasks.items():
            try:
                origins, internal_map = fn(queries, cap)
                all_origins.extend(origins)
                self._store_internal_map(source, internal_map)
                log.debug(f"{source} → {len(origins)} origins")
            except Exception as exc:
                log.error(f"get_origins failed for {source}: {exc}")
        return all_origins

    def _run_sequential_comments(self, tasks: dict) -> list[dict]:
        all_comments = []
        for source, (fn, origins, internal_map) in tasks.items():
            if not origins:
                continue
            try:
                comments = fn(origins, internal_map)
                all_comments.extend(comments)
                log.debug(f"{source} → {sum(len(c['comments']) for c in comments)} comments")
            except Exception as exc:
                log.error(f"get_comments failed for {source}: {exc}")
        return all_comments

    # ------------------------------------------------------------------
    # Parallel runners
    # ------------------------------------------------------------------

    def _run_parallel_origins(self, tasks: dict) -> list[dict]:
        all_origins = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(fn, queries, cap): source
                for source, (fn, queries, cap) in tasks.items()
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    origins, internal_map = future.result()
                    all_origins.extend(origins)
                    self._store_internal_map(source, internal_map)
                    log.debug(f"{source} → {len(origins)} origins (parallel)")
                except Exception as exc:
                    log.error(f"get_origins failed for {source}: {exc}")
        return all_origins

    def _run_parallel_comments(self, tasks: dict) -> list[dict]:
        all_comments = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {
                pool.submit(fn, origins, internal_map): source
                for source, (fn, origins, internal_map) in tasks.items()
                if origins
            }
            for future in as_completed(futures):
                source = futures[future]
                try:
                    comments = future.result()
                    all_comments.extend(comments)
                    log.debug(f"{source} → {sum(len(c['comments']) for c in comments)} comments (parallel)")
                except Exception as exc:
                    log.error(f"get_comments failed for {source}: {exc}")
        return all_comments

    # ------------------------------------------------------------------
    # Internal map storage
    # ------------------------------------------------------------------

    def _store_internal_map(self, source: str, internal_map: dict):
        if source == "reddit":
            self._permalink_map.update(internal_map)
        elif source == "youtube":
            self._video_id_map.update(internal_map)
        elif source == "twitter":
            self._tweet_map.update(internal_map)