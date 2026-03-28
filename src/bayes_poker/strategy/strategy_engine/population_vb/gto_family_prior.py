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

# 42 维极简状态机 (Index 0~41)：各节点的人类大盘经验分布 [Fold, Call, Raise]
# 保证 F + C + R = 1.0。
# 用于在 GTO 缺少 Call 动作时，通过 Raise EV 平滑重构出合理的 Call 范围。
EMPIRICAL_MIX_BY_PARAM: dict[int, np.ndarray] = {
    # ==========================================
    # 🟢 阶段一：首次行动 First-In [0 ~ 20]
    # ==========================================
    # --- 率先入池 (RFI) 场景：基本只有 Raise/Fold，极小概率 Limp ---
    0: np.array([0.83, 0.02, 0.15], dtype=np.float64),  # 0: UTG RFI (赋予2%手滑Limp底噪)
    1: np.array([0.78, 0.02, 0.20], dtype=np.float64),  # 1: MP RFI
    4: np.array([0.70, 0.02, 0.28], dtype=np.float64),  # 4: CO RFI
    8: np.array([0.55, 0.02, 0.43], dtype=np.float64),  # 8: BTN Steal (高频偷盲)
    12: np.array([0.45, 0.15, 0.40], dtype=np.float64), # 12: SB vs BB (盲注战会有一部分Limp)

    # --- 面对前方 Limper(s)：出现隔离和同情跟注 ---
    2: np.array([0.70, 0.12, 0.18], dtype=np.float64),  # 2: MP 面对 Limp
    5: np.array([0.65, 0.15, 0.20], dtype=np.float64),  # 5: CO 面对 Limper
    9: np.array([0.50, 0.25, 0.25], dtype=np.float64),  # 9: BTN 面对 Limper (极爱便宜看翻牌)
    13: np.array([0.60, 0.25, 0.15], dtype=np.float64), # 13: SB 面对 Limper (补半盲)
    16: np.array([0.00, 0.70, 0.30], dtype=np.float64), # 16: BB 面对 Limper (【绝对法则】大盲免费Check，Fold率必须为0)

    # --- 面临单人 Open：防守节点，大盘有大量 Call ---
    3: np.array([0.82, 0.10, 0.08], dtype=np.float64),  # 3: MP 面对 Open (防守偏紧)
    6: np.array([0.72, 0.18, 0.10], dtype=np.float64),  # 6: CO 面对 Open
    10: np.array([0.60, 0.28, 0.12], dtype=np.float64), # 10: BTN 面对 Open (最高频平跟位)
    14: np.array([0.75, 0.12, 0.13], dtype=np.float64), # 14: SB 面对 Open
    17: np.array([0.55, 0.35, 0.10], dtype=np.float64), # 17: BB 面对 Open (大盲防守主力桶)

    # --- 面临 Open + Caller(s) (挤压位/Squeeze) ---
    7: np.array([0.75, 0.12, 0.13], dtype=np.float64),  # 7: CO Squeeze位
    11: np.array([0.65, 0.20, 0.15], dtype=np.float64), # 11: BTN Squeeze位
    15: np.array([0.78, 0.10, 0.12], dtype=np.float64), # 15: SB Squeeze位
    18: np.array([0.60, 0.30, 0.10], dtype=np.float64), # 18: BB Squeeze位

    # --- [降维合并] 还没入池就遭遇高压 3B/4B+ ---
    19: np.array([0.93, 0.03, 0.04], dtype=np.float64), # 19: CO/BTN 面临 3B/4B+ (后位高压防守)
    20: np.array([0.94, 0.03, 0.03], dtype=np.float64), # 20: 盲注位 面临 3B/4B+ (盲注高压防守)

    # ==========================================
    # 🟡 阶段二：被动重入池 Passive Re-entry [21 ~ 29]
    # ==========================================
    # --- hr=0 (Hero 之前 Limp/Check) ---
    21: np.array([0.45, 0.45, 0.10], dtype=np.float64), # 21: Limp 遇冷隔离(Iso), IP
    22: np.array([0.55, 0.35, 0.10], dtype=np.float64), # 22: Limp/Check 遇冷隔离, OOP
    23: np.array([0.88, 0.08, 0.04], dtype=np.float64), # 23: [黑洞合并] Limp 被隔离后又遭遇 3B+，极端疯狂

    # --- hr=1 (Hero 之前 Call Open) ---
    24: np.array([0.65, 0.30, 0.05], dtype=np.float64), # 24: 跟注后被冷挤压, IP
    25: np.array([0.75, 0.20, 0.05], dtype=np.float64), # 25: 跟注后被冷挤压, OOP
    26: np.array([0.60, 0.35, 0.05], dtype=np.float64), # 26: 跟注后被老面孔(React)挤压, IP (原Limper反打)
    27: np.array([0.70, 0.25, 0.05], dtype=np.float64), # 27: 跟注后被老面孔(React)挤压, OOP
    28: np.array([0.93, 0.05, 0.02], dtype=np.float64), # 28: [黑洞合并] CallOpen 后底池直接面临 4B+ (底池爆炸)

    # --- hr>=2 (Hero 之前 Call 3Bet+) ---
    29: np.array([0.87, 0.10, 0.03], dtype=np.float64), # 29: [黑洞合并] Call 3B+ 后底池面临 4B+ (修罗场，强行接推比例高)

    # ==========================================
    # 🔴 阶段三：主动重入 Active Re-entry [30 ~ 41]
    # ==========================================
    # --- hr=1 (Hero 之前 Open / Iso) ---
    30: np.array([0.45, 0.40, 0.15], dtype=np.float64), # 30: Open 遇冷 3B, IP (核心交火区：极爱 Flat 3B)
    31: np.array([0.55, 0.30, 0.15], dtype=np.float64), # 31: Open 遇冷 3B, OOP
    32: np.array([0.50, 0.35, 0.15], dtype=np.float64), # 32: Open 遇老面孔(Limp-RR陷阱) 3B, IP
    33: np.array([0.60, 0.25, 0.15], dtype=np.float64), # 33: Open 遇老面孔(Limp-RR陷阱) 3B, OOP
    34: np.array([0.82, 0.05, 0.13], dtype=np.float64), # 34: [位置合并] Open 遇天外冷 4B+ (位置优势被绝对牌力抹平)
    35: np.array([0.78, 0.08, 0.14], dtype=np.float64), # 35: [位置合并] Open 遇陷阱老面孔 4B+

    # --- hr=2 (Hero 之前 3Bet / Squeeze) ---
    36: np.array([0.60, 0.15, 0.25], dtype=np.float64), # 36: 3B 遇其他人冷 4B, IP
    37: np.array([0.65, 0.10, 0.25], dtype=np.float64), # 37: 3B 遇其他人冷 4B, OOP
    38: np.array([0.50, 0.25, 0.25], dtype=np.float64), # 38: 3B 遇原Open者 4B 反击, IP (最硬核的强强死磕区)
    39: np.array([0.60, 0.15, 0.25], dtype=np.float64), # 39: 3B 遇原Open者 4B 反击, OOP
    40: np.array([0.72, 0.05, 0.23], dtype=np.float64), # 40: [冷热位置全合并] 3B 遇 5B+ 全压炸锅 (纯极化：接推/反推 或 弃牌)

    # --- hr>=3 (Hero 之前 4Bet+) ---
    41: np.array([0.52, 0.08, 0.40], dtype=np.float64), # 41: [终极合并] 4B+ 遇 5B+ 终极摊牌对决 (底池赔率极度扭曲)
}

