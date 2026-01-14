import os
from pathlib import Path

from bayes_poker.player_metrics.rust_api import batch_process_phhs


def run_batch_task() -> None:
    phhs_dir = os.getenv("BAYES_POKER_PHHS_DIR", "data/outputs")
    db_path = Path(os.getenv("BAYES_POKER_DB_PATH", "data/database/base.db"))

    max_files_env = os.getenv("BAYES_POKER_MAX_FILES_IN_MEMORY")
    max_files_in_memory = int(max_files_env) if max_files_env else None

    db_path.parent.mkdir(parents=True, exist_ok=True)

    batch_process_phhs(
        phhs_dir,
        db_path,
        max_files_in_memory=max_files_in_memory,
    )


if __name__ == "__main__":
    run_batch_task()
