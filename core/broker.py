import asyncio
import time
import random
import json
import threading
import websockets
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime, timedelta
from core.logger import custom_logger as logger
from core.config import settings

class BaseBroker(ABC):
    @abstractmethod
    async def connect_websocket(self, queue: asyncio.Queue): 
        """Connects to the websocket and streams market ticks to the queue."""
        pass
    
    @abstractmethod
    async def place_order(self, symbol: str, action: str, qty: int, price: float) -> Dict[str, Any]: 
        """Places a buy/sell order with the broker."""
        pass

class DhanAdapter(BaseBroker):
    def __init__(self, client_id: str, api_token: str):
        self.client_id = client_id
        self.api_token = api_token
        self.loop = None
        self.queue = None
        self.feed = None
        self.is_running = True

    async def connect_websocket(self, queue: asyncio.Queue):
        logger.info("Connecting to Dhan WebSockets for real market data...")
        self.queue = queue
        self.loop = asyncio.get_running_loop()

        # Check market hours before starting
        if not self._is_market_hours():
            logger.warning("Market is currently CLOSED. Dhan Real-time Feed will sleep until next market open...")
            await self._sleep_until_market_open()
            if not self.is_running:
                return

        # Start DhanHQ MarketFeed in a daemon thread
        threading.Thread(target=self._run_dhan_feed, daemon=True, name="Dhan-MarketFeed").start()

        # Run a monitoring loop in the main asyncio thread to check for market close
        while self.is_running:
            await asyncio.sleep(60)
            if not self._is_market_hours():
                logger.warning("Market closed! Gracefully shutting down the real-time feed.")
                self.is_running = False
                if self.feed:
                    try:
                        self.feed.disconnect()  # Disconnect the websocket
                    except Exception as e:
                        logger.error(f"Error disconnecting Dhan Feed: {e}")
                # Stop the entire engine loop gracefully
                import os
                import signal
                os.kill(os.getpid(), signal.SIGINT)

    def _run_dhan_feed(self):
        try:
            from dhanhq import dhanhq, MarketFeed
            
            dhan_context = dhanhq(self.client_id, self.api_token)
            
            # Subscribing to NIFTY 50 (13) and BANK NIFTY (14) Index tickers
            instruments = [
                (MarketFeed.IDX_I, "13", MarketFeed.Ticker),
                (MarketFeed.IDX_I, "14", MarketFeed.Ticker)
            ]
            
            self.feed = MarketFeed(dhan_context, instruments)
            
            def on_connect(instance):
                logger.success("Dhan Real-time WebSocket Feed connected successfully!")
                
            def on_message(instance, message):
                try:
                    if not message or not isinstance(message, dict):
                        return
                    
                    sec_id = str(message.get("security_id"))
                    ltp = message.get("ltp")
                    
                    if not sec_id or ltp is None:
                        return
                        
                    symbol = "NIFTY50" if sec_id == "13" else "BANKNIFTY" if sec_id == "14" else None
                    if not symbol:
                        return
                        
                    tick_data = {
                        "timestamp": time.time(),
                        "symbol": symbol,
                        "close": float(ltp)
                    }
                    
                    # Feed it thread-safely into the asyncio queue
                    self.loop.call_soon_threadsafe(self.queue.put_nowait, tick_data)
                    
                except Exception as e:
                    logger.error(f"Error parsing Dhan websocket message: {e}")

            self.feed.on_connect = on_connect
            self.feed.on_message = on_message
            
            self.feed.run_forever()
            
        except Exception as e:
            logger.error(f"Dhan MarketFeed thread failed: {e}")

    def _is_market_hours(self) -> bool:
        """Checks if current time is within Indian market hours (09:15 - 15:30 IST, Mon-Fri)."""
        # IST is UTC+5:30
        now_utc = datetime.utcnow()
        now_ist = now_utc + timedelta(hours=5, minutes=30)
        
        # Weekday check: Mon=0, Fri=4
        if now_ist.weekday() > 4:
            return False
            
        market_start = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        market_end = now_ist.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_start <= now_ist <= market_end

    async def _sleep_until_market_open(self):
        """Calculates duration until next market open and sleeps."""
        while self.is_running and not self._is_market_hours():
            await asyncio.sleep(10) # check every 10 seconds

    async def place_order(self, symbol: str, action: str, qty: int, price: float) -> Dict[str, Any]:
        # Since execution_mode is PAPER, this DhanAdapter will just log the paper trade!
        start_time = time.time()
        logger.warning(f"ROUTING ORDER (PAPER/MOCK DHAN) -> {action} | {symbol} | Qty: {qty} | Price: {price}")
        await asyncio.sleep(0.02)
        latency = (time.time() - start_time) * 1000
        
        return {
            "status": "SUCCESS",
            "order_id": f"DHN-PPR-{int(time.time()*1000)}",
            "price": price,
            "qty": qty,
            "timestamp": time.time()
        }

