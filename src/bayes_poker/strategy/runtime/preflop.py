"""翻前(preflop)策略执行(runtime)。

该模块面向 server 的实时策略请求(`StrategyHandler`)，在保持"表驱动可用"的同时，
提供完整的分层代码框架，便于后续替换/细化细节算法:

- RFI / 3Bet / 4Bet 分层(按行动前缀路由)
- Level 偏差(基于对手画像对范围/频率缩放)
- 下注尺度微调(例如 ISO:+Nbb/limper)
- 玩家画像驱动(`PlayerStatsRepository`)

使用 ObservedTableState 作为输入状态格式。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bayes_poker.player_metrics.enums import TableType
from bayes_poker.storage.player_stats_repository import PlayerStatsRepository
from bayes_poker.strategy.runtime.base import StrategyHandler, _base_response
from bayes_poker.strategy.preflop_parse.models import (
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.preflop_parse.parser import parse_strategy_directory
from bayes_poker.strategy.runtime.preflop_history import (
    PreflopLayer,
    count_limpers_in_history,
    infer_preflop_layer,
    is_open_no_limper,
)
from bayes_poker.strategy.range import (
    card_to_index52,
    combo_to_index1326,
    get_range_1326_to_169,
)
from bayes_poker.table.layout.base import (
    Position as TablePosition,
    get_position_by_seat,
)

if TYPE_CHECKING:
    from bayes_poker.table.observed_state import ObservedTableState

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PreflopRuntimeConfig:
    """翻前 runtime 配置(最小集合，后续可扩展)。

    Attributes:
        iso_raise_increment_per_limper_bb: 每个 limper 增加的 ISO 加注金额(BB)。
        enable_open_level_adjustment: 是否启用 open 时的 level 调整。
    """

    iso_raise_increment_per_limper_bb: float = 1.0
    enable_open_level_adjustment: bool = True


_count_limpers_in_history = count_limpers_in_history


def _hero_index_169(hero_cards: list[str]) -> int | None:
    """将 hero 手牌转换为 169 手牌索引。

    Args:
        hero_cards: Hero 手牌列表。

    Returns:
        169 手牌索引，或 None 如果无法解析。
    """
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


def _pick_action_by_hero_hand(
    node: StrategyNode, hero_idx_169: int
) -> StrategyAction | None:
    """根据 hero 手牌选择最佳动作。

    Args:
        node: 策略节点。
        hero_idx_169: Hero 手牌的 169 索引。

    Returns:
        最佳动作，或 None 如果无可用动作。
    """
    best_action: StrategyAction | None = None
    best_prob = -1.0
    for action in node.actions:
        prob = action.range.strategy[hero_idx_169]
        if prob > best_prob:
            best_action = action
            best_prob = prob
    return best_action


_is_open_no_limper = is_open_no_limper


def _coerce_table_position(value: Any) -> TablePosition | None:
    """将输入值转换为位置枚举。

    Args:
        value: 输入位置值, 支持枚举或字符串。

    Returns:
        位置枚举, 失败时返回 `None`。
    """
    if isinstance(value, TablePosition):
        return value
    if isinstance(value, str):
        try:
            return TablePosition(value.upper())
        except ValueError:
            return None
    return None


def _find_first_raise(node: StrategyNode) -> StrategyAction | None:
    """查找节点中的第一个加注动作。

    Args:
        node: 策略节点。

    Returns:
        第一个加注动作，或 None。
    """
    for action in node.actions:
        if action.is_all_in:
            return action
        if action.action_code.upper() == "RAI":
            return action
        if action.action_type in (
            "RAISE",
            "BET",
        ) or action.action_code.upper().startswith("R"):
            return action
    return None


def _extract_bb_player_id(payload: dict[str, Any]) -> str | None:
    """从 payload 中提取 BB 位置玩家 ID。

    Args:
        payload: 请求 payload。

    Returns:
        BB 玩家 ID，或 None。
    """
    players = payload.get("players")
    btn_seat = payload.get("btn_seat")
    if not isinstance(players, list) or not isinstance(btn_seat, int):
        return None

    player_count = len(players)
    if player_count <= 0:
        return None

    for idx, p in enumerate(players):
        if isinstance(p, dict):
            seat_index = p.get("seat_index")
            if not isinstance(seat_index, int):
                seat_index = idx
            player_id = str(p.get("player_id") or "").strip()
        else:
            seat_index = getattr(p, "seat_index", idx)
            if not isinstance(seat_index, int):
                seat_index = idx
            player_id = str(getattr(p, "player_id", "") or "").strip()
        if not player_id:
            continue

        try:
            pos = get_position_by_seat(seat_index, btn_seat, player_count)
        except Exception:
            continue

        if pos == TablePosition.BB:
            return player_id

    return None


def _node_action_beliefs(node: StrategyNode) -> tuple[float, float, float]:
    """计算节点动作的信念分布。

    Args:
        node: 策略节点。

    Returns:
        (call_belief, raise_belief, fold_belief) 三元组。
    """
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


def _player_cluster_beliefs(
    repo: PlayerStatsRepository, player_id: str, table_type: TableType
) -> tuple[float, float]:
    """获取玩家的聚类信念。

    Args:
        repo: 玩家统计仓库。
        player_id: 玩家 ID。
        table_type: 牌桌类型。

    Returns:
        (fold_belief, raise_belief) 二元组。
    """
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
    """调整 open 加注的缩放比例。

    Args:
        base_raise: 基础加注频率。
        bb_standard_fold: BB 标准弃牌频率。
        bb_standard_raise: BB 标准加注频率。
        bb_cluster_fold: BB 聚类弃牌频率。
        bb_cluster_raise: BB 聚类加注频率。

    Returns:
        加注缩放比例。
    """
    if base_raise <= 0.0:
        return 1.0
    if bb_standard_fold <= 1e-6:
        return 1.0
    target_raise = min(
        1.0,
        (bb_cluster_fold / bb_standard_fold) * base_raise
        + bb_standard_raise
        - bb_cluster_raise,
    )
    target_raise = max(0.0, min(1.0, target_raise))
    return target_raise / base_raise if base_raise > 0 else 1.0


def _pick_action_by_hero_hand_with_raise_scale(
    node: StrategyNode, hero_idx_169: int, *, raise_scale: float
) -> StrategyAction | None:
    """根据 hero 手牌和加注缩放选择动作。

    Args:
        node: 策略节点。
        hero_idx_169: Hero 手牌的 169 索引。
        raise_scale: 加注缩放比例。

    Returns:
        最佳动作，或 None。
    """
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
    """创建可注册到 server 的 preflopStrategy 处理器。

    Args:
        strategy: 翻前策略对象。
        stats_repo: 玩家统计仓库(可选)。
        config: 运行时配置(可选)。

    Returns:
        策略处理器函数。
    """
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
    """翻前 runtime 策略(分层框架 + 最小实现)。

    Attributes:
        strategy: 翻前策略对象。
        stats_repo: 玩家统计仓库。
        config: 运行时配置。
    """

    strategy: PreflopStrategy
    stats_repo: PlayerStatsRepository | None = None
    config: PreflopRuntimeConfig = PreflopRuntimeConfig()

    def decide(self, payload: dict[str, Any]) -> dict[str, Any]:
        """处理翻前策略请求。

        从 payload 中的 observed_state 提取信息，
        调用策略查询并返回推荐动作。

        Args:
            payload: 包含 observed_state 等信息的字典

        Returns:
            策略响应字典
        """
        state_version = int(payload.get("state_version", 0) or 0)

        # 优先从 observed_state 提取信息
        observed_state: ObservedTableState | None = payload.get("observed_state")

        if observed_state is not None:
            # 新格式: 直接从 ObservedTableState 提取
            stack_bb = int(observed_state.get_hero_stack_bb())
            hero_cards = (
                list(observed_state.hero_cards) if observed_state.hero_cards else []
            )
            history = observed_state.get_action_history_string()
            hero_position = observed_state.get_hero_position_enum()
            player_count = observed_state.player_count
        else:
            # Fallback: 从 engine 层已经解析好的字段提取
            stack_bb = int(payload.get("hero_stack_bb", 0) or 0)
            hero_cards = payload.get("hero_cards", [])
            history = payload.get("action_history", "")
            hero_position = _coerce_table_position(payload.get("hero_position"))
            player_count = 6

        if stack_bb <= 0:
            return _base_response(
                state_version,
                "preflopStrategy: 无法获取有效的 stack_bb",
            )

        hero_idx_169 = _hero_index_169(hero_cards)
        if hero_idx_169 is None:
            return _base_response(state_version, "preflopStrategy: 无法解析 hero_cards")

        layer = infer_preflop_layer(history)

        # 将提取的信息添加到 payload 供后续方法使用
        enriched_payload = {
            **payload,
            "stack_bb": stack_bb,
            "hero_cards": hero_cards,
            "history": history,
            "hero_position": hero_position,
            "player_count": player_count,
        }

        try:
            if layer == PreflopLayer.RFI:
                return self._decide_rfi(
                    enriched_payload, stack_bb, hero_idx_169, history
                )
            if layer == PreflopLayer.THREE_BET:
                return self._decide_3bet(
                    enriched_payload, stack_bb, hero_idx_169, history
                )
            if layer == PreflopLayer.FOUR_BET:
                return self._decide_4bet(
                    enriched_payload, stack_bb, hero_idx_169, history
                )
            return self._decide_fallback(
                enriched_payload, stack_bb, hero_idx_169, history
            )
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

        分层(框架):
            1) no limper: 直接查表；SB/BTN 位置考虑 BB 3B 与防守范围(Level 偏差)
            2) 有 limper: 查"无 limper 基准"；按 3B 范围来加注(ISO)；下注尺度微调

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。

        Returns:
            策略响应字典。
        """
        state_version = int(payload.get("state_version", 0) or 0)
        num_limpers = _count_limpers_in_history(history)
        if num_limpers > 0:
            return self._decide_rfi_face_limper(
                payload, stack_bb, hero_idx_169, history, num_limpers
            )

        match = self.strategy.query(stack_bb, history)
        if match is None:
            return _base_response(
                state_version,
                f"preflopStrategy[RFI]: 未找到策略节点 (history={history})",
            )

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
                "action_evs": {
                    a.action_code: float(a.range.evs[hero_idx_169])
                    for a in match.node.actions
                },
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
        """面对 limper 的 RFI 决策。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。
            num_limpers: limper 数量。

        Returns:
            策略响应字典。
        """
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
            return _base_response(
                state_version, "preflopStrategy[RFI face limper]: 节点无可用行动"
            )

        amount = float(chosen.bet_size_bb or 0.0)
        if chosen.action_type in ("RAISE", "BET") and amount > 0:
            amount += float(num_limpers) * float(
                self.config.iso_raise_increment_per_limper_bb
            )

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
                "action_evs": {
                    a.action_code: float(a.range.evs[hero_idx_169])
                    for a in match.node.actions
                },
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
        """SB/BTN open 的 Level 偏差入口(最小实现，可替换)。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。
            node: 策略节点。

        Returns:
            选择的动作，或 None。
        """
        hero_position = _coerce_table_position(payload.get("hero_position"))
        if not (self.stats_repo and self.config.enable_open_level_adjustment):
            return _pick_action_by_hero_hand(node, hero_idx_169)

        if hero_position not in (TablePosition.SB, TablePosition.BTN):
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
        if hero_position == TablePosition.BTN:
            bb_history = f"{bb_history}-F"

        bb_match = self.strategy.query(stack_bb, bb_history)
        if bb_match is None:
            return _pick_action_by_hero_hand(node, hero_idx_169)

        _, bb_standard_raise, bb_standard_fold = _node_action_beliefs(bb_match.node)
        player_count = len(payload.get("players", []) or [])
        table_type = TableType.HEADS_UP if player_count <= 2 else TableType.SIX_MAX
        bb_cluster_fold, bb_cluster_raise = _player_cluster_beliefs(
            self.stats_repo, bb_player_id, table_type
        )
        raise_scale = _adjust_open_raise_scale(
            base_raise=float(base_raise_action.total_frequency),
            bb_standard_fold=float(bb_standard_fold),
            bb_standard_raise=float(bb_standard_raise),
            bb_cluster_fold=float(bb_cluster_fold),
            bb_cluster_raise=float(bb_cluster_raise),
        )

        return _pick_action_by_hero_hand_with_raise_scale(
            node, hero_idx_169, raise_scale=raise_scale
        )

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
        """3Bet 层(框架)。

        分层(框架):
            1) RFI 玩家非 ISO:查该玩家 RSI 范围；查该位置标准 RSI 与 3B 范围；根据比例缩放 3B 范围
            2) RFI 玩家 ISO:查该玩家 RSI 范围；3B 顶端 1/3 范围

        当前默认:直接查表并按英雄手牌概率选择行动；范围/下注尺度调整留作扩展点。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。

        Returns:
            策略响应字典。
        """
        return self._decide_from_table(
            payload, stack_bb, hero_idx_169, history, layer="3Bet"
        )

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
        """4Bet 层(框架)。

        分层(框架):
            1) cold 4bet:查最后 raiser 的 3B 范围，4B 顶端 1/2 范围
            2) RSI face 3bet:查表

        当前默认:直接查表并按英雄手牌概率选择行动；范围/下注尺度调整留作扩展点。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。

        Returns:
            策略响应字典。
        """
        return self._decide_from_table(
            payload, stack_bb, hero_idx_169, history, layer="4Bet"
        )

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
        """Fallback 决策。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。

        Returns:
            策略响应字典。
        """
        return self._decide_from_table(
            payload, stack_bb, hero_idx_169, history, layer="fallback"
        )

    def _decide_from_table(
        self,
        payload: dict[str, Any],
        stack_bb: int,
        hero_idx_169: int,
        history: str,
        *,
        layer: str,
    ) -> dict[str, Any]:
        """从策略表查询并返回决策。

        Args:
            payload: 请求 payload。
            stack_bb: 筹码(BB 单位)。
            hero_idx_169: Hero 手牌的 169 索引。
            history: 动作历史字符串。
            layer: 层名称(用于日志)。

        Returns:
            策略响应字典。
        """
        state_version = int(payload.get("state_version", 0) or 0)
        match = self.strategy.query(stack_bb, history)
        if match is None:
            return _base_response(
                state_version,
                f"preflopStrategy[{layer}]: 未找到策略节点 (history={history})",
            )

        chosen = _pick_action_by_hero_hand(match.node, hero_idx_169)
        if chosen is None:
            return _base_response(
                state_version, f"preflopStrategy[{layer}]: 节点无可用行动"
            )

        result = _base_response(
            state_version,
            f"preflopStrategy[{layer}]: matched={match.matched_history}, fallback={match.fallback_level}",
        )
        result.update(
            {
                "recommended_action": chosen.action_code,
                "recommended_amount": float(chosen.bet_size_bb or 0.0),
                "confidence": float(chosen.range.strategy[hero_idx_169]),
                "action_evs": {
                    a.action_code: float(a.range.evs[hero_idx_169])
                    for a in match.node.actions
                },
            }
        )
        return result


def load_preflop_strategy_from_directory(
    *, strategy_dir: str | Path
) -> PreflopStrategy:
    """加载"单策略目录"的翻前策略。

    Args:
        strategy_dir: 策略目录路径。

    Returns:
        翻前策略对象。
    """
    return parse_strategy_directory(Path(strategy_dir))


def create_preflop_strategy_from_directory(
    *,
    strategy_dir: str | Path,
    stats_repo: PlayerStatsRepository | None = None,
    config: PreflopRuntimeConfig | None = None,
) -> StrategyHandler:
    """从"单策略目录"创建可注册的 preflopStrategy handler。

    Args:
        strategy_dir: 策略目录路径。
        stats_repo: 玩家统计仓库(可选)。
        config: 运行时配置(可选)。

    Returns:
        策略处理器函数。
    """
    strategy = load_preflop_strategy_from_directory(strategy_dir=strategy_dir)
    return create_preflop_strategy(
        strategy=strategy, stats_repo=stats_repo, config=config
    )
