"""翻前（preflop）策略执行（runtime）。

该模块面向 server 的实时策略请求（`StrategyHandler`），在保持“表驱动可用”的同时，
提供完整的分层代码框架，便于后续替换/细化细节算法：

- RFI / 3Bet / 4Bet 分层（按行动前缀路由）
- Level 偏差（基于对手画像对范围/频率缩放）
- 下注尺度微调（例如 ISO：+Nbb/limper）
- 玩家画像驱动（`PlayerStatsRepository`）

当前默认实现仍以 `PreflopStrategy.query()`（内部用 `query_node`）为主，并提供：
- limp 的 ISO 注码粗调（默认 +1bb/limper）
- SB/BTN open 的 BB 画像缩放入口（最小实现，便于你后续替换）
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.engine import StrategyHandler, _base_response
from bayes_poker.strategy.preflop.models import PreflopStrategy, StrategyAction, StrategyNode
from bayes_poker.strategy.preflop.parser import parse_strategy_directory
from bayes_poker.strategy.range import (
    card_to_index52,
    combo_to_index1326,
    get_range_1326_to_169,
)
from bayes_poker.table.layout.base import get_position_by_seat

LOGGER = logging.getLogger(__name__)


class PreflopLayer(str, Enum):
    """翻前分层（用于路由与扩展点）。"""

    RFI = "rfi"
    THREE_BET = "3bet"
    FOUR_BET = "4bet"
    UNKNOWN = "unknown"


@dataclass(slots=True, frozen=True)
class PreflopRuntimeConfig:
    """翻前 runtime 配置（最小集合，后续可扩展）。"""

    iso_raise_increment_per_limper_bb: float = 1.0
    enable_open_level_adjustment: bool = True


def infer_preflop_layer(history: str) -> PreflopLayer:
    """从行动前缀推断翻前分层。

约定（与后续策略细化兼容）：
    - 0 次加注：RFI（包括 limp/overlimp/iso 前）
    - 1 次加注：3Bet（hero 面对 open/iso）
    - 2 次加注：4Bet（hero 面对 3bet）