class PaperBroker(BaseBroker):
    def __init__(self, symbols: List[str], tick_interval_seconds: float = 0.05):
        self.symbols = symbols
        self.tick_interval_seconds = tick_interval_seconds
        
        initial_prices = {
            "RELIANCE": 2900.0,
            "HDFCBANK": 1550.0,
            "INFY": 1450.0,
            "TCS": 3850.0,
            "ICICIBANK": 1150.0,
            "BHARTIARTL": 1250.0,
            "SBIN": 800.0,
            "LICI": 950.0,
            "ITC": 430.0,
            "LT": 3500.0,
            "NIFTY50": 22500.0,
            "BANKNIFTY": 48000.0
        }
        
        self.price_track = {
            sym: initial_prices.get(sym, random.uniform(100, 1000))
            for sym in self.symbols
        }

    async def connect_websocket(self, queue: asyncio.Queue):
        logger.info(f"Paper Trading WebSocket initialized for {len(self.symbols)} Nifty 50 symbols. Streaming simulated ticks...")
        
        while True:
            await asyncio.sleep(self.tick_interval_seconds)
            sym = random.choice(self.symbols)
            
            drift_percent = random.uniform(-0.0002, 0.0002)
            drift = self.price_track[sym] * drift_percent
            self.price_track[sym] = round(self.price_track[sym] + drift, 2)
            
            tick_data = {
                "timestamp": time.time(),
                "symbol": sym,
                "close": self.price_track[sym],
            }
            await queue.put(tick_data)

    async def place_order(self, symbol: str, action: str, qty: int, price: float) -> Dict[str, Any]:
        start_time = time.time()
        logger.warning(f"ROUTING ORDER (PAPER) -> {action} | {symbol} | Qty: {qty} | Price: {price}")
        
        simulated_latency = random.uniform(0.01, 0.025)
        await asyncio.sleep(simulated_latency)
        
        latency_ms = (time.time() - start_time) * 1000
        order_id = f"PPR-{int(time.time()*1000)}"
        
        fill_price = self.price_track.get(symbol, price)
        logger.success(f"ORDER FILLED (PAPER) -> ID: {order_id} | Price: {fill_price} | Latency: {latency_ms:.2f}ms")
        
        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "price": fill_price,
            "qty": qty,
            "timestamp": time.time()
        }

class BinanceAdapter(BaseBroker):
    def __init__(self, symbols: List[str]):
        self.symbols = [sym.upper() for sym in symbols]
        self.price_track = {}

    async def connect_websocket(self, queue: asyncio.Queue):
        logger.info(f"Binance Public WebSockets Connection Initialized for {self.symbols}. Streaming Live Data...")
        
        streams = "/".join([f"{sym.lower()}@ticker" for sym in self.symbols])
        url = f"wss://stream.binance.com:9443/ws/{streams}"
        
        while True:
            try:
                async with websockets.connect(url) as websocket:
                    logger.success("Successfully connected to Binance WebSocket!")
                    async for message in websocket:
                        data = json.loads(message)
                        symbol = data.get("s")
                        close_price = float(data.get("c", 0.0))
                        
                        self.price_track[symbol] = close_price
                        
                        tick_data = {
                            "timestamp": time.time(),
                            "symbol": symbol,
                            "close": close_price,
                        }
                        await queue.put(tick_data)
            except Exception as e:
                logger.error(f"Binance WebSocket encountered error: {e}. Reconnecting in 5 seconds...")
                await asyncio.sleep(5)

    async def place_order(self, symbol: str, action: str, qty: int, price: float) -> Dict[str, Any]:
        start_time = time.time()
        logger.warning(f"ROUTING ORDER (BINANCE MOCK) -> {action} | {symbol} | Qty: {qty} | Price: {price}")
        
        await asyncio.sleep(0.02)
        latency = (time.time() - start_time) * 1000
        
        order_id = f"BIN-{int(time.time()*1000)}"
        fill_price = self.price_track.get(symbol, price)
        
        logger.success(f"ORDER FILLED (BINANCE MOCK) -> ID: {order_id} | Price: {fill_price} | Latency: {latency:.2f}ms")
        return {
            "status": "SUCCESS",
            "order_id": order_id,
            "price": fill_price,
            "qty": qty,
            "timestamp": time.time()
        }