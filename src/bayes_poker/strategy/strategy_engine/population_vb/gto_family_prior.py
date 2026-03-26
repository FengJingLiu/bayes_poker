"""从策略库构建 family-level GTO 先验。"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import numpy as np

from bayes_poker.player_metrics.enums import ActionType as MetricsActionType
from bayes_poker.player_metrics.enums import Position as MetricsPosition
from bayes_poker.player_metrics.enums import TableType
from bayes_poker.player_metrics.params import PreFlopParams
from bayes_poker.storage.preflop_strategy_repository import (
    PreflopStrategyRepository,
    SolverActionRecord,
)
from bayes_poker.strategy.range import RANGE_169_LENGTH

from .contracts import GtoFamilyPrior, PriorKind
from .holdcards import combo_weights_169
from .pseudo_call_prior import (
    build_pseudo_call_prior_from_raise_ev,
    compute_raise_score_from_actions,
)

_ACTION_FAMILY_INDEX: dict[str, int] = {"F": 0, "C": 1, "R": 2}
_POSITION_TO_METRICS: dict[str, MetricsPosition] = {
    "SB": MetricsPosition.SMALL_BLIND,
    "BB": MetricsPosition.BIG_BLIND,
    "UTG": MetricsPosition.UTG,
    "HJ": MetricsPosition.HJ,
    "MP": MetricsPosition.HJ,
    "CO": MetricsPosition.CO,
    "BTN": MetricsPosition.BUTTON,
}


@dataclass
class _AggregatedPrior:
    """聚合中的临时状态。"""

    probs_sum: np.ndarray
    raise_score_sum: np.ndarray
    total_weight: float
    prior_kind: PriorKind


class GtoFamilyPriorBuilder:
    """从 strategy SQLite 构建 family-level 先验。"""

    def __init__(
        self,
        strategy_db_path: str,
        source_id: int,
        stack_bb: int = 100,
        empirical_mix_by_param: dict[int, np.ndarray] | None = None,
    ) -> None:
        """初始化先验构建器。

        Args:
            strategy_db_path: 策略 SQLite 路径。
            source_id: 策略源 ID。
            stack_bb: 目标筹码深度。
            empirical_mix_by_param: 可选经验动作占比, key 为 `param_index`。
        """

        self._strategy_db_path = strategy_db_path
        self._source_id = source_id
        self._stack_bb = stack_bb
        self._empirical_mix_by_param = empirical_mix_by_param or {}
        self._combo_weights = combo_weights_169()

    def build_all(self, table_type: int) -> dict[int, GtoFamilyPrior]:
        """构建给定桌型下全部 param 的先验。

        Args:
            table_type: 桌型编码（例如 6）。

        Returns:
            `param_index -> GtoFamilyPrior` 映射。
        """

        repo = PreflopStrategyRepository(self._strategy_db_path)
        repo.connect()
        try:
            node_rows = self._load_solver_nodes(repo=repo)
            node_ids = tuple(int(row["node_id"]) for row in node_rows)
            actions_by_node = repo.get_actions_for_nodes(node_ids)
        finally:
            repo.close()

        aggregated: dict[int, _AggregatedPrior] = {}
        for row in node_rows:
            param_index = self._to_param_index(node_row=row, table_type=table_type)
            if param_index is None:
                continue
            node_id = int(row["node_id"])
            action_records = actions_by_node.get(node_id, ())
            if not action_records:
                continue
            node_prior, node_raise_score, node_weight, node_prior_kind = (
                self._build_node_prior(
                    action_records=action_records,
                    param_index=param_index,
                )
            )
            if node_weight <= 0.0:
                continue

            if param_index not in aggregated:
                aggregated[param_index] = _AggregatedPrior(
                    probs_sum=node_prior * node_weight,
                    raise_score_sum=node_raise_score * node_weight,
                    total_weight=node_weight,
                    prior_kind=node_prior_kind,
                )
                continue

            agg = aggregated[param_index]
            agg.probs_sum += node_prior * node_weight
            agg.raise_score_sum += node_raise_score * node_weight
            agg.total_weight += node_weight
            if node_prior_kind == "pseudo_call_from_raise_ev":
                agg.prior_kind = "pseudo_call_from_raise_ev"

        result: dict[int, GtoFamilyPrior] = {}
        for param_index, agg in aggregated.items():
            if agg.total_weight <= 0.0:
                continue
            probs_fcr = agg.probs_sum / agg.total_weight
            probs_fcr = _normalize_rows(probs_fcr)
            raise_score = agg.raise_score_sum / agg.total_weight
            result[param_index] = GtoFamilyPrior(
                table_type=table_type,
                param_index=param_index,
                probs_fcr=probs_fcr.astype(np.float32),
                raise_score=raise_score.astype(np.float32),
                prior_kind=agg.prior_kind,
            )
        return result

    def _load_solver_nodes(
        self,
        *,
        repo: PreflopStrategyRepository,
    ) -> list[sqlite3.Row]:
        """读取构建先验所需节点。"""

        cursor = repo.conn.cursor()
        cursor.execute(
            """
            SELECT
                node_id,
                actor_position,
                call_count,
                limp_count,
                raise_time
            FROM solver_nodes
            WHERE source_id = ?
              AND stack_bb = ?
              AND actor_position IS NOT NULL
            ORDER BY node_id ASC
            """,
            (self._source_id, self._stack_bb),
        )
        return list(cursor.fetchall())

    def _to_param_index(
        self,
        *,
        node_row: sqlite3.Row,
        table_type: int,
    ) -> int | None:
        """把 solver 节点上下文映射到 `PreFlopParams` 索引。"""

        actor_position_raw = str(node_row["actor_position"])
        metrics_position = _POSITION_TO_METRICS.get(actor_position_raw)
        if metrics_position is None:
            return None

        raises = int(node_row["raise_time"])
        callers = (
            int(node_row["limp_count"]) if raises == 0 else int(node_row["call_count"])
        )
        try:
            params = PreFlopParams(
                table_type=TableType(table_type),
                position=metrics_position,
                num_callers=min(max(callers, 0), 1),
                num_raises=min(max(raises, 0), 2),
                num_active_players=max(2, int(table_type)),
                previous_action=MetricsActionType.FOLD,
                in_position_on_flop=False,
            )
        except ValueError:
            return None
        return params.to_index()

    def _build_node_prior(
        self,
        *,
        action_records: tuple[SolverActionRecord, ...],
        param_index: int,
    ) -> tuple[np.ndarray, np.ndarray, float, PriorKind]:
        """把单个 solver 节点动作聚合为 family-level prior。"""

        probs_by_family = np.zeros((RANGE_169_LENGTH, 3), dtype=np.float64)
        family_total_frequency = np.zeros(3, dtype=np.float64)
        raise_evs: list[np.ndarray] = []
        raise_freqs: list[float] = []
        has_call_action = False
        node_weight = 0.0

        for action in action_records:
            family_index = _resolve_action_family_index(action)
            strategy, evs = action.preflop_range.to_list()
            action_strategy = np.array(strategy, dtype=np.float64)
            probs_by_family[:, family_index] += action_strategy
            family_total_frequency[family_index] += max(
                float(action.total_frequency), 0.0
            )
            node_weight += max(float(action.total_combos), 0.0)
            if family_index == _ACTION_FAMILY_INDEX["C"]:
                has_call_action = True
            if family_index == _ACTION_FAMILY_INDEX["R"]:
                raise_evs.append(np.array(evs, dtype=np.float64))
                raise_freqs.append(max(float(action.total_frequency), 1e-8))

        raise_score = compute_raise_score_from_actions(
            raise_evs=np.stack(raise_evs, axis=0)
            if raise_evs
            else np.zeros((0, RANGE_169_LENGTH)),
            raise_freqs=np.array(raise_freqs, dtype=np.float64),
        ).astype(np.float64)

        if has_call_action:
            return (
                _normalize_rows(probs_by_family),
                raise_score,
                max(node_weight, 1.0),
                "direct_gto",
            )

        family_total_sum = float(np.sum(family_total_frequency))
        if family_total_sum <= 0.0:
            empirical_mix = np.array([1.0, 0.0, 0.0], dtype=np.float64)
            solver_raise_share = 0.0
        else:
            empirical_mix = family_total_frequency / family_total_sum
            solver_raise_share = float(family_total_frequency[2] / family_total_sum)
        empirical_mix = self._empirical_mix_by_param.get(
            param_index,
            empirical_mix,
        )
        pseudo = build_pseudo_call_prior_from_raise_ev(
            raise_score=raise_score.astype(np.float32),
            combo_weights=self._combo_weights,
            empirical_mix_fcr=np.array(empirical_mix, dtype=np.float32),
            solver_raise_share=solver_raise_share,
        )
        return (
            pseudo.astype(np.float64),
            raise_score,
            max(node_weight, 1.0),
            "pseudo_call_from_raise_ev",
        )


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """对 `169x3` 矩阵做逐行归一化。"""

    row_sums = np.sum(matrix, axis=1, keepdims=True)
    zero_mask = row_sums[:, 0] <= 1e-8
    if np.any(zero_mask):
        matrix = matrix.copy()
        matrix[zero_mask, :] = np.array([1.0, 0.0, 0.0], dtype=np.float64)
        row_sums = np.sum(matrix, axis=1, keepdims=True)
    return matrix / row_sums


def _resolve_action_family_index(action: SolverActionRecord) -> int:
    """把动作记录映射到 `F/C/R` 家族索引。"""

    action_code = action.action_code.strip().upper()
    action_type = action.action_type.strip().upper()
    if action_code == "F" or action_type == "FOLD":
        return _ACTION_FAMILY_INDEX["F"]
    if action_code == "C" or action_type in {"CALL", "CHECK"}:
        return _ACTION_FAMILY_INDEX["C"]
    return _ACTION_FAMILY_INDEX["R"]