更复杂的 cold 4bet / squeeze / limp-raise 等细分后续在对应层内部处理。
    """
    if not history:
        return PreflopLayer.RFI

    tokens = [t.strip().upper() for t in history.split("-") if t.strip()]
    raise_count = sum(1 for t in tokens if t == "RAI" or t.startswith("R"))

    if raise_count <= 0:
        return PreflopLayer.RFI
    if raise_count == 1:
        return PreflopLayer.THREE_BET
    if raise_count == 2:
        return PreflopLayer.FOUR_BET
    return PreflopLayer.UNKNOWN


def _extract_stack_bb(payload: dict[str, Any]) -> int:
    stack_bb = payload.get("stack_bb")
    if isinstance(stack_bb, int) and stack_bb > 0:
        return stack_bb
    if isinstance(stack_bb, float) and stack_bb > 0:
        return int(round(stack_bb))

    effective_stack = payload.get("effective_stack", 0.0) or 0.0
    if isinstance(effective_stack, (int, float)) and effective_stack > 0:
        return int(round(effective_stack))

    hero_stack = payload.get("hero_stack", 0.0) or 0.0
    if isinstance(hero_stack, (int, float)) and hero_stack > 0:
        return int(round(hero_stack))

    return 0


def _extract_history(payload: dict[str, Any]) -> str:
    history = payload.get("history")
    return str(history) if history is not None else ""


def _count_limpers_in_history(history: str) -> int:
    if not history:
        return 0
    tokens = [t.strip().upper() for t in history.split("-") if t.strip()]
    if any(t.startswith("R") for t in tokens):
        return 0
    return sum(1 for t in tokens if t == "C")


def _hero_index_169(hero_cards: list[str]) -> int | None:
    if len(hero_cards) != 2:
        return None

    c1 = hero_cards[0].strip()
    c2 = hero_cards[1].strip()
    if len(c1) != 2 or len(c2) != 2:
        return None

    rank1, suit1 = c1[0].upper(), c1[1].lower()
    rank2, suit2 = c2[0].upper(), c2[1].lower()

    try:
        idx1 = card_to_index52(rank1, suit1)
        idx2 = card_to_index52(rank2, suit2)
    except KeyError:
        return None

    idx1326 = combo_to_index1326(idx1, idx2)
    return get_range_1326_to_169()[idx1326]


def _pick_action_by_hero_hand(node: StrategyNode, hero_idx_169: int) -> StrategyAction | None:
    best_action: StrategyAction | None = None
    best_prob = -1.0
    for action in node.actions:
        prob = action.range.strategy[hero_idx_169]
        if prob > best_prob:
            best_action = action
            best_prob = prob
    return best_action


def _is_open_no_limper(history: str) -> bool:
    if not history:
        return True
    tokens = [t.strip().upper() for t in history.split("-") if t.strip()]
    return not any(t == "C" or t.startswith("R") for t in tokens)


def _find_first_raise(node: StrategyNode) -> StrategyAction | None:
    for action in node.actions:
        if action.is_all_in:
            return action
        if action.action_code.upper() == "RAI":
            return action
        if action.action_type in ("RAISE", "BET") or action.action_code.upper().startswith("R"):
            return action
    return None


def _extract_bb_player_id(payload: dict[str, Any]) -> str | None:
    players = payload.get("players")
    btn_seat = payload.get("btn_seat")
    if not isinstance(players, list) or not isinstance(btn_seat, int):
        return None

    player_count = len(players)
    if player_count <= 0:
        return None

    for idx, p in enumerate(players):
        if not isinstance(p, dict):
            continue
        seat_index = p.get("seat_index")
        if not isinstance(seat_index, int):
            seat_index = idx
        player_id = str(p.get("player_id") or "").strip()
        if not player_id:
            continue

        try:
            pos = get_position_by_seat(seat_index, btn_seat, player_count).value
        except Exception:
            continue

        if pos == "BB":
            return player_id

    return None


def _node_action_beliefs(node: StrategyNode) -> tuple[float, float, float]:
    call_belief = 0.0
    raise_belief = 0.0
    fold_belief = 0.0

    for action in node.actions:
        if action.action_type in ("CALL", "CHECK"):
            call_belief += float(action.total_frequency)
        elif action.action_type in ("RAISE", "BET") or action.is_all_in:
            raise_belief += float(action.total_frequency)
        elif action.action_type == "FOLD":
            fold_belief += float(action.total_frequency)

    if fold_belief <= 0.0:
        fold_belief = max(0.0, 1.0 - call_belief - raise_belief)

    return call_belief, raise_belief, fold_belief


def _player_cluster_beliefs(repo: PlayerStatsRepository, player_id: str, table_type: TableType) -> tuple[float, float]:
    stats = repo.get(player_id, table_type)
    if stats is None or not stats.preflop_stats:
        return 1.0 / 3, 1.0 / 3

    fold_sum = 0.0
    raise_sum = 0.0
    for s in stats.preflop_stats:
        fold_sum += float(s.fold_probability())
        raise_sum += float(s.bet_raise_probability())

    n = float(len(stats.preflop_stats))
    return fold_sum / n, raise_sum / n


def _adjust_open_raise_scale(
    *,
    base_raise: float,
    bb_standard_fold: float,
    bb_standard_raise: float,
    bb_cluster_fold: float,
    bb_cluster_raise: float,
) -> float:
    if base_raise <= 0.0:
        return 1.0
    if bb_standard_fold <= 1e-6:
        return 1.0
    target_raise = min(
        1.0,
        (bb_cluster_fold / bb_standard_fold) * base_raise + bb_standard_raise - bb_cluster_raise,
    )
    target_raise = max(0.0, min(1.0, target_raise))
    return target_raise / base_raise if base_raise > 0 else 1.0


def _pick_action_by_hero_hand_with_raise_scale(
    node: StrategyNode, hero_idx_169: int, *, raise_scale: float
) -> StrategyAction | None:
    best_action: StrategyAction | None = None
    best_prob = -1.0

    for action in node.actions:
        prob = float(action.range.strategy[hero_idx_169])
        if action.action_type in ("RAISE", "BET") or action.is_all_in:
            prob *= float(raise_scale)
        if prob > best_prob:
            best_action = action
            best_prob = prob
    return best_action


def create_preflop_strategy(
    *,
    strategy: PreflopStrategy,
    stats_repo: PlayerStatsRepository | None = None,
    config: PreflopRuntimeConfig | None = None,
) -> StrategyHandler:
    """创建可注册到 server 的 preflopStrategy 处理器。"""
    runtime = PreflopRuntime(
        strategy=strategy,
        stats_repo=stats_repo,
        config=config or PreflopRuntimeConfig(),
    )

    async def _handler(session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        _ = session_id
        return runtime.decide(payload)

    return _handler


@dataclass(slots=True)
class PreflopRuntime:
    """翻前 runtime 策略（分层框架 + 最小实现）。"""

    strategy: PreflopStrategy
    stats_repo: PlayerStatsRepository | None = None
    config: PreflopRuntimeConfig = PreflopRuntimeConfig()

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        state_version = int(payload.get("state_version", 0) or 0)
        stack_bb = _extract_stack_bb(payload)
        if stack_bb <= 0:
            return _base_response(state_version, "preflopStrategy: 缺少 stack_bb/effective_stack/hero_stack")

        hero_cards = payload.get("hero_cards") or []
        if not isinstance(hero_cards, list):
            hero_cards = []

        hero_idx_169 = _hero_index_169([str(c) for c in hero_cards])
        if hero_idx_169 is None:
            return _base_response(state_version, "preflopStrategy: 无法解析 hero_cards")

        history = _extract_history(payload)
        layer = infer_preflop_layer(history)

        try:
            if layer == PreflopLayer.RFI:
                return self._decide_rfi(payload, stack_bb, hero_idx_169, history)
            if layer == PreflopLayer.THREE_BET:
                return self._decide_3bet(payload, stack_bb, hero_idx_169, history)
            if layer == PreflopLayer.FOUR_BET:
                return self._decide_4bet(payload, stack_bb, hero_idx_169, history)
            return self._decide_fallback(payload, stack_bb, hero_idx_169, history)
        except Exception as exc:
            LOGGER.exception("preflopStrategy 计算异常: %s", exc)
            return _base_response(state_version, f"preflopStrategy: 异常 {exc}")

    # ----------------------------
    # RFI
    # ----------------------------
    def _decide_rfi(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
    ) -> dict[str, Any]:
        """RFI 层。

