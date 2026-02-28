from typing import List
from core.ingestors._base_ingestor import base_ingestor

class YoutubeIngestor(base_ingestor):
    
    def __init__(self,
            timeout:int = 10,
            limit:int = 5,
            ratelimit:float = 1.0
        ):
        super().__init__()

    def process(self, query: str, limit = 5) -> List[dict]:
        """
        Given a product name,
        returns list of structured youtube comments.
        """
        pass

    #######################################
    # EVERYTHING ELSE WLD BE HELPER FUNCTIONS
    #######################################