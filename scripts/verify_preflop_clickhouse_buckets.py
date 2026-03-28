#!/usr/bin/env python3
"""验证 ClickHouse preflop 分桶质量.

使用说明:
1. 确保本机已安装并可执行 `clickhouse-client`.
2. 在项目根目录执行默认验证:
   `uv run python scripts/verify_preflop_clickhouse_buckets.py`
3. 指定连接与表名执行:
   `uv run python scripts/verify_preflop_clickhouse_buckets.py --clickhouse-url http://127.0.0.1:8123 --database default --table-name default.player_actions`
4. 如需覆盖原生协议端口:
   `uv run python scripts/verify_preflop_clickhouse_buckets.py --clickhouse-url http://127.0.0.1:8123 --native-port 9000`
5. 需要报告不通过时返回非 0 退出码:
   `uv run python scripts/verify_preflop_clickhouse_buckets.py --strict`
6. 查看全部参数:
   `uv run python scripts/verify_preflop_clickhouse_buckets.py -h`
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from bayes_poker.strategy.strategy_engine.population_vb.clickhouse_bucket_validator import (
    QueryRows,
    ValidationConfig,
    format_validation_report,
    parse_tsv_with_header,
    validate_clickhouse_buckets,
)

_HTTP_TO_NATIVE_PORT: dict[int, int] = {
    8123: 9000,
    8443: 9440,
}


@dataclass(frozen=True)
class ClickHouseCliConfig:
    """ClickHouse CLI 连接配置。

    Attributes:
        host: ClickHouse 主机名。
        port: ClickHouse 原生协议端口。
        database: 数据库名。
        user: 用户名。
        password: 密码。
        secure: 是否启用 TLS。
    """

    host: str
    port: int
    database: str
    user: str
    password: str
    secure: bool = False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。为空时使用进程参数。

    Returns:
        参数对象。
    """

    parser = argparse.ArgumentParser(
        description="验证 ClickHouse preflop_param_index 65 桶映射质量。",
    )
    parser.add_argument(
        "--clickhouse-url",
        default="http://127.0.0.1:8123",
        help="ClickHouse HTTP URL。默认 http://127.0.0.1:8123。",
    )
    parser.add_argument(
        "--database",
        default="default",
        help="数据库名。默认 default。",
    )
    parser.add_argument(
        "--user",
        default="default",
        help="用户名。默认 default。",
    )
    parser.add_argument(
        "--password",
        default="",
        help="密码。",
    )
    parser.add_argument(
        "--native-port",
        type=int,
        default=None,
        help=(
            "clickhouse-client 原生协议端口覆盖值。"
            "未设置时会把 URL 的 8123/8443 自动映射到 9000/9440。"
        ),
    )
    parser.add_argument(
        "--table-name",
        default="default.player_actions",
        help="动作表全名。默认 default.player_actions。",
    )
    parser.add_argument(
        "--preflop-street",
        type=int,
        default=1,
        help="preflop 的 street 编码。默认 1。",
    )
    parser.add_argument(
        "--min-valid-pct",
        type=float,
        default=98.0,
        help="合法桶占比阈值。默认 98.0。",
    )
    parser.add_argument(
        "--unhandled-limit",
        type=int,
        default=20,
        help="非法样本聚类明细上限。默认 20。",
    )
    parser.add_argument(
        "--micro-top-n",
        type=int,
        default=5,
        help="每个微观桶返回的历史条数。默认 5。",
    )
    parser.add_argument(
        "--micro-bucket-a",
        type=int,
        default=45,
        help="微观抽样桶 A。默认 45。",
    )
    parser.add_argument(
        "--micro-bucket-b",
        type=int,
        default=47,
        help="微观抽样桶 B。默认 47。",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="开启后当报告未通过时返回非 0 退出码。",
    )
    return parser.parse_args(argv)


