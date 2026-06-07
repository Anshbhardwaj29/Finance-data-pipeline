import asyncio
import time
import copy
from typing import List
from core.broker import BaseBroker
from strategies.base import BaseStrategy
from core.risk_manager import RiskManager
from core.logger import custom_logger as logger

class TradingEngine:
    def __init__(self, broker: BaseBroker):
        self.broker = broker
        self.strategies: List[BaseStrategy] = []
        self.tick_queue = asyncio.Queue()
        self.is_running = False
        
        # Initialize Risk Manager
        self.risk_manager = RiskManager(broker=self.broker)
        self.risk_manager.engine = self  # Give risk manager access to notifications & logging
        
        # Initialize Excel logging and Notification Alerting systems
        from core.excel_logger import ExcelLogger
        from core.notifier import Notifier
        from core.dashboard import start_dashboard_server
        from core.config import settings

        self.excel_logger = ExcelLogger()
        self.notifier = Notifier()

        # Start the interactive UI dashboard
        if settings.config.get("dashboard", {}).get("enabled", True):
            import os
            port = int(os.environ.get("PORT", settings.config.get("dashboard", {}).get("port", 8050)))
            start_dashboard_server(self, port=port)

    def add_strategy(self, strategy: BaseStrategy):
        self.strategies.append(strategy)
        logger.info(f"Strategy Registered: {strategy.name}")

    async def execute_trade(self, strategy_name: str, symbol: str, action: str, price: float):
        """
        Executes order placement and risk registration in a background task
        to prevent blocking the main tick-processing event loop.
        """
        qty = self.risk_manager.default_qty
        
        # 1. Pre-trade Risk Verification
        if not self.risk_manager.check_order_risk(symbol, action, qty, price):
            return
            
        # 2. Broker Order Routing (simulated or live)
        order_res = await self.broker.place_order(symbol, action, qty, price)
        
        # 3. Post-trade Risk Settlement
        if order_res.get("status") == "SUCCESS":
            await self.risk_manager.register_trade(
                symbol=symbol,
                action=action,
                qty=qty,
                price=order_res.get("price", price),
                order_id=order_res.get("order_id", f"TXN-{int(time.time()*1000)}")
            )

    async def run_strategies(self):
        while self.is_running:
            tick = await self.tick_queue.get()
            
            # 1. Real-time Risk Monitoring: Monitor existing open positions for SL/TP breaches
            await self.risk_manager.monitor_open_positions(tick)
            
            # 2. Strategy Execution:
            # Guarantee data state integrity by feeding copy of tick data
            tasks = [strat.process_tick(copy.deepcopy(tick)) for strat in self.strategies]
            
            # Profile concurrent strategy run execution time
            start_time = time.time()
            
            # return_exceptions=True -> isolated crash-proofing
            signals = await asyncio.gather(*tasks, return_exceptions=True)
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            if elapsed_ms > 1000:
                logger.warning(f"LATENCY ALERT -> Execution took {elapsed_ms:.2f}ms (>1000ms target) for {len(self.strategies)} strategies.")
            else:
                logger.debug(f"Concurrently evaluated {len(self.strategies)} strategies in {elapsed_ms:.3f}ms")

            # 3. Signal Processing:
            for idx, signal in enumerate(signals):
                strat_name = self.strategies[idx].name
                
                if isinstance(signal, Exception):
                    logger.error(f"ISOLATED CRASH in strategy '{strat_name}': {signal}")
                    continue
                    
                if signal == 1:
                    logger.info(f"{strat_name} triggered BUY (ATM Call Option CE) for {tick['symbol']} at Rs.{tick['close']}")
                    # Run trade execution asynchronously in the background
                    asyncio.create_task(self.execute_trade(strat_name, tick['symbol'], "BUY", tick['close']))
                elif signal == -1:
                    logger.info(f"{strat_name} triggered SELL (ATM Put Option PE) for {tick['symbol']} at Rs.{tick['close']}")
                    asyncio.create_task(self.execute_trade(strat_name, tick['symbol'], "SELL", tick['close']))
                    
            self.tick_queue.task_done()

    async def start(self):
        self.is_running = True
        logger.success("PIPELINE STARTED | Waiting for live Nifty 50 ticks...")
        await asyncio.gather(
            self.broker.connect_websocket(self.tick_queue),
            self.run_strategies()
        )