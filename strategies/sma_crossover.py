import collections
from typing import Dict, Any
from strategies.base import BaseStrategy

class SMACrossoverStrategy(BaseStrategy):
    def __init__(self, short_window=9, long_window=21):
        super().__init__(f"SMA_Crossover_{short_window}x{long_window}")
        self.short_window = short_window
        self.long_window = long_window
        
        # Alag-alag stocks ke prices ko yaad rakhne ke liye memory dictionary
        self.prices = collections.defaultdict(lambda: collections.deque(maxlen=long_window + 1))
        self.position = collections.defaultdict(int) # 0: none, 1: long, -1: short

    async def process_tick(self, tick: Dict[str, Any]) -> int:
        symbol = tick['symbol']
        current_price = tick['close']
        
        # Price ko list me add karo
        history = self.prices[symbol]
        history.append(current_price)
        
        # Jab tak 21 ticks ka data nahi aata, tab tak wait karo
        if len(history) < self.long_window + 1:
            return 0
            
        # Calculate Moving Averages (Pichle data aur current data ka)
        short_sma_current = sum(list(history)[-self.short_window:]) / self.short_window
        long_sma_current = sum(list(history)[-self.long_window:]) / self.long_window
        
        short_sma_prev = sum(list(history)[-(self.short_window+1):-1]) / self.short_window
        long_sma_prev = sum(list(history)[-(self.long_window+1):-1]) / self.long_window

        # Logic for BUY: Short crosses Long from below
        if short_sma_prev <= long_sma_prev and short_sma_current > long_sma_current:
            if self.position[symbol] <= 0:
                self.position[symbol] = 1
                return 1 # BUY Signal
                
        # Logic for SELL: Short crosses Long from above
        elif short_sma_prev >= long_sma_prev and short_sma_current < long_sma_current:
            if self.position[symbol] >= 0:
                self.position[symbol] = -1
                return -1 # SELL Signal
                
        return 0 # HOLD