import os
import time
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from core.logger import custom_logger as logger

class ExcelLogger:
    def __init__(self, output_dir="logs"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        
    def _get_daily_filepath(self):
        date_str = time.strftime("%Y-%m-%d")
        return os.path.join(self.output_dir, f"trading_report_{date_str}.xlsx")

    def log_trade(self, trade_data: dict, portfolio_summary: dict):
        """Appends trade transaction and current portfolio state into formatted Excel."""
        file_path = self._get_daily_filepath()
        
        # Prepare trade dataframe row
        trade_row = {
            "Time": time.strftime("%H:%M:%S", time.localtime(trade_data.get("timestamp", time.time()))),
            "Symbol": trade_data.get("symbol"),
            "Instrument": trade_data.get("instrument", "N/A"),
            "Action": trade_data.get("action"),
            "Qty": trade_data.get("qty"),
            "Entry Index": round(trade_data.get("entry_price", 0.0), 2),
            "Exit Index": round(trade_data.get("exit_price", 0.0), 2),
            "Entry Premium": round(trade_data.get("entry_premium", 0.0), 2),
            "Exit Premium": round(trade_data.get("exit_premium", 0.0), 2),
            "P&L": round(trade_data.get("pnl", 0.0), 2),
            "Peak Run (Pts)": round(trade_data.get("peak_run", 0.0), 2),
            "Reason": trade_data.get("reason", "STRATEGY EXIT"),
            "Account Balance": round(portfolio_summary.get("current_balance", 0.0), 2)
        }
        
        df_new = pd.DataFrame([trade_row])
        
        # Read or create Excel
        if os.path.exists(file_path):
            try:
                # Load existing data
                df_existing = pd.read_excel(file_path, sheet_name="Trades")
                df_combined = pd.concat([df_existing, df_new], ignore_index=True)
                with pd.ExcelWriter(file_path, engine="openpyxl", mode="w") as writer:
                    df_combined.to_excel(writer, sheet_name="Trades", index=False)
            except Exception as e:
                logger.error(f"Error appending to Excel sheet: {e}")
                return
        else:
            try:
                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                    df_new.to_excel(writer, sheet_name="Trades", index=False)
            except Exception as e:
                logger.error(f"Error creating Excel sheet: {e}")
                return
                
        # Format the Excel columns and color codes
        self._format_excel(file_path)

    def _format_excel(self, file_path):
        """Applies headers styling, grid lines, alignment, and P&L green/red color styling."""
        try:
            wb = load_workbook(file_path)
            ws = wb["Trades"]
            
            # Fonts and Fills
            header_fill = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid") # Dark Navy
            header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
            data_font = Font(name="Segoe UI", size=10)
            
            green_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid") # Soft Green
            red_fill = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid") # Soft Red
            
            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'),
                right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'),
                bottom=Side(style='thin', color='D9D9D9')
            )
            
            # Format Headers (Row 1) - 13 columns now
            for col in range(1, 14):
                cell = ws.cell(row=1, column=col)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Format Data rows
            for row in range(2, ws.max_row + 1):
                pnl_cell = ws.cell(row=row, column=10) # Column J (10th column) is P&L
                pnl_val = float(pnl_cell.value or 0.0)
                
                # Dynamic conditional formatting
                fill_color = green_fill if pnl_val > 0 else (red_fill if pnl_val < 0 else PatternFill(fill_type=None))
                
                for col in range(1, 14):
                    cell = ws.cell(row=row, column=col)
                    cell.font = data_font
                    cell.border = thin_border
                    
                    # Alignment
                    if col in [1, 2, 3, 4]: # Time, Symbol, Instrument, Action
                        cell.alignment = Alignment(horizontal="center")
                    elif col in [5, 6, 7, 8, 9, 10, 11, 13]: # Qty, Entry/Exit Index, Entry/Exit Premium, P&L, Peak Run, Balance
                        cell.alignment = Alignment(horizontal="right")
                        cell.number_format = '#,##0.00'
                    else: # Reason
                        cell.alignment = Alignment(horizontal="left")
                    
                    # Apply background color to P&L cell
                    if col == 10 and fill_color.fill_type:
                        cell.fill = fill_color
            
            # Auto-adjust column widths for premium layout
            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)
                
            wb.save(file_path)
            logger.debug(f"Excel report updated and stylized at: {file_path}")
        except Exception as e:
            logger.error(f"Error styling Excel report: {e}")
