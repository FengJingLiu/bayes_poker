from __future__ import annotations

import logging
import os


def get_log_level(default: int = logging.INFO) -> int:
    """
    获取项目日志等级。

    通过环境变量 BAYES_POKER_LOG_LEVEL 配置，可取：
    - 标准等级名：DEBUG/INFO/WARNING/ERROR/CRITICAL
    - 数字：10/20/30/40/50
    """
    raw = os.getenv("BAYES_POKER_LOG_LEVEL")
    if not raw:
        return default

    raw = raw.strip()
    if not raw:
        return default

    if raw.isdigit():
        return int(raw)

    level = logging.getLevelName(raw.upper())
    return level if isinstance(level, int) else default
