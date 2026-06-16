import time
from typing import Dict, Any, Optional, List
from core.logger import custom_logger as logger

class CandleAggregator:
    def __init__(self, timeframe_seconds: int = 60):
        self.timeframe_seconds = timeframe_seconds
        # Stores current active candle metadata for each symbol:
        # { symbol: { "open": float, "high": float, "low": float, "close": float, "start_time": float } }
        self.current_candles: Dict[str, Dict[str, Any]] = {}
        # Stores history of completed/closed candles for each symbol:
        # { symbol: [close_price1, close_price2, ...] }
        self.candle_history: Dict[str, List[float]] = {}
        logger.info(f"Initialized CandleAggregator with timeframe: {self.timeframe_seconds} seconds.")

    def aggregate(self, tick: Dict[str, Any]) -> Optional[float]:
        """
        Aggregates tick data.
        Returns the closed candle's close price if a candle has just closed,
        otherwise returns None.
        """
        symbol = tick["symbol"]
        price = float(tick["close"])
        timestamp = tick.get("timestamp", time.time())

        # If it's the first tick for this symbol
        if symbol not in self.current_candles:
            # Align candle start time to the timeframe boundary (e.g. minute mark)
            start_time = (timestamp // self.timeframe_seconds) * self.timeframe_seconds
            self.current_candles[symbol] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "start_time": start_time
            }
            if symbol not in self.candle_history:
                self.candle_history[symbol] = []
            return None

        candle = self.current_candles[symbol]
        # Check if the tick falls into a new candle timeframe
        if timestamp >= candle["start_time"] + self.timeframe_seconds:
            # The current candle is closed!
            closed_close = candle["close"]
            
            # Save closed price to history
            self.candle_history[symbol].append(closed_close)
            
            # Limit history to prevent memory leak (keep last 200 candles)
            if len(self.candle_history[symbol]) > 200:
                self.candle_history[symbol].pop(0)

            # Start new candle
            new_start_time = (timestamp // self.timeframe_seconds) * self.timeframe_seconds
            self.current_candles[symbol] = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "start_time": new_start_time
            }
            return closed_close
        else:
            # Update active candle
            candle["high"] = max(candle["high"], price)
            candle["low"] = min(candle["low"], price)
            candle["close"] = price
            return None
