import collections
import time
from typing import Dict, Any
from strategies.base import BaseStrategy
from core.logger import custom_logger as logger
from core.candle_aggregator import CandleAggregator
from datetime import datetime, timezone, timedelta

class AxisHDFCMultiTierStrategy(BaseStrategy):
    def __init__(self, ema_filter_len=50, st_period=10, st_multiplier=2.5, timeframe_seconds=60):
        super().__init__("Axis_HDFC_MultiTier_V4")
        self.ema_filter_len = ema_filter_len
        self.st_period = st_period
        self.st_multiplier = st_multiplier
        self.timeframe_seconds = timeframe_seconds
        
        self.aggregator = CandleAggregator(timeframe_seconds=timeframe_seconds)
        self.states = {} # symbol -> {"entry_price": float, "current_sl": float, "max_points_gained": float}

    def _calculate_ema(self, prices, period):
        if len(prices) < period:
            return 0.0
        sma = sum(prices[:period]) / period
        ema = sma
        multiplier = 2.0 / (period + 1.0)
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        return round(ema, 2)

    def _calculate_supertrend_series(self, ohlc_list, period, multiplier):
        n = len(ohlc_list)
        if n < period:
            return [0.0] * n, [0] * n
            
        tr = []
        for i in range(n):
            high = ohlc_list[i]['high']
            low = ohlc_list[i]['low']
            if i == 0:
                tr.append(high - low)
            else:
                prev_close = ohlc_list[i-1]['close']
                tr.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
                
        atr = [0.0] * n
        sum_tr = sum(tr[:period])
        atr[period - 1] = sum_tr / period
        for i in range(period, n):
            atr[i] = (atr[i-1] * (period - 1) + tr[i]) / period
            
        basic_upper = [0.0] * n
        basic_lower = [0.0] * n
        for i in range(n):
            hl2 = (ohlc_list[i]['high'] + ohlc_list[i]['low']) / 2.0
            basic_upper[i] = hl2 + multiplier * atr[i]
            basic_lower[i] = hl2 - multiplier * atr[i]
            
        final_upper = [0.0] * n
        final_lower = [0.0] * n
        supertrend = [0.0] * n
        direction = [1] * n
        
        final_upper[period - 1] = basic_upper[period - 1]
        final_lower[period - 1] = basic_lower[period - 1]
        supertrend[period - 1] = basic_upper[period - 1]
        direction[period - 1] = 1
        
        for i in range(period, n):
            prev_close = ohlc_list[i-1]['close']
            
            if basic_upper[i] < final_upper[i-1] or prev_close > final_upper[i-1]:
                final_upper[i] = basic_upper[i]
            else:
                final_upper[i] = final_upper[i-1]
                
            if basic_lower[i] > final_lower[i-1] or prev_close < final_lower[i-1]:
                final_lower[i] = basic_lower[i]
            else:
                final_lower[i] = final_lower[i-1]
                
            if direction[i-1] == 1:
                if ohlc_list[i]['close'] > final_upper[i]:
                    direction[i] = -1
                    supertrend[i] = final_lower[i]
                else:
                    direction[i] = 1
                    supertrend[i] = final_upper[i]
            else:
                if ohlc_list[i]['close'] < final_lower[i]:
                    direction[i] = 1
                    supertrend[i] = final_upper[i]
                else:
                    direction[i] = -1
                    supertrend[i] = final_lower[i]
                    
        return supertrend, direction

    async def process_tick(self, tick: Dict[str, Any]) -> int:
        symbol = tick['symbol']
        
        # 1. Handle Active Position Trailing Logic first
        pos = None
        if hasattr(self, 'engine'):
            pos = self.engine.risk_manager.positions.get(symbol)
            
        # Convert timestamp to IST
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        dt_ist = datetime.fromtimestamp(tick['timestamp'], ist_tz)
        
        # Intraday Square Off check
        from core.config import settings
        is_paper_broker = settings.config.get("active_broker") == "paper"
        if is_paper_broker:
            is_square_off_time = False
        else:
            is_square_off_time = (dt_ist.hour == 15 and dt_ist.minute >= 15) or (dt_ist.hour > 15)
        
        if pos is not None:
            if is_square_off_time:
                logger.warning(f"SQUARE OFF TIME REACHED -> Forcing Exit for {symbol}")
                pos["force_exit"] = True
                pos["reason"] = "INTRADAY CLOSE"
                return 0
                
            # If in position, verify state initialization
            if symbol not in self.states:
                self.states[symbol] = {
                    "entry_price": pos["entry_price"],
                    "current_sl": pos["sl"],
                    "max_points_gained": 0.0
                }
        else:
            # Not in trade, clear state
            if symbol in self.states:
                del self.states[symbol]
                
        # 2. Aggregate tick
        closed_close = self.aggregator.aggregate(tick)
        if closed_close is None:
            return 0
            
        history = self.aggregator.candle_history[symbol]
        ohlc_history = self.aggregator.ohlc_history[symbol]
        
        required_len = max(self.ema_filter_len, self.st_period + 1)
        if len(history) < required_len or len(ohlc_history) < required_len:
            return 0
            
        # Calculate Indicators
        ema_filter = self._calculate_ema(history, self.ema_filter_len)
        st_series, dir_series = self._calculate_supertrend_series(ohlc_history, self.st_period, self.st_multiplier)
        
        st_curr, dir_curr = st_series[-1], dir_series[-1]
        st_prev, dir_prev = st_series[-2], dir_series[-2]
        
        # Update trailing SL if in position based on the newly closed candle
        if pos is not None and symbol in self.states:
            state = self.states[symbol]
            entry_price = state["entry_price"]
            max_points_gained = state["max_points_gained"]
            completed_candle = ohlc_history[-1]
            action = pos["action"]
            
            if action == "SELL":
                points_gained = entry_price - completed_candle['low']
                if points_gained > max_points_gained:
                    max_points_gained = points_gained
                    state["max_points_gained"] = max_points_gained
                    
                current_sl = state["current_sl"]
                
                # Multi-Tier Short
                if max_points_gained >= 15.3:
                    current_sl = entry_price - 0.5
                if max_points_gained >= 20.4:
                    current_sl = entry_price - 5.1
                if max_points_gained >= 25.5:
                    current_sl = entry_price - 10.2
                if max_points_gained >= 30.6:
                    current_sl = entry_price - 12.75
                if max_points_gained >= 35.7:
                    current_sl = entry_price - 15.3
                if max_points_gained >= 40.8:
                    current_sl = entry_price - 17.85
                if max_points_gained >= 45.9:
                    current_sl = entry_price - 20.4
                if max_points_gained >= 51.0:
                    current_sl = entry_price - 23.46
                if max_points_gained > 51.0:
                    excess = max_points_gained - 51.0
                    steps = int(excess // 12.2)
                    if steps > 0:
                        current_sl = (entry_price - 23.46) - (steps * 5.1)
                        
                state["current_sl"] = current_sl
                pos["sl"] = current_sl
                logger.info(f"Updated Trailing SL for Short {symbol} to {current_sl} (Max Points Gained: {max_points_gained:.2f})")
                
            else: # BUY (Long)
                points_gained = completed_candle['high'] - entry_price
                if points_gained > max_points_gained:
                    max_points_gained = points_gained
                    state["max_points_gained"] = max_points_gained
                    
                current_sl = state["current_sl"]
                
                # Multi-Tier Long
                if max_points_gained >= 15.3:
                    current_sl = entry_price + 0.5
                if max_points_gained >= 20.4:
                    current_sl = entry_price + 5.1
                if max_points_gained >= 25.5:
                    current_sl = entry_price + 10.2
                if max_points_gained >= 30.6:
                    current_sl = entry_price + 12.75
                if max_points_gained >= 35.7:
                    current_sl = entry_price + 15.3
                if max_points_gained >= 40.8:
                    current_sl = entry_price + 17.85
                if max_points_gained >= 45.9:
                    current_sl = entry_price + 20.4
                if max_points_gained >= 51.0:
                    current_sl = entry_price + 23.46
                if max_points_gained > 51.0:
                    excess = max_points_gained - 51.0
                    steps = int(excess // 12.2)
                    if steps > 0:
                        current_sl = (entry_price + 23.46) + (steps * 5.1)
                        
                state["current_sl"] = current_sl
                pos["sl"] = current_sl
                logger.info(f"Updated Trailing SL for Long {symbol} to {current_sl} (Max Points Gained: {max_points_gained:.2f})")

        # 3. Check Session Window for entries (bypass if paper broker for testing)
        if is_paper_broker:
            in_session = True
        else:
            if dt_ist.weekday() > 4:
                in_session = False
            else:
                minute_of_day = dt_ist.hour * 60 + dt_ist.minute
                in_session = 560 <= minute_of_day <= 885
            
        if not in_session:
            return 0
            
        trend_changed = dir_curr != dir_prev
        is_bullish_trend = dir_curr < 0
        is_bearish_trend = dir_curr > 0
        
        long_condition = (closed_close > ema_filter) and is_bullish_trend and trend_changed
        short_condition = (closed_close < ema_filter) and is_bearish_trend and trend_changed
        
        if long_condition and pos is None:
            logger.success(f"{self.name} BUY Signal for {symbol} at {closed_close} (Supertrend: {st_curr:.2f})")
            return 1
            
        if short_condition and pos is None:
            logger.success(f"{self.name} SELL Signal for {symbol} at {closed_close} (Supertrend: {st_curr:.2f})")
            return -1
            
        return 0