@dataclass
class _AggregatedPrior:
    """聚合中的临时状态。"""

    probs_sum: np.ndarray
    raise_score_sum: np.ndarray
    total_weight: float
    prior_kind: PriorKind

    def debug_str(self, *, top_n: int | None = None, sort_by: str = "raise") -> str:
        """将 probs_sum 和 raise_score_sum 以手牌字符串格式输出，便于调试。

        Args:
            top_n: 仅输出前 N 个手牌; None 表示输出全部 169 个。
            sort_by: 排序依据列, 可选 "fold" / "call" / "raise"。

        Returns:
            格式化调试字符串。
        """
        from bayes_poker.strategy.range.mappings import RANGE_169_ORDER

        col = {"fold": 0, "call": 1, "raise": 2}.get(sort_by, 2)
        indices = sorted(
            range(len(RANGE_169_ORDER)),
            key=lambda i: float(self.probs_sum[i, col]),
            reverse=True,
        )
        if top_n is not None:
            indices = indices[:top_n]
        tw, pk = self.total_weight, self.prior_kind
        lines: list[str] = [
            f"_AggregatedPrior(total_weight={tw:.2f}, prior_kind={pk!r})",
            "  probs_sum (hand: F / C / R) | raise_score_sum:",
        ]
        for i in indices:
            hand = RANGE_169_ORDER[i]
            f, c, r = self.probs_sum[i]
            rs = self.raise_score_sum[i]
            row = f"    {hand:<5}: F={f:.4f}  C={c:.4f}  R={r:.4f}  rs={rs:+.4f}"
            lines.append(row)
        return "\n".join(lines)


class GtoFamilyPriorBuilder:
    """从 strategy SQLite 构建 family-level 先验。"""

    def __init__(
        self,
        strategy_db_path: str,
        source_id: int,
        stack_bb: int = 100,
        empirical_mix_by_param: dict[int, np.ndarray] | None = EMPIRICAL_MIX_BY_PARAM,
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
                raise_time,
                is_in_position,
                previous_action,
                aggressor_first_in,
                hero_invest_raises
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

        raises = max(int(node_row["raise_time"]), 0)
        previous_action_token = str(node_row["previous_action"]).strip().upper()
        previous_action = _to_metrics_action(previous_action_token)
        if previous_action == MetricsActionType.FOLD:
            callers = int(node_row["limp_count"]) if raises == 0 else int(node_row["call_count"])
        else:
            callers = int(node_row["call_count"])
        try:
            params = PreFlopParams(
                table_type=TableType(table_type),
                position=metrics_position,
                num_callers=min(max(callers, 0), 1),
                num_raises=raises,
                num_active_players=max(2, int(table_type)),
                previous_action=previous_action,
                in_position_on_flop=bool(node_row["is_in_position"])
                if node_row["is_in_position"] is not None
                else False,
                aggressor_first_in=bool(node_row["aggressor_first_in"])
                if node_row["aggressor_first_in"] is not None
                else True,
                hero_invest_raises=max(int(node_row["hero_invest_raises"]), 0)
                if node_row["hero_invest_raises"] is not None
                else 0,
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


def _to_metrics_action(token: str) -> MetricsActionType:
    """将 `solver_nodes.previous_action` 映射为指标动作枚举。

    Args:
        token: 预处理后的动作 token，预期为 `F/C/R`。

    Returns:
        对应的指标动作类型；未知值回退为 `FOLD`。
    """

    if token == "R":
        return MetricsActionType.RAISE
    if token == "C":
        return MetricsActionType.CALL
    return MetricsActionType.FOLD


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