def _resolve_native_port(
    parsed_port: int | None,
    secure: bool,
    explicit_native_port: int | None,
) -> int:
    """解析 clickhouse-client 应使用的原生协议端口.

    Args:
        parsed_port: 从 URL 解析出的端口.
        secure: 是否启用 TLS.
        explicit_native_port: 显式覆盖的原生端口.

    Returns:
        原生协议端口.
    """

    if explicit_native_port is not None:
        return explicit_native_port
    if parsed_port is None:
        return 9440 if secure else 9000
    if parsed_port in _HTTP_TO_NATIVE_PORT:
        return _HTTP_TO_NATIVE_PORT[parsed_port]
    return parsed_port


def resolve_clickhouse_cli_config(args: argparse.Namespace) -> ClickHouseCliConfig:
    """解析 ClickHouse URL 到 CLI 配置。

    Args:
        args: 命令行参数对象。

    Returns:
        CLI 连接配置。

    Raises:
        ValueError: 当 URL 非法时抛出。
    """

    parsed = urlparse(str(args.clickhouse_url))
    if not parsed.hostname:
        raise ValueError(f"clickhouse-url 非法: {args.clickhouse_url!r}")
    secure = parsed.scheme.lower() == "https"
    return ClickHouseCliConfig(
        host=parsed.hostname,
        port=_resolve_native_port(
            parsed_port=parsed.port,
            secure=secure,
            explicit_native_port=(
                int(args.native_port)
                if getattr(args, "native_port", None) is not None
                else None
            ),
        ),
        database=str(args.database),
        user=str(args.user),
        password=str(args.password),
        secure=secure,
    )


def build_validator_config(args: argparse.Namespace) -> ValidationConfig:
    """构建分桶验证配置。

    Args:
        args: 命令行参数对象。

    Returns:
        分桶验证配置。
    """

    return ValidationConfig(
        table_name=str(args.table_name),
        preflop_street=int(args.preflop_street),
        min_valid_pct=float(args.min_valid_pct),
        unhandled_limit=int(args.unhandled_limit),
        micro_top_n=int(args.micro_top_n),
        micro_bucket_a=int(args.micro_bucket_a),
        micro_bucket_b=int(args.micro_bucket_b),
    )


def _build_clickhouse_client_command(
    cli_config: ClickHouseCliConfig,
    query: str,
) -> list[str]:
    """构建 clickhouse-client 命令。

    Args:
        cli_config: CLI 连接配置。
        query: SQL 查询语句。

    Returns:
        命令参数列表。
    """

    sql = f"{query} FORMAT TSVWithNames"
    command = [
        "clickhouse-client",
        "--host",
        cli_config.host,
        "--port",
        str(cli_config.port),
        "--database",
        cli_config.database,
        "--user",
        cli_config.user,
        "--password",
        cli_config.password,
        "--query",
        sql,
    ]
    if cli_config.secure:
        command.append("--secure")
    return command


def execute_clickhouse_query(
    cli_config: ClickHouseCliConfig,
    query: str,
) -> QueryRows:
    """执行单条 ClickHouse 查询并解析为行字典。

    Args:
        cli_config: CLI 连接配置。
        query: SQL 查询语句。

    Returns:
        行字典列表。

    Raises:
        RuntimeError: 当命令执行失败时抛出。
    """

    command = _build_clickhouse_client_command(
        cli_config=cli_config,
        query=query,
    )
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise RuntimeError(f"ClickHouse 查询失败: {stderr}")
    return parse_tsv_with_header(completed.stdout)


def run(argv: Sequence[str] | None = None) -> int:
    """执行验证流程。

    Args:
        argv: 可选参数序列。

    Returns:
        进程退出码。
    """

    parsed_args = parse_args(list(argv) if argv is not None else None)
    cli_config = resolve_clickhouse_cli_config(parsed_args)
    validator_config = build_validator_config(parsed_args)
    report = validate_clickhouse_buckets(
        executor=lambda query: execute_clickhouse_query(cli_config, query),
        config=validator_config,
    )
    print(format_validation_report(report))
    if parsed_args.strict and not report.passed:
        return 1
    return 0


def main() -> None:
    """脚本入口函数。"""

    raise SystemExit(run())


if __name__ == "__main__":
    main()
