"""通信 payload 基类。"""

from __future__ import annotations

from dataclasses import asdict, fields
from typing import Any, Mapping, TypeVar


PayloadT = TypeVar("PayloadT", bound="PayloadBase")


class PayloadBase:
    """提供通用的 to_dict/from_dict 逻辑。"""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls: type[PayloadT], data: Mapping[str, Any]) -> PayloadT:
        field_names = {field.name for field in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in field_names})
