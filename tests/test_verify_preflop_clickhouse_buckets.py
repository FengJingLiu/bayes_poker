"""verify_preflop_clickhouse_buckets 脚本测试."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys
from types import ModuleType


def _load_verify_script_module() -> ModuleType:
    """动态加载验证脚本模块.

    Returns:
        脚本模块对象.
    """

    script_path = (
        Path(__file__).resolve().parent.parent
        / "scripts"
        / "verify_preflop_clickhouse_buckets.py"
    )
    spec = importlib.util.spec_from_file_location(
        "verify_preflop_clickhouse_buckets",
        script_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载脚本模块: {script_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SCRIPT_MODULE = _load_verify_script_module()


def _build_args(
    clickhouse_url: str,
    *,
    native_port: int | None = None,
) -> argparse.Namespace:
    """构造最小命令行参数对象.

    Args:
        clickhouse_url: ClickHouse URL.
        native_port: 可选 native 端口覆盖值.

    Returns:
        参数对象.
    """

    return argparse.Namespace(
        clickhouse_url=clickhouse_url,
        database="default",
        user="default",
        password="",
        native_port=native_port,
    )


def test_resolve_clickhouse_cli_config_maps_http_8123_to_native_9000() -> None:
    """验证 http 8123 自动映射到 native 9000."""

    config = SCRIPT_MODULE.resolve_clickhouse_cli_config(
        _build_args("http://127.0.0.1:8123"),
    )

    assert config.port == 9000
    assert config.secure is False


def test_resolve_clickhouse_cli_config_maps_https_default_to_native_9440() -> None:
    """验证 https 默认端口映射到 native 9440."""

    config = SCRIPT_MODULE.resolve_clickhouse_cli_config(
        _build_args("https://clickhouse.local"),
    )

    assert config.port == 9440
    assert config.secure is True


def test_resolve_clickhouse_cli_config_uses_explicit_native_port() -> None:
    """验证显式 native 端口优先生效."""

    config = SCRIPT_MODULE.resolve_clickhouse_cli_config(
        _build_args(
            "http://127.0.0.1:8123",
            native_port=9010,
        ),
    )

    assert config.port == 9010
