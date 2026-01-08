from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
import os
from pathlib import Path

from bayes_poker.hand_history.parse_gg_poker import (
    FAILED_HANDS_LOG_PATH,
    LOGGER,
    RushCashPokerStarsParser,
    configure_logging,
    extract_hand_metadata,
    parse_value_in_cents,
    sanitize_hand_text,
    save_failed_hand,
    save_hand_histories,
    get_skip_reason,
)

INPUT_DIR = Path(
    "/home/autumn/project/gg_handhistory/2025-02-13_GGHRC_NL2_SH_TGOVM255"
)
OUTPUT_DIR = Path("data/outputs")


def parse_file(path: Path) -> tuple[list, int, int]:
    configure_logging(FAILED_HANDS_LOG_PATH)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    parser = RushCashPokerStarsParser()
    hand_texts = parser.HAND.findall(text)
    total = len(hand_texts)
    parsed = 0
    hand_histories = []

    for index, hand_text in enumerate(hand_texts, start=1):
        skip_reason = get_skip_reason(hand_text)
        if skip_reason:
            hand_id, table = extract_hand_metadata(hand_text)
            LOGGER.info(
                "跳过手牌: hand=%s table=%s reason=%s",
                hand_id,
                table,
                skip_reason,
            )
            continue
        try:
            hand_histories.append(
                parser._parse(
                    sanitize_hand_text(hand_text),
                    parse_value_in_cents,
                )
            )
            parsed += 1
        except (KeyError, ValueError, RecursionError) as exc:
            hand_id, table = extract_hand_metadata(hand_text)
            LOGGER.warning(
                "解析失败: hand=%s table=%s error=%s", hand_id, table, exc
            )
            save_failed_hand(hand_text, hand_id, table)

    return hand_histories, total, parsed


def parse_and_save_file(path: Path) -> tuple[str, int, int]:
    hand_histories, total, parsed = parse_file(path)
    output_path = OUTPUT_DIR / f"{path.stem}.phhs"
    save_hand_histories(output_path, hand_histories)
    return output_path.name, total, parsed


def main() -> None:
    configure_logging(FAILED_HANDS_LOG_PATH)
    if not INPUT_DIR.exists():
        raise SystemExit(f"Input directory not found: {INPUT_DIR}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_files = sorted(
        path for path in INPUT_DIR.iterdir() if path.is_file()
    )
    if not input_files:
        raise SystemExit(f"No files found in: {INPUT_DIR}")

    input_files_to_parse: list[Path] = []
    skipped_files = 0
    for input_path in input_files:
        output_path = OUTPUT_DIR / f"{input_path.stem}.phhs"
        if output_path.exists():
            skipped_files += 1
            LOGGER.info(
                "跳过已解析文件: input=%s output=%s",
                input_path.name,
                output_path.name,
            )
            continue
        input_files_to_parse.append(input_path)

    if not input_files_to_parse:
        LOGGER.info("所有文件均已解析完成，无需重复解析。")
        return

    total_seen = 0
    total_parsed = 0
    total_files = len(input_files_to_parse)
    total_files_done = 0

    max_workers = min(os.cpu_count() or 1, total_files)
    LOGGER.info(
        "并行解析启动: workers=%s files=%s skipped=%s",
        max_workers,
        total_files,
        skipped_files,
    )

    if max_workers == 1:
        for input_path in input_files_to_parse:
            output_name, total, parsed = parse_and_save_file(input_path)
            total_seen += total
            total_parsed += parsed
            total_files_done += 1
            LOGGER.info(
                "解析进度: files=%s/%s parsed_hands=%s",
                total_files_done,
                total_files,
                total_parsed,
            )
        return

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for input_path in input_files_to_parse:
            futures[executor.submit(parse_and_save_file, input_path)] = (
                input_path
            )

        for future in as_completed(futures):
            try:
                output_name, total, parsed = future.result()
            except Exception as exc:
                input_path = futures[future]
                LOGGER.exception(
                    "文件解析失败: file=%s error=%s", input_path.name, exc
                )
                continue
            total_seen += total
            total_parsed += parsed
            total_files_done += 1
            LOGGER.info(
                "解析进度: files=%s/%s parsed_hands=%s",
                total_files_done,
                total_files,
                total_parsed,
            )


if __name__ == "__main__":
    main()
