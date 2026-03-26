"""population_vb artifact reader。"""

from __future__ import annotations

from .artifact import load_population_artifact
from .contracts import PopulationPosteriorBucket


class PopulationPosteriorReader:
    """按 `(table_type, param_index)` 读取 population 后验。"""

    def __init__(self, artifact_path: str) -> None:
        """初始化 reader。

        Args:
            artifact_path: population `.npz` artifact 路径。
        """

        self._bucket_by_key = load_population_artifact(artifact_path)

    def get(
        self, table_type: int, param_index: int
    ) -> PopulationPosteriorBucket | None:
        """读取指定 bucket。

        Args:
            table_type: 桌型编码。
            param_index: 翻前参数索引。

        Returns:
            命中时返回 bucket, 否则返回 `None`。
        """

        return self._bucket_by_key.get((table_type, param_index))