分层（框架）：
    1) no limper: 直接查表；SB/BTN 位置考虑 BB 3B 与防守范围（Level 偏差）
    2) 有 limper: 查“无 limper 基准”；按 3B 范围来加注（ISO）；下注尺度微调
        """
        state_version = int(payload.get("state_version", 0) or 0)
        num_limpers = _count_limpers_in_history(history)
        if num_limpers > 0:
            return self._decide_rfi_face_limper(payload, stack_bb, hero_idx_169, history, num_limpers)

        match = self.strategy.query(stack_bb, history)
        if match is None:
            return _base_response(state_version, f"preflopStrategy[RFI]: 未找到策略节点 (history={history})")

        chosen = self._pick_rfi_action_with_open_adjustment(
            payload,
            stack_bb,
            hero_idx_169,
            history,
            match.node,
        )
        if chosen is None:
            return _base_response(state_version, "preflopStrategy[RFI]: 节点无可用行动")

        result = _base_response(
            state_version,
            f"preflopStrategy[RFI]: matched={match.matched_history}, fallback={match.fallback_level}",
        )
        result.update(
            {
                "recommended_action": chosen.action_code,
                "recommended_amount": float(chosen.bet_size_bb or 0.0),
                "confidence": float(chosen.range.strategy[hero_idx_169]),
                "action_evs": {a.action_code: float(a.range.evs[hero_idx_169]) for a in match.node.actions},
            }
        )
        return result

    def _decide_rfi_face_limper(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
        num_limpers: int,
    ) -> dict[str, Any]:
        state_version = int(payload.get("state_version", 0) or 0)
        no_limper_history = history.replace("C", "F").replace("c", "F")
        match = self.strategy.query(stack_bb, no_limper_history)
        if match is None:
            return _base_response(
                state_version,
                f"preflopStrategy[RFI face limper]: 未找到策略节点 (history={no_limper_history})",
            )

        chosen = _pick_action_by_hero_hand(match.node, hero_idx_169)
        if chosen is None:
            return _base_response(state_version, "preflopStrategy[RFI face limper]: 节点无可用行动")

        amount = float(chosen.bet_size_bb or 0.0)
        if chosen.action_type in ("RAISE", "BET") and amount > 0:
            amount += float(num_limpers) * float(self.config.iso_raise_increment_per_limper_bb)

        result = _base_response(
            state_version,
            (
                "preflopStrategy[RFI face limper]: "
                f"limper={num_limpers}, matched={match.matched_history}, fallback={match.fallback_level}"
            ),
        )
        result.update(
            {
                "recommended_action": chosen.action_code,
                "recommended_amount": amount,
                "confidence": float(chosen.range.strategy[hero_idx_169]),
                "action_evs": {a.action_code: float(a.range.evs[hero_idx_169]) for a in match.node.actions},
            }
        )
        return result

    def _pick_rfi_action_with_open_adjustment(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
        node: StrategyNode,
    ) -> StrategyAction | None:
        """SB/BTN open 的 Level 偏差入口（最小实现，可替换）。"""
        hero_position = str(payload.get("hero_position") or "").upper()
        if not (self.stats_repo and self.config.enable_open_level_adjustment):
            return _pick_action_by_hero_hand(node, hero_idx_169)

        if hero_position not in ("SB", "BTN"):
            return _pick_action_by_hero_hand(node, hero_idx_169)

        if not _is_open_no_limper(history):
            return _pick_action_by_hero_hand(node, hero_idx_169)

        base_raise_action = _find_first_raise(node)
        if base_raise_action is None:
            return _pick_action_by_hero_hand(node, hero_idx_169)

        bb_player_id = _extract_bb_player_id(payload)
        if not bb_player_id:
            return _pick_action_by_hero_hand(node, hero_idx_169)

        sep = "-" if history else ""
        bb_history = f"{history}{sep}{base_raise_action.action_code}"
        if hero_position == "BTN":
            bb_history = f"{bb_history}-F"

        bb_match = self.strategy.query(stack_bb, bb_history)
        if bb_match is None:
            return _pick_action_by_hero_hand(node, hero_idx_169)

        _, bb_standard_raise, bb_standard_fold = _node_action_beliefs(bb_match.node)
        player_count = len(payload.get("players", []) or [])
        table_type = TableType.HEADS_UP if player_count <= 2 else TableType.SIX_MAX
        bb_cluster_fold, bb_cluster_raise = _player_cluster_beliefs(self.stats_repo, bb_player_id, table_type)
        raise_scale = _adjust_open_raise_scale(
            base_raise=float(base_raise_action.total_frequency),
            bb_standard_fold=float(bb_standard_fold),
            bb_standard_raise=float(bb_standard_raise),
            bb_cluster_fold=float(bb_cluster_fold),
            bb_cluster_raise=float(bb_cluster_raise),
        )

        return _pick_action_by_hero_hand_with_raise_scale(node, hero_idx_169, raise_scale=raise_scale)

    # ----------------------------
    # 3Bet
    # ----------------------------
    def _decide_3bet(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
    ) -> dict[str, Any]:
        """3Bet 层（框架）。

