"""
cache.py  →  core/utils/cache.py
---------------------------------
Instantiate AFTER load_dotenv() in app.py so CACHE env var is read correctly.

Usage:
    cache = Cache()
    cached = cache.get_product("iphone 15 pro")   # None if disabled or not found
"""

from core.utils.logger import Logger, Verbosity
log = Logger(name=__name__, verbosity=Verbosity.TRACE)

import json
import os

_CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")

_PRODUCTS = {
    "iphone 15 pro":      "p1",
    "samsung galaxy s24": "p2",
    "sony wh-1000xm5":    "p3",
    "macbook air m3":     "p4",
}


class StaticCache:
    def __init__(self):
        self.enabled = os.environ.get("CACHE", "false").strip().lower() not in ("false", "0", "no")
        self.timeout = 0.1
        log.debug(f"Cache enabled: {self.enabled} with timeout {self.timeout}s")

    def get_product(self, product: str) -> dict | None:
        """
        Returns cached response for a product, or None if:
          - CACHE=false in env
          - product not in _PRODUCTS map
          - file missing, unreadable, or unparseable
        """
        if not self.enabled:
            return None
        pid = _PRODUCTS.get(product.lower().strip())
        log.trace(f"Cache lookup for [cyan]{product}[/cyan] with id [magenta]{pid}[/magenta]")
        if not pid:
            return None

        try:
            with open(os.path.join(_CACHE_DIR, f"{pid}.json"), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Error in Cache lookup for [magenta]{product}[/] with id : {e}")
            return None