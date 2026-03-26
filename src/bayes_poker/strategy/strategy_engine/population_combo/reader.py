"""strategy_engine 运行时使用的 population combo reader stub。"""

from __future__ import annotations

from bayes_poker.strategy.strategy_engine.population_vb.contracts import (
    PopulationPosteriorBucket,
)
from bayes_poker.strategy.strategy_engine.population_vb.reader import (
    PopulationPosteriorReader,
)


class PopulationComboReader:
    """包装 `population_vb` reader, 供后续 runtime 接入。"""

    def __init__(self, artifact_path: str) -> None:
        """初始化 reader。

        Args:
            artifact_path: population `.npz` artifact 路径。
        """

        self._reader = PopulationPosteriorReader(artifact_path)

    def get(self, table_type: int, param_index: int) -> PopulationPosteriorBucket | None:
        """读取指定 `(table_type, param_index)` 的后验桶。

        Args:
            table_type: 桌型编码。
            param_index: 翻前参数索引。

        Returns:
            命中时返回后验桶, 否则返回 `None`。
        """

        return self._reader.get(table_type=table_type, param_index=param_index)
