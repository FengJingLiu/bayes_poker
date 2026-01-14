#!/usr/bin/env python3
"""对比 Rust 实现 vs Python 实现的性能"""

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from pokerkit import HandHistory

from bayes_poker.player_metrics.builder import build_player_stats_from_hands
from bayes_poker.player_metrics.enums import TableType

TARGET_HANDS = 20_000


def load_hands(directory: Path, limit: int) -> list[HandHistory]:
    hands: list[HandHistory] = []
    for phhs_file in sorted(directory.glob("*.phhs")):
        with phhs_file.open("rb") as f:
            for hh in HandHistory.load_all(f):
                hands.append(hh)
                if len(hands) >= limit:
                    return hands
    return hands


def hand_to_json(hh: HandHistory) -> str:
    """将 HandHistory 转换为 Rust 可解析的 JSON 格式。

    PHH 动作字符串格式：
    - "d dh p1 ????" -> 发牌（跳过）
    - "d db XxXxXx" -> 发公共牌（街变化）
    - "p1 f" -> 玩家1 fold
    - "p2 cc" -> 玩家2 check/call
    - "p3 cbr 100" -> 玩家3 raise 100
    """
    players = list(hh.players) if hh.players else []
    raw_actions = hh.actions if hh.actions else []
    blinds = list(hh.blinds_or_straddles) if hh.blinds_or_straddles else []

    actions = []
    current_street = "preflop"
    board_cards = 0
    current_bet = max(blinds) if blinds else 0
    player_bets: dict[str, int] = {}

    for i, player_name in enumerate(players):
        if i < len(blinds):
            player_bets[player_name] = blinds[i]
        else:
            player_bets[player_name] = 0

    for action_str in raw_actions:
        action_str = action_str.strip()
        if not action_str:
            continue

        parts = action_str.split()
        if len(parts) < 2:
            continue

        actor = parts[0]

        # 处理 dealer 动作
        if actor == "d":
            action_code = parts[1] if len(parts) > 1 else ""
            if action_code == "db":
                # 发公共牌
                cards_str = parts[2] if len(parts) > 2 else ""
                new_cards = len(cards_str) // 2 if cards_str else 0
                board_cards += new_cards
                if board_cards == 3:
                    current_street = "flop"
                elif board_cards == 4:
                    current_street = "turn"
                elif board_cards == 5:
                    current_street = "river"
                # 新街重置 bets
                for pn in players:
                    player_bets[pn] = 0
                current_bet = 0
            continue

        # 跳过非玩家动作
        if not actor.startswith("p"):
            continue

        try:
            player_idx = int(actor[1:]) - 1
        except ValueError:
            continue

        if player_idx < 0 or player_idx >= len(players):
            continue

        player_name = players[player_idx]
        action_code = parts[1] if len(parts) > 1 else ""
        amount = 0

        if len(parts) > 2:
            try:
                amount = int(parts[2])
            except ValueError:
                pass

        action_lower = action_code.lower()

        # 解析动作类型
        if action_lower == "f":
            action_type = "fold"
        elif action_lower == "cc":
            old_bet = player_bets.get(player_name, 0)
            if current_bet <= old_bet:
                action_type = "check"
            else:
                action_type = "call"
                if amount <= 0:
                    amount = current_bet
        elif action_lower in ("cbr", "raise"):
            action_type = "raise"
        elif action_lower == "bet":
            action_type = "bet"
        elif "all" in action_lower or "allin" in action_lower:
            action_type = "allin"
        else:
            # 跳过未知动作
            continue

        actions.append({
            "street": current_street,
            "player": player_name,
            "action_type": action_type,
            "amount": amount,
        })

        # 更新状态
        if action_type in ("call", "bet", "raise", "allin"):
            player_bets[player_name] = amount
            if amount > current_bet:
                current_bet = amount

    return json.dumps({"players": players, "actions": actions})


def benchmark_python(hands: list[HandHistory]) -> tuple[float, int]:
    hu_hands = [hh for hh in hands if hh.players and len(hh.players) == 2]
    six_max_hands = [hh for hh in hands if hh.players and len(hh.players) > 2]

    start = time.perf_counter()
    
    result = {}
    if hu_hands:
        stats = build_player_stats_from_hands(hu_hands, TableType.HEADS_UP)
        result.update(stats)
    if six_max_hands:
        stats = build_player_stats_from_hands(six_max_hands, TableType.SIX_MAX)
        result.update(stats)
    
    duration = time.perf_counter() - start
    return duration, len(result)


def benchmark_rust(hands: list[HandHistory]) -> tuple[float, int]:
    try:
        import poker_stats_rs
    except ImportError as e:
        print(f"Rust module not found: {e}")
        return 0.0, 0

    hu_hands = [hh for hh in hands if hh.players and len(hh.players) == 2]
    six_max_hands = [hh for hh in hands if hh.players and len(hh.players) > 2]

    start = time.perf_counter()
    
    result = []
    if hu_hands:
        hands_json = [hand_to_json(hh) for hh in hu_hands]
        result.extend(poker_stats_rs.py_build_stats(hands_json, 2))
    if six_max_hands:
        hands_json = [hand_to_json(hh) for hh in six_max_hands]
        result.extend(poker_stats_rs.py_build_stats(hands_json, 6))
    
    duration = time.perf_counter() - start
    return duration, len(result)


def main():
    data_dir = PROJECT_ROOT / "data" / "outputs"
    if not data_dir.exists():
        print(f"错误: 数据目录不存在: {data_dir}")
        sys.exit(1)

    print(f"加载 {TARGET_HANDS:,} 手牌...")
    start_load = time.perf_counter()
    hands = load_hands(data_dir, TARGET_HANDS)
    load_duration = time.perf_counter() - start_load
    print(f"加载完成: {len(hands):,} 手牌，耗时 {load_duration:.2f}s\n")

    print("=" * 60)
    print("Python 实现 (单线程)")
    print("=" * 60)
    py_duration, py_players = benchmark_python(hands)
    py_speed = len(hands) / py_duration if py_duration > 0 else 0
    print(f"  耗时: {py_duration:.2f}s")
    print(f"  速度: {py_speed:,.0f} hands/s")
    print(f"  玩家数: {py_players}")
    print()

    print("=" * 60)
    print("Rust 实现 (rayon 并行)")
    print("=" * 60)
    rust_duration, rust_players = benchmark_rust(hands)
    rust_speed = len(hands) / rust_duration if rust_duration > 0 else 0
    print(f"  耗时: {rust_duration:.2f}s")
    print(f"  速度: {rust_speed:,.0f} hands/s")
    print(f"  玩家数: {rust_players}")
    print()

    print("=" * 60)
    print("对比结果")
    print("=" * 60)
    if rust_duration > 0 and py_duration > 0:
        speedup = py_duration / rust_duration
        print(f"Rust vs Python 加速比: {speedup:.1f}x")
    else:
        print("无法计算加速比")


if __name__ == "__main__":
    main()
