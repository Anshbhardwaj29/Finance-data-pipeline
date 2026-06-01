import asyncio
import time
import random
import json
import websockets
from abc import ABC, abstractmethod
from typing import Dict, Any, List
from core.logger import custom_logger as logger

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
    def __init__(self, api_token: str):
        self.api_token = api_token

    async def connect_websocket(self, queue: asyncio.Queue):
        logger.info("Dhan WebSockets Connection Initialized. Streaming Live Data...")
        symbols = ["RELIANCE", "HDFCBANK"]
        
        # Mocking live ticks
        price_track = {"RELIANCE": 2900.0, "HDFCBANK": 1550.0}
        while True:
            await asyncio.sleep(0.05)  # 50ms tick interval
            sym = random.choice(symbols)
            price_track[sym] += random.uniform(-2, 2) 
            
            tick_data = {
                "timestamp": time.time(),
                "symbol": sym,
                "close": round(price_track[sym], 2),
            }
            await queue.put(tick_data)

    async def place_order(self, symbol: str, action: str, qty: int, price: float) -> Dict[str, Any]:
        start_time = time.time()
        logger.warning(f"ROUTING ORDER -> Platform: Dhan | {action} | {symbol} | Qty: {qty} | Price: {price}")
        await asyncio.sleep(0.03) # Simulating API latency
        latency = (time.time() - start_time) * 1000
        logger.success(f"ORDER EXECUTED -> ID: DHN-{int(time.time()*1000)} | Latency: {latency:.2f}ms")
        return {
            "status": "SUCCESS",
            "order_id": f"DHN-{int(time.time()*1000)}",
            "price": price,
            "qty": qty,
            "timestamp": time.time()
        }

class PaperBroker(BaseBroker):
    def __init__(self, symbols: List[str], tick_interval_seconds: float = 0.05):
        self.symbols = symbols
        self.tick_interval_seconds = tick_interval_seconds
        
        # Real-world Indian Market initial price mappings for Nifty 50 constituents
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
        
        # Initialize price tracker with default or custom Nifty 50 stock values
        self.price_track = {
            sym: initial_prices.get(sym, random.uniform(100, 1000))
            for sym in self.symbols
        }

    async def connect_websocket(self, queue: asyncio.Queue):
        logger.info(f"Paper Trading WebSocket initialized for {len(self.symbols)} Nifty 50 symbols. Streaming simulated ticks...")
        
        while True:
            await asyncio.sleep(self.tick_interval_seconds)
            # Pick a random Nifty 50 symbol to tick
            sym = random.choice(self.symbols)
            
            # Simulate high-speed Indian market price fluctuation (up to 0.02% per tick)
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
        
        # Simulate slight network latency (e.g. 10ms - 25ms)
        simulated_latency = random.uniform(0.01, 0.025)
        await asyncio.sleep(simulated_latency)
        
        latency_ms = (time.time() - start_time) * 1000
        order_id = f"PPR-{int(time.time()*1000)}"
        
        # Use current tracked simulated price as the filled price to avoid mismatch
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
        
        # Binance multi-stream URL format: /ws/btcusdt@ticker/ethusdt@ticker
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
        
        # Simulate local network latency of 20ms
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