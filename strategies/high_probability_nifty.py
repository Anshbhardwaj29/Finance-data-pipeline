import collections
from typing import Dict, Any
from strategies.base import BaseStrategy
from core.logger import custom_logger as logger

class HighProbabilityNiftyStrategy(BaseStrategy):
    def __init__(self, ema_fast=9, ema_slow=21, rsi_period=14, rsi_buy_min=50, rsi_sell_max=50):
        super().__init__(f"HighProb_EMA_{ema_fast}x{ema_slow}_RSI")
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_buy_min = rsi_buy_min
        self.rsi_sell_max = rsi_sell_max
        
        # Historical prices memory
        self.prices = collections.defaultdict(list)
        self.position = collections.defaultdict(int)

    def _calculate_ema(self, prices_list, period) -> float:
        if len(prices_list) < period:
            return 0.0
        # Calculate standard EMA
        multiplier = 2 / (period + 1)
        ema = prices_list[0]
        for price in prices_list[1:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 2)

    def _calculate_rsi(self, prices_list, period) -> float:
        if len(prices_list) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(len(prices_list) - period, len(prices_list)):
            diff = prices_list[i] - prices_list[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 2)

    async def process_tick(self, tick: Dict[str, Any]) -> int:
        symbol = tick['symbol']
        current_price = tick['close']
        
        history = self.prices[symbol]
        history.append(current_price)
        
        # Max limit memory size
        if len(history) > 100:
            history.pop(0)
            
        required_len = max(self.ema_slow, self.rsi_period + 1)
        if len(history) < required_len:
            return 0
            
        # Calculate EMA values
        ema_fast_curr = self._calculate_ema(history, self.ema_fast)
        ema_slow_curr = self._calculate_ema(history, self.ema_slow)
        
        ema_fast_prev = self._calculate_ema(history[:-1], self.ema_fast)
        ema_slow_prev = self._calculate_ema(history[:-1], self.ema_slow)
        
        # Calculate RSI momentum
        rsi = self._calculate_rsi(history, self.rsi_period)
        
        # 1. Strong Bullish Crossover confirmed with RSI momentum above buy threshold
        if ema_fast_prev <= ema_slow_prev and ema_fast_curr > ema_slow_curr:
            if rsi >= self.rsi_buy_min and self.position[symbol] <= 0:
                self.position[symbol] = 1
                logger.debug(f"{self.name} generated BUY signal for {symbol} | Fast EMA: {ema_fast_curr}, Slow EMA: {ema_slow_curr}, RSI: {rsi}")
                return 1
                
        # 2. Strong Bearish Crossover confirmed with RSI below sell threshold
        elif ema_fast_prev >= ema_slow_prev and ema_fast_curr < ema_slow_curr:
            if rsi <= self.rsi_sell_max and self.position[symbol] >= 0:
                self.position[symbol] = -1
                logger.debug(f"{self.name} generated SELL signal for {symbol} | Fast EMA: {ema_fast_curr}, Slow EMA: {ema_slow_curr}, RSI: {rsi}")
                return -1
                
        return 0
