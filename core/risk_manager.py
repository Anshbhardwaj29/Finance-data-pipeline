import time
from typing import Dict, Any, List, Optional
from core.logger import custom_logger as logger
from core.config import settings

class RiskManager:
    def __init__(self, broker):
        self.broker = broker
        
        # Load risk parameters from config
        risk_cfg = settings.risk_config
        self.rr_ratio = risk_cfg.get("risk_reward_ratio", 2.0)
        self.risk_pct = risk_cfg.get("risk_percentage_per_trade", 0.01)
        self.default_qty = risk_cfg.get("default_qty", 10)
        
        # Load paper trading settings
        paper_cfg = settings.broker_config.get("paper", {})
        self.balance = paper_cfg.get("initial_capital", 1000000.0)
        self.initial_balance = self.balance

        # Track active positions
        # Schema: { symbol: { "action": "BUY"/"SELL", "qty": int, "entry_price": float, "highest_price": float, "lowest_price": float, ... } }
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict[str, Any]] = []

        # Parallel RR Simulator (Ratios 1:2, 1:3, 1:4, 1:5)
        # Tracks unoptimized vs optimized (Break-even trailing SL)
        self.rr_performance = {
            2: {"unopt_pnl": 0.0, "unopt_wins": 0, "unopt_losses": 0, "opt_pnl": 0.0, "opt_wins": 0, "opt_losses": 0},
            3: {"unopt_pnl": 0.0, "unopt_wins": 0, "unopt_losses": 0, "opt_pnl": 0.0, "opt_wins": 0, "opt_losses": 0},
            4: {"unopt_pnl": 0.0, "unopt_wins": 0, "unopt_losses": 0, "opt_pnl": 0.0, "opt_wins": 0, "opt_losses": 0},
            5: {"unopt_pnl": 0.0, "unopt_wins": 0, "unopt_losses": 0, "opt_pnl": 0.0, "opt_wins": 0, "opt_losses": 0}
        }
        
        # Active Parallel Trackers
        self.active_rr_trackers: Dict[str, Dict[str, Any]] = {}
        
        # Loss Optimization Metrics
        self.total_losses_avoided = 0
        self.total_peak_runs: List[float] = []

    def check_order_risk(self, symbol: str, action: str, qty: int, price: float) -> bool:
        """
        Enforce pre-trade checks.
        Ensures we have enough capital to enter the position.
        """
        # Option Premium calculation at entry
        entry_premium = round(price * 0.01, 2)
        cost = entry_premium * qty
        if action == "BUY" and self.balance < cost:
            logger.warning(f"RISK REJECT -> Insufficient funds for {symbol} Option BUY. Required: Rs.{cost:.2f}, Available: Rs.{self.balance:.2f}")
            return False
        
        # Check if we already have an active position on this symbol to prevent over-leveraging
        if symbol in self.positions:
            logger.info(f"RISK LIMIT -> Position already exists for {symbol}. Skipping order.")
            return False
            
        return True

    def calculate_sl_tp(self, action: str, entry_price: float) -> tuple:
        """
        Calculates Risk-to-Reward SL and TP boundaries based on index price.
        If risk_pct is 1%, SL is at 1% loss, TP is at 2% gain (for 1:2 RR).
        """
        risk_points = entry_price * self.risk_pct
        if action == "BUY":
            sl = round(entry_price - risk_points, 2)
            tp = round(entry_price + (risk_points * self.rr_ratio), 2)
        else: # SELL (Short)
            sl = round(entry_price + risk_points, 2)
            tp = round(entry_price - (risk_points * self.rr_ratio), 2)
        return sl, tp

    async def register_trade(self, symbol: str, action: str, qty: int, price: float, order_id: str):
        """Records trade and updates portfolio state using ATM Option BUY model."""
        sl, tp = self.calculate_sl_tp(action, price)
        
        # 1. ATM Strike Price rounding
        if "BANKNIFTY" in symbol:
            strike_interval = 100
        elif "NIFTY" in symbol:
            strike_interval = 50
        else:
            strike_interval = 10
        
        strike = int(round(price / strike_interval) * strike_interval)
        option_type = "CE" if action == "BUY" else "PE"
        instrument_name = f"{symbol} {strike} {option_type}"
        
        # 2. Estimate entry premium (1% of index price)
        entry_premium = round(price * 0.01, 2)
        cost = entry_premium * qty
        
        # Adjust virtual balance for purchase cost (simulated options buy)
        self.balance -= cost
        
        self.positions[symbol] = {
            "order_id": order_id,
            "action": action, # BUY index -> buy Call, SELL index -> buy Put
            "qty": qty,
            "entry_price": price,
            "highest_price": price,
            "lowest_price": price,
            "strike": strike,
            "option_type": option_type,
            "instrument": instrument_name,
            "entry_premium": entry_premium,
            "current_premium": entry_premium,
            "sl": sl,
            "tp": tp,
            "sl_trailed": False, # Trail to breakeven status
            "timestamp": time.time()
        }
        
        logger.info(f"RISK REGISTERED -> Option BUY: {instrument_name} | Premium: Rs.{entry_premium} | Index Entry: Rs.{price} | Index SL: {sl} | Index TP: {tp} | Balance: Rs.{self.balance:.2f}")

        # Initialize Parallel RR Trackers for this signal
        risk_points = price * self.risk_pct
        states = {}
        for RR in [2, 3, 4, 5]:
            if action == "BUY":
                unopt_sl = price - risk_points
                unopt_tp = price + RR * risk_points
            else:
                unopt_sl = price + risk_points
                unopt_tp = price - RR * risk_points
            
            states[RR] = {
                "unopt_sl": unopt_sl,
                "unopt_tp": unopt_tp,
                "unopt_active": True,
                "opt_sl": unopt_sl,
                "opt_tp": unopt_tp,
                "opt_active": True,
                "opt_sl_trailed": False
            }
            
        self.active_rr_trackers[symbol] = {
            "action": action,
            "entry_price": price,
            "entry_premium": entry_premium,
            "qty": qty,
            "risk_points": risk_points,
            "states": states
        }

        # Send real-time notification alert on entry
        if hasattr(self, 'engine'):
            self.engine.notifier.send_alert(
                f"🟢 *OPTION POSITION OPENED* 🟢\n"
                f"Instrument: {instrument_name}\n"
                f"Index Price: ₹{price:.2f}\n"
                f"Premium Cost: ₹{entry_premium:.2f}\n"
                f"Qty: {qty}\n"
                f"SL: ₹{sl:.2f} | TP: ₹{tp:.2f}"
            )

    async def monitor_open_positions(self, tick: Dict[str, Any]):
        """
        Monitors live price ticks.
        Calculates Option Premium adjustments using Delta=0.5.
        Applies Loss Optimization (Break-Even stop trailing) and tracks parallel RRs.
        """
        symbol = tick['symbol']
        current_price = tick['close']
        
        # 1. Update Parallel Virtual RR Trackers
        if symbol in self.active_rr_trackers:
            tracker = self.active_rr_trackers[symbol]
            entry_price = tracker["entry_price"]
            entry_premium = tracker["entry_premium"]
            qty = tracker["qty"]
            action = tracker["action"]
            risk_points = tracker["risk_points"]
            
            active_count = 0
            for RR, state in tracker["states"].items():
                # --- Unoptimized RR check ---
                if state["unopt_active"]:
                    active_count += 1
                    unopt_sl = state["unopt_sl"]
                    unopt_tp = state["unopt_tp"]
                    
                    unopt_exit_reason = ""
                    unopt_exit_price = 0.0
                    
                    if action == "BUY":
                        if current_price <= unopt_sl:
                            unopt_exit_reason = "SL"
                            unopt_exit_price = unopt_sl
                        elif current_price >= unopt_tp:
                            unopt_exit_reason = "TP"
                            unopt_exit_price = unopt_tp
                    else: # SELL
                        if current_price >= unopt_sl:
                            unopt_exit_reason = "SL"
                            unopt_exit_price = unopt_sl
                        elif current_price <= unopt_tp:
                            unopt_exit_reason = "TP"
                            unopt_exit_price = unopt_tp
                            
                    if unopt_exit_reason:
                        state["unopt_active"] = False
                        # Calculate Option premium at exit
                        p_dir = 1 if action == "BUY" else -1
                        exit_premium = max(1.0, entry_premium + 0.5 * (unopt_exit_price - entry_price) * p_dir)
                        pnl = round((exit_premium - entry_premium) * qty, 2)
                        
                        if unopt_exit_reason == "TP":
                            self.rr_performance[RR]["unopt_wins"] += 1
                        else:
                            self.rr_performance[RR]["unopt_losses"] += 1
                        self.rr_performance[RR]["unopt_pnl"] += pnl
                        logger.info(f"PARALLEL TRACKER -> {symbol} Unoptimized RR 1:{RR} closed on {unopt_exit_reason}. Premium P&L: Rs.{pnl:+.2f}")
                
                # --- Optimized RR check (Break-even Trailing) ---
                if state["opt_active"]:
                    active_count += 1
                    opt_sl = state["opt_sl"]
                    opt_tp = state["opt_tp"]
                    
                    # Trailing Trigger: If price moves 50% towards target, move stop to entry (break-even)
                    if not state["opt_sl_trailed"]:
                        target_dist = abs(opt_tp - entry_price)
                        current_dist = (current_price - entry_price) if action == "BUY" else (entry_price - current_price)
                        if current_dist >= 0.5 * target_dist:
                            state["opt_sl"] = entry_price
                            state["opt_sl_trailed"] = True
                            logger.success(f"PARALLEL OPTIMIZER -> {symbol} RR 1:{RR} moved SL to Break-Even (Rs.{entry_price})")
                    
                    opt_exit_reason = ""
                    opt_exit_price = 0.0
                    
                    if action == "BUY":
                        if current_price <= opt_sl:
                            opt_exit_reason = "SL"
                            opt_exit_price = opt_sl
                        elif current_price >= opt_tp:
                            opt_exit_reason = "TP"
                            opt_exit_price = opt_tp
                    else: # SELL
                        if current_price >= opt_sl:
                            opt_exit_reason = "SL"
                            opt_exit_price = opt_sl
                        elif current_price <= opt_tp:
                            opt_exit_reason = "TP"
                            opt_exit_price = opt_tp
                            
                    if opt_exit_reason:
                        state["opt_active"] = False
                        p_dir = 1 if action == "BUY" else -1
                        exit_premium = max(1.0, entry_premium + 0.5 * (opt_exit_price - entry_price) * p_dir)
                        pnl = round((exit_premium - entry_premium) * qty, 2)
                        
                        # Check if we saved a loss
                        if opt_exit_reason == "SL" and state["opt_sl_trailed"]:
                            # Hit break-even instead of full loss!
                            self.total_losses_avoided += 1
                            logger.info(f"PARALLEL OPTIMIZER SUCCESS -> Saved potential loss for {symbol} RR 1:{RR} (Exited at Break-Even).")
                        
                        if pnl >= 0:
                            self.rr_performance[RR]["opt_wins"] += 1
                        else:
                            self.rr_performance[RR]["opt_losses"] += 1
                        self.rr_performance[RR]["opt_pnl"] += pnl
                        logger.info(f"PARALLEL TRACKER -> {symbol} Optimized RR 1:{RR} closed on {opt_exit_reason}. Premium P&L: Rs.{pnl:+.2f}")
            
            # Clean up trackers when all setups have completed
            if active_count == 0:
                del self.active_rr_trackers[symbol]

        # 2. Update Live Active Position
        if symbol not in self.positions:
            return
            
        pos = self.positions[symbol]
        action = pos["action"]
        qty = pos["qty"]
        entry_price = pos["entry_price"]
        entry_premium = pos["entry_premium"]
        sl = pos["sl"]
        tp = pos["tp"]
        option_type = pos["option_type"]
        instrument = pos["instrument"]
        
        # Keep track of highest / lowest index prices reached during trade
        pos["highest_price"] = max(pos.get("highest_price", current_price), current_price)
        pos["lowest_price"] = min(pos.get("lowest_price", current_price), current_price)
        
        # Calculate Simulated Option Premium (Delta = 0.5 ATM)
        p_dir = 1 if option_type == "CE" else -1
        current_premium = round(max(1.0, entry_premium + 0.5 * (current_price - entry_price) * p_dir), 2)
        pos["current_premium"] = current_premium
        
        # --- Live Loss Optimization ---
        # Break-Even: If price goes halfway to TP, move SL to entry index price
        if not pos["sl_trailed"]:
            target_dist = abs(tp - entry_price)
            current_dist = (current_price - entry_price) if action == "BUY" else (entry_price - current_price)
            if current_dist >= 0.5 * target_dist:
                pos["sl"] = entry_price
                pos["sl_trailed"] = True
                sl = entry_price
                logger.success(f"LOSS OPTIMIZER -> {instrument} price moved 50% to target. Stop Loss trailed to entry (Break-Even: Rs.{entry_price}) to protect premium!")

        triggered_exit = False
        exit_reason = ""
        
        if action == "BUY":
            if current_price <= sl:
                triggered_exit = True
                exit_reason = "STOP LOSS TRIGGERED" if not pos["sl_trailed"] else "BREAK-EVEN STOP TRIGGERED"
            elif current_price >= tp:
                triggered_exit = True
                exit_reason = "TAKE PROFIT TRIGGERED"
        else: # SELL
            if current_price >= sl:
                triggered_exit = True
                exit_reason = "STOP LOSS TRIGGERED" if not pos["sl_trailed"] else "BREAK-EVEN STOP TRIGGERED"
            elif current_price <= tp:
                triggered_exit = True
                exit_reason = "TAKE PROFIT TRIGGERED"
                
        if triggered_exit:
            exit_action = "SELL" if action == "BUY" else "BUY"
            
            # Calculate final Option P&L
            pnl = round((current_premium - entry_premium) * qty, 2)
            
            logger.critical(f"RISK ALERT -> {instrument} {exit_reason} | Premium: Rs.{current_premium} (Entry: Rs.{entry_premium}) | P&L: Rs.{pnl:+.2f}")
            
            # Place exit order with the broker (simulated or live)
            exit_order = await self.broker.place_order(symbol, exit_action, qty, current_price)
            
            if exit_order.get("status") == "SUCCESS":
                # Credit the simulated options sale premium proceeds back to balance
                self.balance += current_premium * qty
                
                # Calculate Peak points run (MFE)
                peak_run = round((pos["highest_price"] - entry_price) if action == "BUY" else (entry_price - pos["lowest_price"]), 2)
                self.total_peak_runs.append(peak_run)
                
                # Clean up position
                del self.positions[symbol]
                
                # Log to history
                trade_data = {
                    "symbol": symbol,
                    "instrument": instrument,
                    "action": action,
                    "qty": qty,
                    "entry_price": entry_price,
                    "exit_price": current_price,
                    "entry_premium": entry_premium,
                    "exit_premium": current_premium,
                    "pnl": pnl,
                    "peak_run": peak_run,
                    "reason": exit_reason,
                    "timestamp": time.time()
                }
                self.trade_history.append(trade_data)
                
                logger.success(f"OPTION POSITION CLOSED -> {instrument} P&L: Rs.{pnl:+.2f} | Peak Points Run: {peak_run} | Balance: Rs.{self.balance:.2f}")

                # Excel logging and Notification Alert
                if hasattr(self, 'engine'):
                    self.engine.excel_logger.log_trade(trade_data, self.get_portfolio_summary())
                    self.engine.notifier.send_alert(
                        f"🔴 *OPTION POSITION CLOSED* 🔴\n"
                        f"Instrument: {instrument}\n"
                        f"Index Entry/Exit: ₹{entry_price:.2f} / ₹{current_price:.2f}\n"
                        f"Premium Entry/Exit: ₹{entry_premium:.2f} / ₹{current_premium:.2f}\n"
                        f"P&L: ₹{pnl:+.2f} ({exit_reason})\n"
                        f"Peak Index Points Run: +{peak_run:.2f} pts"
                    )

    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Calculates current portfolio metrics."""
        total_pnl = sum(t["pnl"] for t in self.trade_history)
        win_trades = sum(1 for t in self.trade_history if t["pnl"] > 0)
        total_trades = len(self.trade_history)
        win_rate = (win_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        avg_peak_run = round(sum(self.total_peak_runs) / len(self.total_peak_runs), 2) if self.total_peak_runs else 0.0
        
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.balance,
            "total_pnl": total_pnl,
            "win_rate_pct": win_rate,
            "total_trades": total_trades,
            "active_positions_count": len(self.positions),
            "rr_performance": self.rr_performance,
            "total_losses_avoided": self.total_losses_avoided,
            "avg_peak_run": avg_peak_run
        }
