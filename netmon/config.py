"""Configuration management for netmon."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Default paths
CONFIG_DIR = Path("/etc/netmon")
CONFIG_FILE = CONFIG_DIR / "config.yaml"
CONFIG_FILE_JSON = CONFIG_DIR / "config.json"  # Legacy
DATA_DIR = Path("/var/lib/netmon")
DB_PATH = DATA_DIR / "traffic.db"
LOG_FILE = Path("/var/log/netmon.log")
PID_FILE = Path("/var/run/netmon.pid")


class PathsConfig(BaseModel):
    """Path configuration."""
    
    config_dir: Path = CONFIG_DIR
    data_dir: Path = DATA_DIR
    log_file: Path = LOG_FILE
    pid_file: Path = PID_FILE
    db_file: Path = DB_PATH


class NetmonConfig(BaseModel):
    """Main netmon configuration."""
    
    interfaces: list[str] = Field(default_factory=list)
    db_write_interval: int = 300
    data_retention_days: int = 90
    log_level: str = "INFO"
    nethogs_refresh_sec: int = 5
    main_loop_check_sec: int = 10
    paths: PathsConfig = Field(default_factory=PathsConfig)
    
    @property
    def db_path(self) -> Path:
        return self.paths.db_file
    
    @property
    def pid_path(self) -> Path:
        return self.paths.pid_file


def load_config() -> NetmonConfig:
    """Load configuration from file.
    
    Tries YAML first, then legacy JSON.
    
    Returns:
        NetmonConfig object
    """
    config_data = {}
    
    # Try YAML config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            logger.info(f"Config loaded from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load YAML config: {e}")
    
    # Try legacy JSON config
    elif CONFIG_FILE_JSON.exists():
        try:
            with open(CONFIG_FILE_JSON, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            logger.info(f"Config loaded from legacy JSON: {CONFIG_FILE_JSON}")
        except Exception as e:
            logger.warning(f"Failed to load JSON config: {e}")
    
    return NetmonConfig(**config_data)


def save_config(config: NetmonConfig) -> None:
    """Save configuration to YAML file.
    
    Args:
        config: NetmonConfig object to save
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    # Convert to dict, excluding paths (keep defaults)
    data = config.model_dump(exclude={'paths'})
    
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    logger.info(f"Config saved to {CONFIG_FILE}")


def get_config_value(key: str) -> Any:
    """Get a specific config value.
    
    Args:
        key: Dot-notation key like 'db_write_interval'
        
    Returns:
        Config value
    """
    config = load_config()
    
    # Handle dot notation
    obj = config
    for part in key.split('.'):
        if hasattr(obj, part):
            obj = getattr(obj, part)
        else:
            raise ValueError(f"Unknown config key: {key}")
    
    return obj


def set_config_value(key: str, value: str) -> NetmonConfig:
    """Set a specific config value.
    
    Args:
        key: Config key
        value: New value (will be type-converted)
        
    Returns:
        Updated config
    """
    config = load_config()
    data = config.model_dump()
    
    # Type conversion
    if key == 'db_write_interval':
        data[key] = int(value)
    elif key == 'data_retention_days':
        data[key] = int(value)
    elif key == 'nethogs_refresh_sec':
        data[key] = int(value)
    elif key == 'main_loop_check_sec':
        data[key] = int(value)
    elif key == 'log_level':
        data[key] = value.upper()
    elif key == 'interfaces':
        data[key] = [i.strip() for i in value.split(',') if i.strip()]
    else:
        raise ValueError(f"Unknown or read-only config key: {key}")
    
    new_config = NetmonConfig(**data)
    save_config(new_config)
    
    return new_config


def setup_logging(config: Optional[NetmonConfig] = None) -> logging.Logger:
    """Configure logging.
    
    Args:
        config: Optional config object
        
    Returns:
        Logger instance
    """
    if config is None:
        config = load_config()
    
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    
    # Handlers
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    
    # File handler
    try:
        config.paths.data_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(config.paths.log_file, encoding='utf-8')
        handlers.append(file_handler)
    except PermissionError:
        pass  # Console only
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=handlers,
        force=True
    )
    
    return logging.getLogger('netmon')
