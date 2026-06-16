import collections
from typing import Dict, Any
from strategies.base import BaseStrategy
from core.candle_aggregator import CandleAggregator
from core.logger import custom_logger as logger

class SMACrossoverStrategy(BaseStrategy):
    def __init__(self, short_window=9, long_window=21, timeframe_seconds=60):
        super().__init__(f"SMA_Crossover_{short_window}x{long_window}")
        self.short_window = short_window
        self.long_window = long_window
        
        self.aggregator = CandleAggregator(timeframe_seconds=timeframe_seconds)
        self.position = collections.defaultdict(int) # 0: none, 1: long, -1: short

    async def process_tick(self, tick: Dict[str, Any]) -> int:
        symbol = tick['symbol']
        
        # Aggregate tick into candle
        closed_close = self.aggregator.aggregate(tick)
        if closed_close is None:
            return 0  # Wait for candle to close
            
        history = self.aggregator.candle_history[symbol]
        
        # Jab tak long_window + 1 candles ka data nahi aata, tab tak wait karo
        if len(history) < self.long_window + 1:
            return 0
            
        # Calculate Moving Averages (Pichle data aur current data ka)
        short_sma_current = sum(history[-self.short_window:]) / self.short_window
        long_sma_current = sum(history[-self.long_window:]) / self.long_window
        
        short_sma_prev = sum(history[-(self.short_window+1):-1]) / self.short_window
        long_sma_prev = sum(history[-(self.long_window+1):-1]) / self.long_window

        # Logic for BUY: Short crosses Long from below
        if short_sma_prev <= long_sma_prev and short_sma_current > long_sma_current:
            if self.position[symbol] <= 0:
                self.position[symbol] = 1
                logger.success(f"{self.name} generated BUY signal for {symbol} on closed candle | Price: {closed_close} | Short SMA: {short_sma_current:.2f}, Long SMA: {long_sma_current:.2f}")
                return 1 # BUY Signal
                
        # Logic for SELL: Short crosses Long from above
        elif short_sma_prev >= long_sma_prev and short_sma_current < long_sma_current:
            if self.position[symbol] >= 0:
                self.position[symbol] = -1
                logger.success(f"{self.name} generated SELL signal for {symbol} on closed candle | Price: {closed_close} | Short SMA: {short_sma_current:.2f}, Long SMA: {long_sma_current:.2f}")
                return -1 # SELL Signal
                
        return 0 # HOLD