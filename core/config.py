import os
import re
import yaml
from core.logger import custom_logger as logger

# Base configuration path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")
LOCAL_CONFIG_PATH = os.path.join(BASE_DIR, "config_local.yaml")
ENV_PATH = os.path.join(BASE_DIR, ".env")

def load_dotenv(dotenv_path):
    if os.path.exists(dotenv_path):
        try:
            from dotenv import load_dotenv as py_dotenv_load
            py_dotenv_load(dotenv_path)
            logger.info(f"Loaded environment variables from {dotenv_path} via python-dotenv")
        except ImportError:
            logger.info(f"python-dotenv not found. Parsing {dotenv_path} manually...")
            try:
                with open(dotenv_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip("'\"")
                            if key:
                                os.environ[key] = val
            except Exception as e:
                logger.error(f"Failed to read {dotenv_path} manually: {e}")

# Load environment variables
load_dotenv(ENV_PATH)

class ConfigManager:
    def __init__(self):
        self.config = {}
        self.load_config()

    def _resolve_env_vars(self, data):
        """Recursively resolves ${VAR_NAME} or ${VAR_NAME:default} in config values."""
        if isinstance(data, dict):
            return {k: self._resolve_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_env_vars(item) for item in data]
        elif isinstance(data, str):
            # Match ${VAR_NAME} or ${VAR_NAME:default}
            pattern = re.compile(r'\$\{(\w+)(?::([^}]*))?\}')
            
            def replacer(match):
                var_name, default = match.groups()
                env_val = os.environ.get(var_name)
                if env_val is not None:
                    return env_val
                return default if default is not None else ""
            
            # If the entire string is just one ${VAR_NAME}, we can return its direct type (e.g. if it matches numbers)
            match = pattern.match(data)
            if match and match.group(0) == data:
                var_name, default = match.groups()
                env_val = os.environ.get(var_name)
                if env_val is not None:
                    return env_val
                return default if default is not None else ""
            
            return pattern.sub(replacer, data)
        return data

    def load_config(self):
        # 1. Load default config
        if not os.path.exists(CONFIG_PATH):
            raise FileNotFoundError(f"Base config file not found at: {CONFIG_PATH}")
            
        with open(CONFIG_PATH, "r") as f:
            base_config = yaml.safe_load(f) or {}
            self.config = self._resolve_env_vars(base_config)
            logger.info("Base configuration (config.yaml) loaded and environment variables resolved.")

        # 2. Apply local overrides for staging/development
        if os.path.exists(LOCAL_CONFIG_PATH):
            with open(LOCAL_CONFIG_PATH, "r") as f:
                local_config = yaml.safe_load(f) or {}
                if local_config:
                    resolved_local = self._resolve_env_vars(local_config)
                    self._deep_merge(self.config, resolved_local)
                    logger.success("Staging local overrides (config_local.yaml) loaded and environment variables resolved.")

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
