from __future__ import annotations

from pathlib import Path
from time import perf_counter
from warnings import filterwarnings

from bayes_poker.hand_history.parse_gg_poker import (
    HAND_HISTORY_PATH,
    RushCashPokerStarsParser,
    load_hand_histories,
    parse_value_in_cents,
    save_hand_histories,
)

PERSISTED_BENCH_PATH = Path("data/outputs/bench_hand_histories.phhs")


def main() -> None:
    text = HAND_HISTORY_PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    parser = RushCashPokerStarsParser()
    filterwarnings("ignore", message="Unable to parse.*")

    start = perf_counter()
    hand_histories = list(parser(text, parse_value=parse_value_in_cents))
    parse_elapsed = perf_counter() - start
    parsed_count = len(hand_histories)
    parse_rate = parsed_count / parse_elapsed if parse_elapsed else 0.0

    start = perf_counter()
    save_hand_histories(PERSISTED_BENCH_PATH, hand_histories)
    save_elapsed = perf_counter() - start
    file_size = PERSISTED_BENCH_PATH.stat().st_size
    save_rate = file_size / save_elapsed if save_elapsed else 0.0

    start = perf_counter()
    loaded = load_hand_histories(PERSISTED_BENCH_PATH)
    load_elapsed = perf_counter() - start
    load_rate = len(loaded) / load_elapsed if load_elapsed else 0.0

    print(
        " | ".join(
            [
                f"parse {parsed_count} hands in {parse_elapsed:.3f}s",
                f"{parse_rate:.1f} hands/s",
            ]
        )
    )
    print(
        " | ".join(
            [
                f"save {file_size} bytes in {save_elapsed:.3f}s",
                f"{save_rate / (1024 * 1024):.2f} MB/s",
            ]
        )
    )
    print(
        " | ".join(
            [
                f"load {len(loaded)} hands in {load_elapsed:.3f}s",
                f"{load_rate:.1f} hands/s",
            ]
        )
    )


if __name__ == "__main__":
    main()
