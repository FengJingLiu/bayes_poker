"""翻前策略 JSON 解析器。

解析 GTOWizard 风格的翻前策略 JSON 文件。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from bayes_poker.domain.table import Position as TablePosition
from bayes_poker.strategy.preflop_engine.state import ActionFamily
from bayes_poker.strategy.preflop_parse.models import (
    STRATEGY_VECTOR_LENGTH,
    PreflopStrategy,
    StrategyAction,
    StrategyNode,
)
from bayes_poker.strategy.preflop_parse.records import (
    ParsedStrategyActionRecord,
    ParsedStrategyNodeRecord,
)
from bayes_poker.strategy.range import PreflopRange

LOGGER = logging.getLogger(__name__)

_FILENAME_PATTERN = re.compile(
    r"^(?P<strategy_name>.+?)_(?P<stack_bb>\d+)(?:_(?P<history>.+))?$"
)
_PREFLOP_ACTION_ORDER_6MAX: tuple[TablePosition, ...] = (
    TablePosition.UTG,
    TablePosition.MP,
    TablePosition.CO,
    TablePosition.BTN,
    TablePosition.SB,
    TablePosition.BB,
)
_PREFLOP_ACTION_ORDER_9MAX: tuple[TablePosition, ...] = (
    TablePosition.UTG,
    TablePosition.UTG1,
    TablePosition.MP,
    TablePosition.MP1,
    TablePosition.HJ,
    TablePosition.CO,
    TablePosition.BTN,
    TablePosition.SB,
    TablePosition.BB,
)
_POSTFLOP_POSITION_ORDER: tuple[TablePosition, ...] = (
    TablePosition.SB,
    TablePosition.BB,
    TablePosition.UTG,
    TablePosition.UTG1,
    TablePosition.MP,
    TablePosition.MP1,
    TablePosition.HJ,
    TablePosition.CO,
    TablePosition.BTN,
)


def parse_bet_size_from_code(code: str) -> float | None:
    """从行动代码中提取下注大小。

    Args:
        code: 行动代码，如 "R2", "R2.5", "RAI", "F", "C"

    Returns:
        下注大小（BB），如果无法解析则返回 None
    """
    if not code:
        return None
    if code.upper() == "RAI":
        return None
    if len(code) > 1 and code[0].upper() == "R":
        try:
            return float(code[1:])
        except ValueError:
            return None
    return None


def normalize_token(token: str) -> str:
    """标准化行动 token。

    Args:
        token: 原始 token，如 "R2.5", "RAI", "F", "C"

    Returns:
        标准化后的 token：R/C/F
    """
    if not token:
        return ""
    if token.upper() == "RAI":
        return "R"
    first = token[0].upper()
    if first in ("R", "C", "F"):
        return first
    return first


def split_history_tokens(history_full: str) -> list[str]:
    """按 '-' 分割行动历史。

    Args:
        history_full: 完整行动历史，如 "F-R2-R6.5-F-R17.5-R35-RAI-C"

    Returns:
        分割后的 token 列表
    """
    if not history_full or not history_full.strip():
        return []
    return [t.strip() for t in history_full.split("-") if t.strip()]


def parse_file_meta(strategy_name: str, file_name: str) -> tuple[int, str] | None:
    """从文件名中解析 stack_bb 和 history_full。

    文件名格式：{strategy_name}_{stack_bb}.json 或
               {strategy_name}_{stack_bb}_{history_full}.json

    Args:
        strategy_name: 策略名称，如 "Cash6m50zGeneral"
        file_name: 文件名（不含扩展名），如 "Cash6m50zGeneral_100_F-R2"

    Returns:
        (stack_bb, history_full) 元组，或 None 如果无法解析
    """
    if not file_name.startswith(strategy_name):
        return None

    suffix = file_name[len(strategy_name) :]
    if not suffix or suffix[0] != "_":
        return None

    suffix = suffix[1:]
    parts = suffix.split("_", 1)

    try:
        stack_bb = int(parts[0])
    except ValueError:
        return None

    history_full = parts[1] if len(parts) > 1 else ""
    return stack_bb, history_full


def _parse_vector(solution: dict[str, Any], property_name: str) -> list[float]:
    """解析策略/EV 向量。"""
    arr = solution.get(property_name)
    if not isinstance(arr, list):
        msg = f"缺少 {property_name} 数组"
        raise ValueError(msg)
    if len(arr) != STRATEGY_VECTOR_LENGTH:
        msg = f"{property_name} 长度 {len(arr)} != {STRATEGY_VECTOR_LENGTH}"
        raise ValueError(msg)
    return [float(v) for v in arr]


def _resolve_position(position_name: str) -> TablePosition | None:
    """将字符串位置解析为枚举.

    Args:
        position_name: 位置名称。

    Returns:
        对应的位置枚举；无法识别时返回 None。
    """

    for position in TablePosition:
        if position.value == position_name:
            return position
    return None


def _resolve_action_positions(
    *,
    actor_position: TablePosition,
    token_count: int,
) -> tuple[TablePosition, ...] | None:
    """解析历史 token 对应的行动位置序列.

    Args:
        actor_position: 当前待行动位置。
        token_count: 历史 token 数量。

    Returns:
        与历史 token 一一对应的位置序列；无法确定时返回 None。
    """

    for action_order in (_PREFLOP_ACTION_ORDER_6MAX, _PREFLOP_ACTION_ORDER_9MAX):
        if actor_position not in action_order:
            continue
        actor_index = action_order.index(actor_position)
        if actor_index != token_count:
            continue
        return action_order[:actor_index]
    return None


def _is_aggressive_token(token: str) -> bool:
    """判断 token 是否为激进行动.

    Args:
        token: 单个历史 token。

    Returns:
        是否为 raise / jam 类动作。
    """

    normalized_token = token.upper()
    return normalized_token == "RAI" or (
        normalized_token.startswith("R") and len(normalized_token) > 1
    )


def _extract_raise_size(token: str) -> float | None:
    """从历史 token 中提取加注尺度.

    Args:
        token: 单个历史 token。

    Returns:
        解析出的尺度；无法解析时返回 None。
    """

    normalized_token = token.upper()
    if normalized_token == "RAI":
        return 1000.0
    return parse_bet_size_from_code(normalized_token)


def _is_in_position(
    *,
    actor_position: TablePosition,
    aggressor_position: TablePosition,
) -> bool:
    """判断行动方相对 aggressor 是否有位置优势.

    Args:
        actor_position: 当前待行动位置。
        aggressor_position: 首个激进行动位置。

    Returns:
        如果当前行动方翻后位置更靠后则返回 True。
    """

    actor_index = _POSTFLOP_POSITION_ORDER.index(actor_position)
    aggressor_index = _POSTFLOP_POSITION_ORDER.index(aggressor_position)
    return actor_index > aggressor_index


def _derive_mapper_fields(
    *,
    acting_position: str,
    history_full: str,
) -> tuple[
    ActionFamily | None,
    TablePosition | None,
    TablePosition | None,
    int,
    int,
    float | None,
    bool | None,
]:
    """根据节点事实推导 mapper 匹配字段.

    Args:
        acting_position: 当前节点行动位置。
        history_full: 完整历史字符串。

    Returns:
        `(action_family, actor_position, aggressor_position, call_count, limp_count, raise_size_bb, is_in_position)`。
        对当前 mapper 不支持的节点形状, `action_family` 等关键字段返回 None。
    """

    actor_position = _resolve_position(acting_position)
    if actor_position is None:
        return (None, None, None, 0, 0, None, None)

    tokens = split_history_tokens(history_full)
    action_positions = _resolve_action_positions(
        actor_position=actor_position,
        token_count=len(tokens),
    )
    if action_positions is None:
        return (None, actor_position, None, 0, 0, None, None)

    aggressor_position: TablePosition | None = None
    call_count = 0
    limp_count = 0
    raise_size_bb: float | None = None

    for position, token in zip(action_positions, tokens, strict=True):
        normalized_token = token.upper()
        if normalized_token in {"F", "CHECK", "X"}:
            continue

        if normalized_token == "C":
            if aggressor_position is None:
                limp_count += 1
            else:
                call_count += 1
            continue

        if _is_aggressive_token(normalized_token):
            if aggressor_position is not None or limp_count > 0:
                return (None, actor_position, None, 0, 0, None, None)
            aggressor_position = position
            raise_size_bb = _extract_raise_size(normalized_token)
            continue

        return (None, actor_position, None, 0, 0, None, None)

    if aggressor_position is None:
        if limp_count > 0:
            return (
                ActionFamily.LIMP,
                actor_position,
                None,
                0,
                limp_count,
                None,
                None,
            )
        return (
            ActionFamily.OPEN,
            actor_position,
            None,
            0,
            0,
            None,
            None,
        )

    return (
        ActionFamily.CALL_VS_OPEN,
        actor_position,
        aggressor_position,
        call_count,
        limp_count,
        raise_size_bb,
        _is_in_position(
            actor_position=actor_position,
            aggressor_position=aggressor_position,
        ),
    )


def parse_strategy_node_records(
    *,
    data: dict[str, Any],
    stack_bb: int,
    history_full: str,
    source_file: str,
) -> tuple[ParsedStrategyNodeRecord, tuple[ParsedStrategyActionRecord, ...]] | None:
    """从 JSON 数据解析 sqlite 导入记录.

    Args:
        data: JSON 根对象。
        stack_bb: 筹码深度（BB 数）。
        history_full: 完整行动历史。
        source_file: 来源文件名。

    Returns:
        节点记录和动作记录；如果没有有效动作则返回 None。
    """

    solutions = data.get("solutions")
    if not isinstance(solutions, list) or len(solutions) == 0:
        return None

    actions: list[ParsedStrategyActionRecord] = []
    acting_position = ""

    for index, solution in enumerate(solutions):
        action_elem = solution.get("action")
        if not isinstance(action_elem, dict):
            continue

        acting_position = action_elem.get("position", "") or ""
        code = action_elem.get("code", "") or ""
        action_type = action_elem.get("type", "") or ""
        next_position = action_elem.get("next_position", "") or ""
        is_all_in = bool(action_elem.get("allin", False))
        bet_size = parse_bet_size_from_code(code)

        total_frequency = float(solution.get("total_frequency", 0.0))
        total_ev = float(solution.get("total_ev", 0.0))
        total_combos = float(solution.get("total_combos", 0.0))

        strategy_data = _parse_vector(solution, "strategy")
        evs_data = _parse_vector(solution, "evs")
        action_range = PreflopRange(strategy=strategy_data, evs=evs_data)

        actions.append(
            ParsedStrategyActionRecord(
                order_index=index,
                action_code=code,
                action_type=action_type,
                bet_size_bb=bet_size,
                is_all_in=is_all_in,
                total_frequency=total_frequency,
                next_position=next_position,
                preflop_range=action_range,
                total_ev=total_ev,
                total_combos=total_combos,
            )
        )

    if not actions:
        return None

    tokens = split_history_tokens(history_full)
    history_actions = "-".join(normalize_token(t) for t in tokens)
    (
        action_family,
        actor_position,
        aggressor_position,
        call_count,
        limp_count,
        raise_size_bb,
        is_in_position,
    ) = _derive_mapper_fields(
        acting_position=acting_position,
        history_full=history_full,
    )

    return (
        ParsedStrategyNodeRecord(
            stack_bb=stack_bb,
            history_full=history_full,
            history_actions=history_actions,
            history_token_count=len(tokens),
            acting_position=acting_position,
            source_file=source_file,
            action_family=action_family,
            actor_position=actor_position,
            aggressor_position=aggressor_position,
            call_count=call_count,
            limp_count=limp_count,
            raise_size_bb=raise_size_bb,
            is_in_position=is_in_position,
        ),
        tuple(actions),
    )


def parse_strategy_node(
    data: dict[str, Any], history_full: str, source_file: str
) -> StrategyNode | None:
    """从 JSON 数据解析策略节点。

    Args:
        data: JSON 根对象
        history_full: 行动历史
        source_file: 来源文件名

    Returns:
        解析后的 StrategyNode，或 None 如果数据无效
    """
    parsed_records = parse_strategy_node_records(
        data=data,
        stack_bb=0,
        history_full=history_full,
        source_file=source_file,
    )
    if parsed_records is None:
        return None

    node_record, action_records = parsed_records

    return StrategyNode(
        history_full=node_record.history_full,
        history_actions=node_record.history_actions,
        history_token_count=node_record.history_token_count,
        acting_position=node_record.acting_position,
        source_file=node_record.source_file,
        actions=tuple(
            StrategyAction(
                order_index=record.order_index,
                action_code=record.action_code,
                action_type=record.action_type,
                bet_size_bb=record.bet_size_bb,
                is_all_in=record.is_all_in,
                total_frequency=record.total_frequency,
                next_position=record.next_position,
                range=record.preflop_range,
                total_ev=record.total_ev,
                total_combos=record.total_combos,
            )
            for record in action_records
        ),
    )


def parse_strategy_file(
    file_path: Path, strategy_name: str
) -> tuple[int, StrategyNode] | None:
    """解析单个策略 JSON 文件。

    Args:
        file_path: JSON 文件路径
        strategy_name: 策略名称

    Returns:
        (stack_bb, StrategyNode) 元组，或 None 如果解析失败
    """
    file_name = file_path.stem
    meta = parse_file_meta(strategy_name, file_name)
    if meta is None:
        LOGGER.debug("跳过无法解析的文件名: %s", file_name)
        return None

    stack_bb, history_full = meta

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("解析文件 %s 失败: %s", file_path.name, exc)
        return None

    node = parse_strategy_node(data, history_full, file_path.name)
    if node is None:
        LOGGER.debug("文件 %s 未包含有效策略数据", file_name)
        return None

    return stack_bb, node


def parse_strategy_directory(strategy_dir: Path) -> PreflopStrategy:
    """解析一个策略目录下的所有 JSON 文件。

    Args:
        strategy_dir: 策略目录路径（如 preflop_strategy/Cash6m50zGeneral/）

    Returns:
        解析后的 PreflopStrategy 对象
    """
    strategy_name = strategy_dir.name
    strategy = PreflopStrategy(name=strategy_name, source_dir=str(strategy_dir))

    json_files = sorted(strategy_dir.glob("*.json"))
    LOGGER.info("开始解析策略 %s，共 %d 个文件", strategy_name, len(json_files))

    parsed_count = 0
    for file_path in json_files:
        result = parse_strategy_file(file_path, strategy_name)
        if result is not None:
            stack_bb, node = result
            strategy.add_node(stack_bb, node)
            parsed_count += 1

    LOGGER.info(
        "策略 %s 解析完成：%d 个文件，%d 个节点",
        strategy_name,
        parsed_count,
        strategy.node_count(),
    )
    return strategy


def parse_all_strategies(
    root_dir: Path, strategy_filters: list[str] | None = None
) -> list[PreflopStrategy]:
    """解析根目录下的所有策略。

    Args:
        root_dir: 策略根目录（包含多个策略子目录）
        strategy_filters: 可选的策略名称过滤列表

    Returns:
        解析后的 PreflopStrategy 列表
    """
    if not root_dir.is_dir():
        msg = f"策略目录不存在: {root_dir}"
        raise NotADirectoryError(msg)

    strategy_dirs = sorted(d for d in root_dir.iterdir() if d.is_dir())

    if strategy_filters:
        filter_set = set(strategy_filters)
        strategy_dirs = [d for d in strategy_dirs if d.name in filter_set]

    if not strategy_dirs:
        LOGGER.warning("未在目录 %s 中发现匹配的策略子目录", root_dir)
        return []

    strategies = []
    for strategy_dir in strategy_dirs:
        strategy = parse_strategy_directory(strategy_dir)
        if strategy.node_count() > 0:
            strategies.append(strategy)

    return strategies
