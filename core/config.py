import os
import yaml
from core.logger import custom_logger as logger

# Base configuration path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config_local.yaml")

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.load_config()

    def load_config(self):
        # 1. Load default config
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Base config file not found at: {CONFIG_PATH}")
            
        with open(CONFIG_PATH, "r") as f:
            self.config = yaml.safe_load(f) or {}
            logger.info("Base configuration (config.yaml) loaded successfully.")

        # 2. Apply local overrides for staging/development
        if os.path.exists(LOCAL_CONFIG_PATH):
            with open(LOCAL_CONFIG_PATH, "r") as f:
                local_config = yaml.safe_load(f) or {}
                if local_config:
                    self._deep_merge(self.config, local_config)
                    logger.success("Staging local overrides (config_local.yaml) merged successfully.")

    def _deep_merge(self, base_dict, override_dict):
        """Recursively merges override_dict into base_dict."""
        for key, val in override_dict.items():
            if isinstance(val, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_merge(base_dict[key], val)
            else:
                base_dict[key] = val

    def get(self, key, default=None):
        return self.config.get(key, default)

    @property
    def execution_mode(self) -> str:
        return self.config.get("execution_mode", "PAPER").upper()

    @property
    def active_broker(self) -> str:
        return self.config.get("active_broker", "paper").lower()

    @property
    def broker_config(self) -> dict:
        return self.config.get("broker", {})

    @property
    def risk_config(self) -> dict:
        return self.config.get("risk", {})

    @property
    def strategies_config(self) -> list:
        return self.config.get("strategies", [])

# Global Config Manager Instance
settings = ConfigManager()
