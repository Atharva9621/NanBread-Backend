from core.ingestors.MainIngestor import MainIngestor

mig = MainIngestor(parallel=False)

# Step 1 — get origins from all three sources
origins, url_map = mig.get_origins(
    queries=["iphone 15", "samsung galaxy s23"],
    caps={"reddit": 3, "youtube": 3, "twitter": 3},
)
print("========== ORIGINS ==========")
print(origins)
# [{"idx": "r1", "source": "reddit", "url": "..."}, 
#  {"idx": "y1", "source": "youtube", "url": "..."},
#  {"idx": "t1", "source": "twitter", "url": "..."}, ...]

print("========== URL MAP ==========")
print(url_map)
# {"r1": "https://reddit.com/...", "y1": "https://youtube.com/...", ...}

# Step 2 — get comments (uses internal maps stored during get_origins)
comments = mig.get_comments(origins)
print("========== COMMENTS ==========")
print(comments)
# [{"idx": "r1", "comments": ["...", "..."]},
#  {"idx": "y1", "comments": ["[STUB] ...", ...]},
#  {"idx": "t1", "comments": ["[STUB] ..."]}]