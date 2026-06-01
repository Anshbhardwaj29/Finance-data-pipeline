import asyncio
import sys
from core.logger import custom_logger as logger
from core.config import settings
from core.broker import DhanAdapter, PaperBroker, BinanceAdapter
from core.engine import TradingEngine
from strategies.sma_crossover import SMACrossoverStrategy
from strategies.high_probability_nifty import HighProbabilityNiftyStrategy
from strategies.base import BaseStrategy

# A dummy strategy to test isolation and verify that crashes do not stop other strategies
class CrashTestStrategy(BaseStrategy):
    def __init__(self):
        super().__init__("Crash_Test_Strategy_11")
        self.tick_counter = 0

    async def process_tick(self, tick: dict) -> int:
        self.tick_counter += 1
        # Deliberately raise an exception every 8th tick to test isolation
        if self.tick_counter % 8 == 0:
            raise ZeroDivisionError("Simulated Strategy Error: Division By Zero for test purposes.")
        return 0

async def main():
    logger.info("Initializing Institutional-Grade Algorithmic Trading Systems...")
    logger.info(f"Execution Mode: {settings.execution_mode}")
    logger.info(f"Active Broker Adapter: {settings.active_broker}")

    # 1. Initialize the appropriate broker adapter based on configurations
    if settings.active_broker == "dhan":
        dhan_token = settings.broker_config.get("dhan", {}).get("api_token", "YOUR_DHAN_TOKEN_HERE")
        broker = DhanAdapter(api_token=dhan_token)
    elif settings.active_broker == "binance":
        binance_cfg = settings.broker_config.get("binance", {})
        symbols = binance_cfg.get("symbols", ["BTCUSDT", "ETHUSDT"])
        broker = BinanceAdapter(symbols=symbols)
    elif settings.active_broker == "paper":
        paper_cfg = settings.broker_config.get("paper", {})
        symbols = paper_cfg.get("symbols", ["RELIANCE"])
        tick_interval = paper_cfg.get("tick_interval_seconds", 0.05)
        broker = PaperBroker(symbols=symbols, tick_interval_seconds=tick_interval)
    else:
        logger.error(f"Unknown active broker configuration: {settings.active_broker}")
        sys.exit(1)

    # 2. Setup Core Trading Engine
    engine = TradingEngine(broker=broker)

    # 3. Dynamically load and register strategies from configuration
    for strat_cfg in settings.strategies_config:
        strat_type = strat_cfg.get("type")
        strat_params = strat_cfg.get("params", {})
        
        if strat_type == "SMA_Crossover":
            strategy = SMACrossoverStrategy(
                short_window=strat_params.get("short_window", 9),
                long_window=strat_params.get("long_window", 21)
            )
            engine.add_strategy(strategy)
        elif strat_type == "High_Probability_Nifty":
            strategy = HighProbabilityNiftyStrategy(
                ema_fast=strat_params.get("ema_fast", 9),
                ema_slow=strat_params.get("ema_slow", 21),
                rsi_period=strat_params.get("rsi_period", 14),
                rsi_buy_min=strat_params.get("rsi_buy_min", 50),
                rsi_sell_max=strat_params.get("rsi_sell_max", 50)
            )
            engine.add_strategy(strategy)
        else:
            logger.warning(f"Unsupported strategy type in configuration: {strat_type}")

    # 4. Inject Crash-Test Strategy (Verification for strict isolation)
    logger.info("Injecting Crash-Test Strategy (11th Strategy) for isolation validation...")
    engine.add_strategy(CrashTestStrategy())

    # 5. Start the Engine Loop
    try:
        await engine.start()
    except KeyboardInterrupt:
        logger.warning("\nShutdown signal received. Stopping trading pipeline...")
    finally:
        # Generate and print final paper trade performance report
        summary = engine.risk_manager.get_portfolio_summary()
        logger.critical("==================================================")
        logger.critical("           TRADING PIPELINE FINAL REPORT          ")
        logger.critical("==================================================")
        logger.critical(f"Initial Capital:   Rs.{summary['initial_balance']:,.2f}")
        logger.critical(f"Current Balance:   Rs.{summary['current_balance']:,.2f}")
        logger.critical(f"Total P&L:         Rs.{summary['total_pnl']:+,.2f}")
        logger.critical(f"Completed Trades:  {summary['total_trades']}")
        logger.critical(f"Win Rate:          {summary['win_rate_pct']:.2f}%")
        logger.critical(f"Open Positions:    {summary['active_positions_count']}")
        logger.critical("==================================================")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass