import logging
import logging.handlers
import os
import yaml
from pathlib import Path

try:
    import psutil as _psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False

_logging_configured = False


def configure_logging() -> None:
    """Configure root logger once: console + rotating file. Call from main.py only."""
    global _logging_configured
    if _logging_configured:
        return

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)-30s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "prism.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet noisy third-party loggers
    for noisy in (
        "httpx", "httpcore", "chromadb", "urllib3", "multipart",
        "huggingface_hub", "sentence_transformers", "transformers",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _logging_configured = True


def setup_logger(name: str) -> logging.Logger:
    """Return named logger. configure_logging() must be called before first use."""
    return logging.getLogger(name)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load config.yaml and return as dict."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def count_tokens(text: str) -> int:
    """Approximate token count: len(text.split()) * 1.3"""
    return int(len(text.split()) * 1.3)


def log_memory_mb(logger: logging.Logger, label: str) -> float:
    """Log current process RSS in MB. Returns MB (0 if psutil unavailable)."""
    if not _PSUTIL:
        return 0.0
    rss = _psutil.Process().memory_info().rss / 1024 / 1024
    logger.info("MEM [%s] RSS=%.1fMB", label, rss)
    return rss