分层（框架）：
    1) RFI 玩家非 ISO：查该玩家 RSI 范围；查该位置标准 RSI 与 3B 范围；根据比例缩放 3B 范围
    2) RFI 玩家 ISO：查该玩家 RSI 范围；3B 顶端 1/3 范围

当前默认：直接查表并按英雄手牌概率选择行动；范围/下注尺度调整留作扩展点。
        """
        return self._decide_from_table(payload, stack_bb, hero_idx_169, history, layer="3Bet")

    # ----------------------------
    # 4Bet
    # ----------------------------
    def _decide_4bet(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
    ) -> dict[str, Any]:
        """4Bet 层（框架）。

分层（框架）：
    1) cold 4bet：查最后 raiser 的 3B 范围，4B 顶端 1/2 范围
    2) RSI face 3bet：查表

当前默认：直接查表并按英雄手牌概率选择行动；范围/下注尺度调整留作扩展点。
        """
        return self._decide_from_table(payload, stack_bb, hero_idx_169, history, layer="4Bet")

    # ----------------------------
    # fallback
    # ----------------------------
    def _decide_fallback(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
    ) -> dict[str, Any]:
        return self._decide_from_table(payload, stack_bb, hero_idx_169, history, layer="fallback")

    def _decide_from_table(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
        *,
        layer: str,
    ) -> dict[str, Any]:
        state_version = int(payload.get("state_version", 0) or 0)
        match = self.strategy.query(stack_bb, history)
        if match is None:
            return _base_response(state_version, f"preflopStrategy[{layer}]: 未找到策略节点 (history={history})")

        chosen = _pick_action_by_hero_hand(match.node, hero_idx_169)
        if chosen is None:
            return _base_response(state_version, f"preflopStrategy[{layer}]: 节点无可用行动")

        result = _base_response(
            state_version,
            f"preflopStrategy[{layer}]: matched={match.matched_history}, fallback={match.fallback_level}",
        )
        result.update(
            {
                "recommended_action": chosen.action_code,
                "recommended_amount": float(chosen.bet_size_bb or 0.0),
                "confidence": float(chosen.range.strategy[hero_idx_169]),
                "action_evs": {a.action_code: float(a.range.evs[hero_idx_169]) for a in match.node.actions},
            }
        )
        return result


def load_preflop_strategy_from_directory(*, strategy_dir: str | Path) -> PreflopStrategy:
    """加载“单策略目录”的翻前策略。"""
    return parse_strategy_directory(Path(strategy_dir))


def create_preflop_strategy_from_directory(
    *,
    strategy_dir: str | Path,
    stats_repo: PlayerStatsRepository | None = None,
    config: PreflopRuntimeConfig | None = None,
) -> StrategyHandler:
    """从“单策略目录”创建可注册的 preflopStrategy handler。"""
    strategy = load_preflop_strategy_from_directory(strategy_dir=strategy_dir)
    return create_preflop_strategy(strategy=strategy, stats_repo=stats_repo, config=config)
