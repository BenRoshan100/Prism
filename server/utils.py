import logging
import yaml
from pathlib import Path


def load_config(config_path: str = "config.yaml") -> dict:
    """Load config.yaml and return as dict."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def count_tokens(text: str) -> int:
    """Approximate token count: len(text.split()) * 1.3"""
    return int(len(text.split()) * 1.3)


def setup_logger(name: str) -> logging.Logger:
    """Return configured logger with timestamp format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
