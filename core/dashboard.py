import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from core.logger import custom_logger as logger

# Shared engine status reference
engine_instance = None

class DashboardHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Suppress standard noise to keep terminal readable

    def do_GET(self):
        global engine_instance
        
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(self._get_dashboard_html().encode("utf-8"))
            
        elif self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            # Package engine status
            status = {"status": "INACTIVE", "portfolio": {}, "positions": [], "trades": []}
            if engine_instance:
                summary = engine_instance.risk_manager.get_portfolio_summary()
                status = {
                    "status": "RUNNING" if engine_instance.is_running else "STOPPED",
                    "broker": type(engine_instance.broker).__name__,
                    "portfolio": summary,
                    "positions": [
                        {"symbol": k, **v} for k, v in engine_instance.risk_manager.positions.items()
                    ],
                    "trades": list(reversed(engine_instance.risk_manager.trade_history[-15:])) # last 15
                }
            self.wfile.write(json.dumps(status).encode("utf-8"))
            
        elif self.path == "/api/reports":
            import os
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            reports = []
            if os.path.exists("logs"):
                for f in sorted(os.listdir("logs"), reverse=True):
                    if f.endswith(".xlsx") or f == "activity_precise.log":
                        filepath = os.path.join("logs", f)
                        reports.append({
                            "name": f,
                            "size": os.path.getsize(filepath),
                            "modified": os.path.getmtime(filepath)
                        })
            self.wfile.write(json.dumps(reports).encode("utf-8"))
            
        elif self.path.startswith("/download/"):
            import os
            import urllib.parse
            # Prevent directory traversal attacks
            filename = os.path.basename(urllib.parse.unquote(self.path[10:]))
            filepath = os.path.join("logs", filename)
            
            if os.path.exists(filepath) and (filename.endswith(".xlsx") or filename == "activity_precise.log"):
                self.send_response(200)
                if filename.endswith(".xlsx"):
                    self.send_header("Content-type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                else:
                    self.send_header("Content-type", "text/plain; charset=utf-8")
                self.send_header("Content-Disposition", f"attachment; filename={filename}")
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def _get_dashboard_html(self) -> str:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Indian Stock Market Trading Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-color: #0b0d17;
            --glass-bg: rgba(18, 22, 38, 0.65);
            --glass-border: rgba(255, 255, 255, 0.08);
            --accent-glow: rgba(0, 242, 254, 0.15);
            --text-main: #f3f4f6;
            --text-muted: #9ca3af;
            --primary: #00f2fe;
            --primary-glow: rgba(0, 242, 254, 0.4);
            --success: #00e676;
            --danger: #ff1744;
            --warning: #ffb300;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            background-image: 
                radial-gradient(at 0% 0%, rgba(0, 242, 254, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(79, 70, 229, 0.08) 0px, transparent 50%);
            color: var(--text-main);
            min-height: 100vh;
            padding: 2rem;
            overflow-x: hidden;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--glass-border);
            padding-bottom: 1.5rem;
        }

        .header h1 {
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #00f2fe 0%, #4f46e5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0px 4px 12px rgba(0, 242, 254, 0.2);
        }

        .status-badge {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            padding: 0.6rem 1.2rem;
            border-radius: 50px;
            font-size: 0.9rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }

        .badge-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background-color: var(--success);
            box-shadow: 0 0 10px var(--success);
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2.5rem;
        }

        .card {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            backdrop-filter: blur(20px);
            border-radius: 24px;
            padding: 1.5rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
            position: relative;
            overflow: hidden;
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, transparent, var(--primary), transparent);
            opacity: 0;
            transition: opacity 0.3s;
        }

        .card:hover::before {
            opacity: 1;
        }

        .card:hover {
            transform: translateY(-5px);
            border-color: rgba(0, 242, 254, 0.4);
            box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.15);
        }

        .card-title {
            font-size: 0.9rem;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.6rem;
        }

        .card-value {
            font-size: 1.9rem;
            font-weight: 800;
            color: var(--text-main);
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }

        .layout-main {
            display: grid;
            grid-template-columns: 2.2fr 1fr;
            gap: 2rem;
        }

        .panel {
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            backdrop-filter: blur(20px);
            border-radius: 28px;
            padding: 1.8rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
            margin-bottom: 2rem;
        }

        .panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.8rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            padding-bottom: 0.8rem;
        }

        .panel-title {
            font-size: 1.3rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th, td {
            padding: 1.1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            font-size: 0.95rem;
        }

        th {
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            font-size: 0.8rem;
            letter-spacing: 0.5px;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.01);
        }

        .pnl-green {
            color: var(--success);
            font-weight: 700;
            text-shadow: 0 0 10px rgba(0, 230, 118, 0.15);
        }

        .pnl-red {
            color: var(--danger);
            font-weight: 700;
            text-shadow: 0 0 10px rgba(255, 23, 68, 0.15);
        }

        .action-buy {
            background: rgba(0, 230, 118, 0.12);
            color: var(--success);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid rgba(0, 230, 118, 0.2);
        }

        .action-sell {
            background: rgba(255, 23, 68, 0.12);
            color: var(--danger);
            padding: 6px 12px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid rgba(255, 23, 68, 0.2);
        }

        .shield-badge {
            background: rgba(0, 230, 118, 0.15);
            color: var(--success);
            border: 1px solid rgba(0, 230, 118, 0.3);
            border-radius: 6px;
            padding: 2px 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .opt-badge {
            background: rgba(255, 179, 0, 0.15);
            color: var(--warning);
            border: 1px solid rgba(255, 179, 0, 0.3);
            border-radius: 6px;
            padding: 2px 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .pos-card {
            background: rgba(255,255,255,0.01);
            padding: 1.2rem;
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.04);
            margin-bottom: 1.2rem;
            transition: all 0.3s;
        }

        .pos-card:hover {
            border-color: rgba(255, 255, 255, 0.1);
            background: rgba(255,255,255,0.02);
            transform: scale(1.01);
        }

        .badge-trailed {
            background: rgba(0, 230, 118, 0.15);
            color: var(--success);
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: bold;
            display: inline-block;
            margin-top: 5px;
            border: 1px solid rgba(0, 230, 118, 0.3);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>ATM Options Command Desk</h1>
        <div class="status-badge">
            <span class="badge-dot" id="engine-status-dot"></span>
            <span id="engine-status-text">CONNECTING...</span>
        </div>
    </div>

    <!-- Portfolio KPI Widgets -->
    <div class="grid">
        <div class="card">
            <div class="card-title">Trading Balance</div>
            <div class="card-value" id="val-balance">₹0.00</div>
        </div>
        <div class="card">
            <div class="card-title">Total P&L</div>
            <div class="card-value" id="val-pnl">₹0.00</div>
        </div>
        <div class="card">
            <div class="card-title">Completed Trades</div>
            <div class="card-value" id="val-trades">0</div>
        </div>
        <div class="card">
            <div class="card-title">Losses Avoided (BE)</div>
            <div class="card-value" style="color: var(--success);" id="val-saved">0</div>
        </div>
        <div class="card">
            <div class="card-title">Avg Peak Run</div>
            <div class="card-value" style="color: var(--primary);" id="val-peak">0.00 pts</div>
        </div>
    </div>

    <div class="layout-main">
        <div>
            <!-- Parallel RR Optimizer Matrix -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Parallel Risk-Reward (RR) Optimizer Matrix</div>
                    <span class="opt-badge">Real-Time Simulation</span>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>RR Setup</th>
                            <th style="text-align: center;">Unoptimized Win Rate</th>
                            <th style="text-align: right;">Unoptimized P&L</th>
                            <th style="text-align: center;">Optimized Win Rate</th>
                            <th style="text-align: right;">Optimized P&L</th>
                            <th style="text-align: right;">Opt Improvement</th>
                        </tr>
                    </thead>
                    <tbody id="tbl-optimizer-matrix">
                        <tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No metrics loaded yet.</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Performance Graph -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Cumulative Equity Curve</div>
                </div>
                <div style="height: 320px; position: relative;">
                    <canvas id="equityChart"></canvas>
                </div>
            </div>

            <!-- Transaction Audit Trail -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Completed Audit Log</div>
                </div>
                <table id="tbl-history">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Symbol</th>
                            <th>Instrument</th>
                            <th>Qty</th>
                            <th>Index Entry/Exit</th>
                            <th>Premium Entry/Exit</th>
                            <th>P&L</th>
                            <th>Peak Run</th>
                            <th>Exit Reason</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td colspan="9" style="text-align: center; color: var(--text-muted);">No records reported yet.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div>
            <!-- Active Positions Desk -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Open Exposure Limits</div>
                </div>
                <div id="positions-list">
                    <p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">No active open exposures.</p>
                </div>
            </div>

            <!-- Downloadable Reports & Logs Desk -->
            <div class="panel">
                <div class="panel-header">
                    <div class="panel-title">Audit Reports & Logs</div>
                </div>
                <div id="reports-list" style="display: flex; flex-direction: column; gap: 10px;">
                    <p style="color: var(--text-muted); text-align: center; padding: 1rem 0;">Loading reports...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let chart = null;

        function updateMetrics() {
            fetch('/api/status')
                .then(r => r.json())
                .then(data => {
                    // Update header status
                    document.getElementById('engine-status-text').innerText = data.status;
                    const dot = document.getElementById('engine-status-dot');
                    dot.style.backgroundColor = data.status === 'RUNNING' ? 'var(--success)' : 'var(--danger)';
                    dot.style.boxShadow = data.status === 'RUNNING' ? '0 0 12px var(--success)' : '0 0 12px var(--danger)';

                    const port = data.portfolio;
                    if (port) {
                        document.getElementById('val-balance').innerText = '₹' + Number(port.current_balance || 0).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        
                        const pnlVal = port.total_pnl || 0;
                        const pnlCell = document.getElementById('val-pnl');
                        pnlCell.innerText = (pnlVal >= 0 ? '+' : '') + '₹' + pnlVal.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                        pnlCell.className = 'card-value ' + (pnlVal > 0 ? 'pnl-green' : (pnlVal < 0 ? 'pnl-red' : ''));
                        
                        document.getElementById('val-trades').innerText = port.total_trades || 0;
                        document.getElementById('val-saved').innerText = port.total_losses_avoided || 0;
                        document.getElementById('val-peak').innerText = (port.avg_peak_run || 0).toFixed(2) + ' pts';

                        // Render Parallel RR Optimizer Matrix
                        const matrixContainer = document.getElementById('tbl-optimizer-matrix');
                        if (port.rr_performance) {
                            let rowsHtml = '';
                            Object.keys(port.rr_performance).forEach(rr => {
                                const perf = port.rr_performance[rr];
                                const unoptTotal = (perf.unopt_wins + perf.unopt_losses);
                                const unoptWinRate = unoptTotal > 0 ? (perf.unopt_wins / unoptTotal * 100) : 0.0;
                                
                                const optTotal = (perf.opt_wins + perf.opt_losses);
                                const optWinRate = optTotal > 0 ? (perf.opt_wins / optTotal * 100) : 0.0;
                                
                                const optDiff = perf.opt_pnl - perf.unopt_pnl;
                                const diffClass = optDiff > 0 ? 'pnl-green' : (optDiff < 0 ? 'pnl-red' : '');
                                
                                rowsHtml += `
                                    <tr>
                                        <td><strong>RR 1:${rr}</strong></td>
                                        <td style="text-align: center;">${unoptWinRate.toFixed(1)}% (${perf.unopt_wins}/${unoptTotal})</td>
                                        <td style="text-align: right;" class="${perf.unopt_pnl > 0 ? 'pnl-green' : (perf.unopt_pnl < 0 ? 'pnl-red' : '')}">₹${perf.unopt_pnl.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                                        <td style="text-align: center;"><strong>${optWinRate.toFixed(1)}%</strong> (${perf.opt_wins}/${optTotal})</td>
                                        <td style="text-align: right;" class="${perf.opt_pnl > 0 ? 'pnl-green' : (perf.opt_pnl < 0 ? 'pnl-red' : '')}"><strong>₹${perf.opt_pnl.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
                                        <td style="text-align: right;" class="${diffClass}"><strong>₹${(optDiff >= 0 ? '+' : '')}${optDiff.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong></td>
                                    </tr>
                                `;
                            });
                            matrixContainer.innerHTML = rowsHtml;
                        }
                    }

                    // Update Open Exposures
                    const posContainer = document.getElementById('positions-list');
                    if (data.positions && data.positions.length > 0) {
                        posContainer.innerHTML = data.positions.map(p => {
                            const premiumDiff = p.current_premium - p.entry_premium;
                            const premiumClass = premiumDiff > 0 ? 'pnl-green' : (premiumDiff < 0 ? 'pnl-red' : '');
                            return `
                                <div class="pos-card">
                                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 0.6rem;">
                                        <strong style="font-size:1.1rem; letter-spacing:0.5px; color:var(--primary);">${p.instrument}</strong>
                                        <span class="${p.action === 'BUY' ? 'action-buy' : 'action-sell'}">${p.option_type} BUY</span>
                                    </div>
                                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size:0.9rem; color:var(--text-muted); margin-bottom: 5px;">
                                        <div>Qty: <strong style="color:var(--text-main); font-weight:600;">${p.qty}</strong></div>
                                        <div>Index Price: <strong style="color:var(--text-main); font-weight:600;">₹${p.current_price.toFixed(2)}</strong></div>
                                        <div>Entry Prem: <strong style="color:var(--text-main); font-weight:600;">₹${p.entry_premium.toFixed(2)}</strong></div>
                                        <div>Current Prem: <strong class="${premiumClass}" style="font-weight:700;">₹${p.current_premium.toFixed(2)}</strong></div>
                                        <div>Index SL: <strong style="color:var(--danger); font-weight:600;">₹${p.sl.toFixed(2)}</strong></div>
                                        <div>Index TP: <strong style="color:var(--success); font-weight:600;">₹${p.tp.toFixed(2)}</strong></div>
                                    </div>
                                    ${p.sl_trailed ? '<div class="badge-trailed">🛡️ Loss Protected (SL at Break-Even)</div>' : ''}
                                </div>
                            `;
                        }).join('');
                    } else {
                        posContainer.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 2rem 0;">No active open exposures.</p>';
                    }

                    // Update Audit Trail Table
                    const tblBody = document.querySelector('#tbl-history tbody');
                    if (data.trades && data.trades.length > 0) {
                        tblBody.innerHTML = data.trades.map(t => `
                            <tr>
                                <td>${new Date(t.timestamp * 1000).toLocaleTimeString()}</td>
                                <td><strong style="letter-spacing:0.5px;">${t.symbol}</strong></td>
                                <td><span style="color: var(--primary); font-weight: 600;">${t.instrument}</span></td>
                                <td>${t.qty}</td>
                                <td>₹${t.entry_price.toFixed(2)} → ₹${t.exit_price.toFixed(2)}</td>
                                <td>₹${t.entry_premium.toFixed(2)} → ₹${t.exit_premium.toFixed(2)}</td>
                                <td class="${t.pnl > 0 ? 'pnl-green' : 'pnl-red'}">₹${(t.pnl >= 0 ? '+' : '')}${t.pnl.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
                                <td>+${t.peak_run.toFixed(2)} pts</td>
                                <td><span style="font-size:0.85rem; opacity:0.8; font-weight:500;">${t.reason}</span></td>
                            </tr>
                        `).join('');
                        
                        // Update Cumulative Equity Curve
                        let balanceAcc = port.initial_balance || 1000000;
                        const balances = [balanceAcc];
                        const labels = ['Start'];
                        
                        // Sort trades chronologically
                        const sortedTrades = [...data.trades].sort((a,b) => a.timestamp - b.timestamp);
                        sortedTrades.forEach((t, i) => {
                            balanceAcc += t.pnl;
                            balances.push(balanceAcc);
                            labels.push('Trade ' + (i + 1));
                        });
                        
                        updateChart(labels, balances);
                    } else {
                        tblBody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem 0;">No records reported yet.</td></tr>';
                    }
                })
                .catch(err => console.error("Dashboard sync error:", err));
        }

        function updateChart(labels, dataPoints) {
            const ctx = document.getElementById('equityChart').getContext('2d');
            if (chart) {
                chart.data.labels = labels;
                chart.data.datasets[0].data = dataPoints;
                chart.update();
            } else {
                chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Account Equity (₹)',
                            data: dataPoints,
                            borderColor: '#00f2fe',
                            borderWidth: 3,
                            pointBackgroundColor: '#00f2fe',
                            pointHoverRadius: 6,
                            tension: 0.35,
                            fill: true,
                            backgroundColor: function(context) {
                                const chart = context.chart;
                                const {ctx, chartArea} = chart;
                                if (!chartArea) return null;
                                const gradient = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                                gradient.addColorStop(0, 'rgba(0, 242, 254, 0.25)');
                                gradient.addColorStop(1, 'rgba(0, 242, 254, 0.00)');
                                return gradient;
                            }
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: { grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#9ca3af', font: { family: 'Outfit' } } },
                            y: { grid: { color: 'rgba(255,255,255,0.02)' }, ticks: { color: '#9ca3af', font: { family: 'Outfit' } } }
                        }
                    }
                });
            }
        }

        function updateReports() {
            fetch('/api/reports')
                .then(r => r.json())
                .then(files => {
                    const container = document.getElementById('reports-list');
                    if (files && files.length > 0) {
                        container.innerHTML = files.map(f => {
                            const dateStr = new Date(f.modified * 1000).toLocaleString();
                            const sizeKb = (f.size / 1024).toFixed(1);
                            const isExcel = f.name.endsWith('.xlsx');
                            const icon = isExcel ? '📊' : '📝';
                            const titleColor = isExcel ? 'var(--success)' : 'var(--primary)';
                            return `
                                <div style="background: rgba(255,255,255,0.01); padding: 1rem; border-radius: 14px; border: 1px solid rgba(255,255,255,0.04); display: flex; justify-content: space-between; align-items: center; transition: all 0.3s;" onmouseover="this.style.borderColor='rgba(0,242,254,0.2)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.04)'">
                                    <div>
                                        <div style="font-weight: 600; font-size: 0.95rem; color: ${titleColor};">${icon} ${f.name}</div>
                                        <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 3px;">Size: ${sizeKb} KB | Mod: ${dateStr}</div>
                                    </div>
                                    <a href="/download/${encodeURIComponent(f.name)}" download style="background: rgba(0,242,254,0.1); border: 1px solid rgba(0,242,254,0.3); color: var(--primary); padding: 6px 12px; border-radius: 8px; font-size: 0.8rem; font-weight: 600; text-decoration: none; display: inline-block; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.background='var(--primary)'; this.style.color='#000';" onmouseout="this.style.background='rgba(0,242,254,0.1)'; this.style.color='var(--primary)';">Download</a>
                                </div>
                            `;
                        }).join('');
                    } else {
                        container.innerHTML = '<p style="color: var(--text-muted); text-align: center; padding: 1rem 0;">No logs or reports available.</p>';
                    }
                })
                .catch(err => console.error("Reports load error:", err));
        }

        setInterval(updateMetrics, 1000);
        updateMetrics();
        setInterval(updateReports, 5000);
        updateReports();
    </script>
</body>
</html>
"""

def start_dashboard_server(engine, port=8050):
    global engine_instance
    engine_instance = engine
    
    def serve():
        server_address = ("", port)
        try:
            httpd = HTTPServer(server_address, DashboardHTTPHandler)
            logger.success(f"DASHBOARD SERVER STARTED -> Access at http://localhost:{port}")
            httpd.serve_forever()
        except Exception as e:
            logger.error(f"Failed to start dashboard HTTP server: {e}")

    t = threading.Thread(target=serve, daemon=True)
    t.start()
