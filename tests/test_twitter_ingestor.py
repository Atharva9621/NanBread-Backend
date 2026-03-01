from core.ingestors.TwitterIngestor import TwitterIngestor

tig = TwitterIngestor()
origins, pmap = tig.get_origins(["iphone 15", "samsung galaxy s23"], cap=3)
print("========== ORIGINS ==========")
print(origins)
print("========== PMAP ==========")
print(pmap)

print("========== COMMENTS ==========")
comments = tig.get_comments(origins, pmap)
print(comments)