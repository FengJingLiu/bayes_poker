"""population_vb 离线训练 CLI。"""

from __future__ import annotations

import argparse
from pathlib import Path

from .artifact import save_population_artifact
from .dataset import load_population_dataset
from .gto_family_prior import GtoFamilyPriorBuilder
from .trainer import PopulationTrainer


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 可选参数列表。为空时使用进程参数。

    Returns:
        解析后的命名空间。
    """

    parser = argparse.ArgumentParser(
        description="训练 preflop population VB posterior artifact。",
    )
    parser.add_argument("--strategy-db", required=True, help="策略 SQLite 路径。")
    parser.add_argument("--source-id", required=True, type=int, help="策略源 ID。")
    parser.add_argument(
        "--action-totals",
        required=True,
        help="action_totals.csv.gz 路径。",
    )
    parser.add_argument(
        "--exposed-counts",
        required=True,
        help="exposed_combo_counts.csv.gz 路径。",
    )
    parser.add_argument("--output", required=True, help="输出 artifact 路径（.npz）。")
    parser.add_argument("--table-type", type=int, default=6, help="桌型编码。默认 6。")
    parser.add_argument(
        "--stack-bb",
        type=int,
        default=100,
        help="目标筹码深度。默认 100。",
    )
    parser.add_argument("--lambda-gto", type=float, default=20.0)
    parser.add_argument("--eps", type=float, default=1e-3)
    parser.add_argument("--max-outer-iter", type=int, default=8)
    parser.add_argument("--max-local-iter", type=int, default=50)
    parser.add_argument("--tol", type=float, default=1e-6)
    return parser.parse_args(argv)


def run_cli(argv: list[str] | None = None) -> int:
    """执行 CLI 主流程。

    Args:
        argv: 可选参数列表。

    Returns:
        进程退出码。
    """

    args = parse_args(argv)
    observations = load_population_dataset(
        action_totals_path=args.action_totals,
        exposed_counts_path=args.exposed_counts,
    )
    prior_builder = GtoFamilyPriorBuilder(
        strategy_db_path=args.strategy_db,
        source_id=args.source_id,
        stack_bb=args.stack_bb,
    )
    priors = prior_builder.build_all(table_type=args.table_type)

    trainer = PopulationTrainer(
        lambda_gto=args.lambda_gto,
        eps=args.eps,
        max_outer_iter=args.max_outer_iter,
        max_local_iter=args.max_local_iter,
        tol=args.tol,
    )
    buckets = trainer.fit(observations=observations, priors=priors)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_population_artifact(
        buckets=buckets,
        output_path=str(output_path),
        metadata={
            "strategy_db": args.strategy_db,
            "source_id": args.source_id,
            "table_type": args.table_type,
            "stack_bb": args.stack_bb,
            "observation_count": len(observations),
            "bucket_count": len(buckets),
            "lambda_gto": args.lambda_gto,
            "eps": args.eps,
            "max_outer_iter": args.max_outer_iter,
            "max_local_iter": args.max_local_iter,
            "tol": args.tol,
        },
    )
    print(
        "population_vb training finished: "
        f"observations={len(observations)} buckets={len(buckets)} output={output_path}"
    )
    return 0


def main() -> None:
    """CLI 入口函数。"""

    raise SystemExit(run_cli())


if __name__ == "__main__":
    main()
