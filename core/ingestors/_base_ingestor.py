from abc import ABC, abstractmethod
from typing import List
from core.utils.logger import Logger

import requests

class base_ingestor(ABC):

    log = Logger("base_ingestor")

    def __init__(self):
        pass

    @abstractmethod
    def process(self, query: str) -> List[dict]:
        """
        Given a product query,
        returns list of structured documents.
        """
        pass
        