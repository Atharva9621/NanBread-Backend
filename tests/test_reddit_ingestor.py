from core.ingestors.RedditIngestor import RedditIngestor

rig = RedditIngestor(timeout=10, ratelimit=1.0)
origins, pmap = rig.get_origins(["iphone 15", "samsung galaxy s23"], cap=3)
print("========== ORIGINS ==========")
print(origins)
print("========== PMAP ==========")
print(pmap)

print("========== COMMENTS ==========")
comments = rig.get_comments(origins, pmap)
print(comments)