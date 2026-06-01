from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def process_tick(self, tick: Dict[str, Any]) -> int:
        """
        Input: Live market tick data
        Output: 1 (Buy), -1 (Sell), 0 (Hold)
        """
        pass