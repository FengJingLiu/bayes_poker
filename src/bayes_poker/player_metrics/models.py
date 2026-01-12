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


@dataclass
class ActionStats:
    bet_raise_samples: int = 0
    check_call_samples: int = 0
    fold_samples: int = 0

    def add_sample(self, action_type: ActionType) -> None:
        if action_type == ActionType.FOLD:
            self.fold_samples += 1
        elif action_type in (ActionType.CALL, ActionType.CHECK):
            self.check_call_samples += 1
        elif action_type in (ActionType.ALL_IN, ActionType.BET, ActionType.RAISE):
            self.bet_raise_samples += 1

    def append(self, other: ActionStats) -> None:
        self.bet_raise_samples += other.bet_raise_samples
        self.check_call_samples += other.check_call_samples
        self.fold_samples += other.fold_samples

    def clear(self) -> None:
        self.bet_raise_samples = 0
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

    @property
    def total_hands(self) -> int:
        from .params import PreFlopParams

        total = 0
        all_params = PreFlopParams.get_all_params(self.table_type)
        for i, params in enumerate(all_params):
            if params.previous_action == ActionType.FOLD:
                total += self.preflop_stats[i].total_samples()
        return total

    def calculate_pfr(self) -> tuple[int, int]:
        from .params import PreFlopParams

        total_ad = ActionStats()
        all_params = PreFlopParams.get_all_params(self.table_type)
        for i, params in enumerate(all_params):
            if params.num_raises == 0:
                total_ad.append(self.preflop_stats[i])
        return total_ad.bet_raise_samples, total_ad.total_samples()

    def calculate_aggression(self) -> tuple[int, int]:
        from .params import PostFlopParams

        total_forced = ActionStats()
        total_unforced = ActionStats()
        all_params = PostFlopParams.get_all_params(self.table_type)
        for i, params in enumerate(all_params):
            if params.num_bets > 0:
                total_forced.append(self.postflop_stats[i])
            else:
                total_unforced.append(self.postflop_stats[i])
        raise_count = total_forced.bet_raise_samples + total_unforced.bet_raise_samples
        total_count = raise_count + total_forced.check_call_samples
        return raise_count, total_count

    def calculate_wtp(self) -> tuple[int, int]:
        from .params import PostFlopParams

        total_forced = ActionStats()
        all_params = PostFlopParams.get_all_params(self.table_type)
        for i, params in enumerate(all_params):
            if params.num_bets > 0:
                total_forced.append(self.postflop_stats[i])
        positive_count = total_forced.check_call_samples + total_forced.bet_raise_samples
        total_count = positive_count + total_forced.fold_samples
        return positive_count, total_count

    def __str__(self) -> str:
        return f"{self.player_name}, VPIP: {self.vpip}"
