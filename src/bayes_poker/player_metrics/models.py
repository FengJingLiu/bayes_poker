from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .enums import ActionType, TableType

if TYPE_CHECKING:
    from .params import PostFlopParams, PreFlopParams


@dataclass
class StatValue:
    positive: int = 0
    total: int = 0

    def add_sample(self, is_positive: bool) -> None:
        self.total += 1
        if is_positive:
            self.positive += 1

    def append(self, other: StatValue) -> None:
        self.total += other.total
        self.positive += other.positive

    def to_float(self) -> float:
        return self.positive / self.total if self.total > 0 else 0.0

    def __str__(self) -> str:
        return f"{self.to_float():.2f} ({self.total})"


class BetSizingCategory:
    BET_0_40 = "bet_0_40"
    BET_40_80 = "bet_40_80"
    BET_80_120 = "bet_80_120"
    BET_OVER_120 = "bet_over_120"


@dataclass
class ActionStats:
    bet_0_40: int = 0
    bet_40_80: int = 0
    bet_80_120: int = 0
    bet_over_120: int = 0
    raise_samples: int = 0
    check_call_samples: int = 0
    fold_samples: int = 0

    @property
    def bet_samples(self) -> int:
        return self.bet_0_40 + self.bet_40_80 + self.bet_80_120 + self.bet_over_120

    @property
    def bet_raise_samples(self) -> int:
        return self.bet_samples + self.raise_samples

    def add_sample(
        self,
        action_type: ActionType,
        *,
        sizing_category: str | None = None,
    ) -> None:
        if action_type == ActionType.FOLD:
            self.fold_samples += 1
        elif action_type in (ActionType.CALL, ActionType.CHECK):
            self.check_call_samples += 1
        elif action_type in (ActionType.BET, ActionType.RAISE):
            if sizing_category == BetSizingCategory.BET_0_40:
                self.bet_0_40 += 1
            elif sizing_category == BetSizingCategory.BET_40_80:
                self.bet_40_80 += 1
            elif sizing_category == BetSizingCategory.BET_80_120:
                self.bet_80_120 += 1
            elif sizing_category == BetSizingCategory.BET_OVER_120:
                self.bet_over_120 += 1
            else:
                self.raise_samples += 1
        elif action_type == ActionType.ALL_IN:
            self.raise_samples += 1

    def append(self, other: ActionStats) -> None:
        self.bet_0_40 += other.bet_0_40
        self.bet_40_80 += other.bet_40_80
        self.bet_80_120 += other.bet_80_120
        self.bet_over_120 += other.bet_over_120
        self.raise_samples += other.raise_samples
        self.check_call_samples += other.check_call_samples
        self.fold_samples += other.fold_samples

    def clear(self) -> None:
        self.bet_0_40 = 0
        self.bet_40_80 = 0
        self.bet_80_120 = 0
        self.bet_over_120 = 0
        self.raise_samples = 0
        self.check_call_samples = 0
        self.fold_samples = 0

    def total_samples(self) -> int:
        return self.bet_raise_samples + self.check_call_samples + self.fold_samples

    def bet_raise_probability(self) -> float:
        total = self.total_samples()
        return self.bet_raise_samples / total if total > 0 else 1 / 3

    def check_call_probability(self) -> float:
        total = self.total_samples()
        return self.check_call_samples / total if total > 0 else 1 / 3

    def fold_probability(self) -> float:
        total = self.total_samples()
        return self.fold_samples / total if total > 0 else 1 / 3

    def bet_0_40_probability(self) -> float:
        total = self.bet_samples
        return self.bet_0_40 / total if total > 0 else 0.25

    def bet_40_80_probability(self) -> float:
        total = self.bet_samples
        return self.bet_40_80 / total if total > 0 else 0.25

    def bet_80_120_probability(self) -> float:
        total = self.bet_samples
        return self.bet_80_120 / total if total > 0 else 0.25

    def bet_over_120_probability(self) -> float:
        total = self.bet_samples
        return self.bet_over_120 / total if total > 0 else 0.25

    def __str__(self) -> str:
        return (
            f"BR: {self.bet_raise_probability():.2f}, "
            f"CC: {self.check_call_probability():.2f}, "
            f"FO: {self.fold_probability():.2f} [{self.total_samples()}]"
        )


@dataclass
class PlayerStats:
    player_name: str
    table_type: TableType
    vpip: StatValue = field(default_factory=StatValue)
    preflop_stats: list[ActionStats] = field(default_factory=list)
    postflop_stats: list[ActionStats] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.preflop_stats:
            from .params import PreFlopParams

            all_preflop = PreFlopParams.get_all_params(self.table_type)
            self.preflop_stats = [ActionStats() for _ in all_preflop]

        if not self.postflop_stats:
            from .params import PostFlopParams

            all_postflop = PostFlopParams.get_all_params(self.table_type)
            self.postflop_stats = [ActionStats() for _ in all_postflop]

    def get_preflop_stats(self, params: PreFlopParams) -> ActionStats:
        return self.preflop_stats[params.to_index()]

    def get_postflop_stats(self, params: PostFlopParams) -> ActionStats:
        return self.postflop_stats[params.to_index()]

    def __str__(self) -> str:
        return f"{self.player_name}, VPIP: {self.vpip}"
