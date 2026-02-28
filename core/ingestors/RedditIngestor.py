from typing import List
from core.ingestors._base_ingestor import base_ingestor

import requests
import time

BASE_URL = "https://www.reddit.com"
HEADERS = {
    "User-Agent": "Safari/5.0 (compatible; Gwalior/Vidya Prathishtha Mandir Student/1.0)"
}

class RedditIngestor(base_ingestor):

    def __init__(self,
                timeout:int = 10,
                limit:int = 5,
                ratelimit:float = 1.0
            ):
        super().__init__()
        self.timeout = timeout
        self.limit = limit
        self.ratelimit = ratelimit

        self.msg_counter = 1
        self.thread_counter = 1
        self.id_to_thread = {}

        self.log.debug(f"Initialized RedditIngestor")

    def process(self, query: str, limit = 5) -> List[dict]:
        """
        Given a product name,
        returns list of structured reddit threads.
        """
        reddit_threads = self.search_threads(query, limit)
        self.log.debug(f"Found {len(reddit_threads)} threads for query '{query}'")
        self.log.trace(f"Sample URLs: {[t['url'] for t in reddit_threads[:3]]}")

        structured_rthreads = []
        for thread in reddit_threads:
            thread_data = self.fetch_thread(thread["permalink"])
            if not thread_data:
                continue

            parsed = self.parse_thread(thread_data, thread["url"])
            structured_rthreads.append(parsed)

            time.sleep(self.ratelimit)

        self.log.trace(f"Sample Conversation: {structured_rthreads[0] if structured_rthreads else 'No threads parsed'}")
        llm_text = self.format_for_llm(structured_rthreads)

        return {
            "threads": structured_rthreads,
            "id_to_thread": self.id_to_thread,
            "llm_text": llm_text
        }

    #######################################
    # EVERYTHING ELSE WLD BE HELPER FUNCTIONS
    #######################################

    def search_threads(self, query:str, limit:int = 5):
        params = {
            "q": query,
            "sort": "relevance",
            "limit": limit
        }

        r = requests.get(
            f"{BASE_URL}/search.json",
            headers=HEADERS,
            params=params,
            timeout=self.timeout
        )

        data = r.json()

        results = []

        for post in data["data"]["children"]:
            p = post["data"]

            if p["num_comments"] < 10 or p["score"] < 5:
                continue

            results.append({
                "title": p["title"],
                "permalink": p["permalink"],
                "url": BASE_URL + p["permalink"]
            })

        return results[:limit]

    def fetch_thread(self, permalink):
        url = BASE_URL + permalink + ".json"

        try:
            r = requests.get(url, headers=HEADERS, timeout=self.timeout)
            if r.status_code != 200:
                return None
            return r.json()
        except:
            return None

    def parse_thread(self, thread_json, thread_url):
        thread_id = f"T{self.thread_counter}"
        self.thread_counter += 1

        post_data = thread_json[0]["data"]["children"][0]["data"]
        comments_tree = thread_json[1]["data"]["children"]

        messages = []

        for comment in comments_tree:
            if comment["kind"] != "t1":
                continue

            parsed_comment = self.parse_comment(
                comment["data"],
                thread_url
            )

            if parsed_comment:
                messages.append(parsed_comment)

        return {
            "thread_id": thread_id,
            "title": post_data["title"],
            "url": thread_url,
            "messages": messages
        }

    def parse_comment(self, comment_data, thread_url, depth=0, max_depth=2):
        if depth > max_depth:
            return None

        body = comment_data.get("body", "")
        score = comment_data.get("score", 0)

        if (
            body in ["[deleted]", "[removed]"]
            or len(body) < 50
            or score < 3
        ):
            return None

        msg_id = f"M{self.msg_counter}"
        self.msg_counter += 1

        self.id_to_thread[msg_id] = thread_url

        message = {
            "msg_id": msg_id,
            "username": comment_data.get("author", "unknown"),
            "text": body.strip(),
            "replies": []
        }

        replies = comment_data.get("replies")

        if replies and isinstance(replies, dict):
            children = replies["data"]["children"]

            for child in children:
                if child["kind"] == "t1":
                    parsed_reply = self.parse_comment(
                        child["data"],
                        thread_url,
                        depth + 1,
                        max_depth
                    )
                    if parsed_reply:
                        message["replies"].append(parsed_reply)

        return message

    def format_for_llm(self, threads):
        output = []

        for thread in threads:
            output.append(f"\n=== Thread {thread['thread_id']} ===")
            output.append(f"Title: {thread['title']}\n")

            for msg in thread["messages"]:
                self._format_msg(msg, output, indent=0)

        return "\n".join(output)

    def _format_msg(self, msg, output, indent):
        space = "  " * indent
        output.append(
            f"{space}[{msg['msg_id']}] {msg['username']}: {msg['text']}"
        )

        for reply in msg["replies"]:
            self._format_msg(reply, output, indent + 1)