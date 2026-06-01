import sys
import io
import os
from loguru import logger

# Ensure standard output and error handles support UTF-8 characters (emojis) under Windows consoles
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Remove default logger and add our custom high-speed async-safe logger
logger.remove()
logger.add(
    "logs/activity_precise.log",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {module}:{function} - {message}",
    level="DEBUG",
    rotation="10 MB", # Har 10MB baad nayi file banegi taaki system slow na ho
    enqueue=True      # Async execution ke liye zaroori
)
logger.add(sys.stdout, format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>")

custom_logger = logger