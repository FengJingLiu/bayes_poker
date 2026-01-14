import pytest

from bayes_poker.player_metrics.enums import ActionType, Position, Street, TableType
from bayes_poker.player_metrics.models import ActionStats, BetSizingCategory, PlayerStats, StatValue
from bayes_poker.player_metrics.params import PostFlopParams, PreFlopParams
from bayes_poker.player_metrics.builder import (
    calculate_aggression,
    calculate_bet_sizing_category,
    calculate_pfr,
    calculate_total_hands,
    calculate_wtp,
)


class TestStatValue:
    def test_initial_values(self):
        sv = StatValue()
        assert sv.positive == 0
        assert sv.total == 0

    def test_add_positive_sample(self):
        sv = StatValue()
        sv.add_sample(True)
        assert sv.positive == 1
        assert sv.total == 1

    def test_add_negative_sample(self):
        sv = StatValue()
        sv.add_sample(False)
        assert sv.positive == 0
        assert sv.total == 1

    def test_to_float_empty(self):
        sv = StatValue()
        assert sv.to_float() == 0.0

    def test_to_float_with_samples(self):
        sv = StatValue(positive=3, total=10)
        assert sv.to_float() == pytest.approx(0.3)

    def test_append(self):
        sv1 = StatValue(positive=2, total=5)
        sv2 = StatValue(positive=3, total=7)
        sv1.append(sv2)
        assert sv1.positive == 5
        assert sv1.total == 12


class TestActionStats:
    def test_initial_values(self):
        ads = ActionStats()
        assert ads.bet_raise_samples == 0
        assert ads.check_call_samples == 0
        assert ads.fold_samples == 0

    def test_add_fold_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.FOLD)
        assert ads.fold_samples == 1
        assert ads.total_samples() == 1

    def test_add_call_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.CALL)
        assert ads.check_call_samples == 1

    def test_add_check_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.CHECK)
        assert ads.check_call_samples == 1

    def test_add_raise_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.RAISE)
        assert ads.raise_samples == 1
        assert ads.bet_raise_samples == 1

    def test_add_bet_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.BET)
        assert ads.bet_over_100 == 1
        assert ads.bet_samples == 1
        assert ads.bet_raise_samples == 1

    def test_add_all_in_sample(self):
        ads = ActionStats()
        ads.add_sample(ActionType.ALL_IN)
        assert ads.raise_samples == 1
        assert ads.bet_raise_samples == 1

    def test_probabilities_empty(self):
        ads = ActionStats()
        assert ads.bet_raise_probability() == pytest.approx(1 / 3)
        assert ads.check_call_probability() == pytest.approx(1 / 3)
        assert ads.fold_probability() == pytest.approx(1 / 3)

    def test_probabilities_with_samples(self):
        ads = ActionStats(raise_samples=10, check_call_samples=5, fold_samples=5)
        assert ads.bet_raise_probability() == pytest.approx(0.5)
        assert ads.check_call_probability() == pytest.approx(0.25)
        assert ads.fold_probability() == pytest.approx(0.25)

    def test_append(self):
        ads1 = ActionStats(raise_samples=2, check_call_samples=3, fold_samples=4)
        ads2 = ActionStats(raise_samples=1, check_call_samples=2, fold_samples=3)
        ads1.append(ads2)
        assert ads1.bet_raise_samples == 3
        assert ads1.check_call_samples == 5
        assert ads1.fold_samples == 7

    def test_clear(self):
        ads = ActionStats(raise_samples=5, check_call_samples=3, fold_samples=2)
        ads.clear()
        assert ads.total_samples() == 0


class TestPreFlopParams:
    def test_get_all_params_six_max_count(self):
        params = PreFlopParams.get_all_params(TableType.SIX_MAX)
        assert len(params) == 30

    def test_get_all_params_heads_up_count(self):
        params = PreFlopParams.get_all_params(TableType.HEADS_UP)
        assert len(params) == 10

    def test_to_index_first_action_sb(self):
        params = PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=Position.SMALL_BLIND,
            num_callers=0,
            num_raises=0,
            num_active_players=6,
            previous_action=ActionType.FOLD,
            in_position_on_flop=False,
        )
        assert params.to_index() == 0

    def test_to_index_bb_one_raise(self):
        params = PreFlopParams(
            table_type=TableType.SIX_MAX,
            position=Position.BIG_BLIND,
            num_callers=0,
            num_raises=1,
            num_active_players=6,
            previous_action=ActionType.FOLD,
            in_position_on_flop=False,
        )
        assert params.to_index() == 7

    def test_to_index_all_unique(self):
        params_list = PreFlopParams.get_all_params(TableType.SIX_MAX)
        indices = [p.to_index() for p in params_list]
        assert len(indices) == len(set(indices))


class TestPostFlopParams:
    def test_get_all_params_six_max_count(self):
        params = PostFlopParams.get_all_params(TableType.SIX_MAX)
        assert len(params) == 216

    def test_get_all_params_heads_up_count(self):
        params = PostFlopParams.get_all_params(TableType.HEADS_UP)
        assert len(params) == 45

    def test_to_index_flop_first_action(self):
        params = PostFlopParams(
            table_type=TableType.SIX_MAX,
            street=Street.FLOP,
            round=0,
            prev_action=ActionType.RAISE,
            num_bets=0,
            in_position=False,
            num_players=2,
        )
        assert params.to_index() == 0

    def test_to_index_all_unique(self):
        params_list = PostFlopParams.get_all_params(TableType.SIX_MAX)
        indices = [p.to_index() for p in params_list]
        assert len(indices) == len(set(indices))


class TestPlayerStats:
    def test_initialization(self):
        stats = PlayerStats(player_name="Hero", table_type=TableType.SIX_MAX)
        assert stats.player_name == "Hero"
        assert stats.table_type == TableType.SIX_MAX
        assert len(stats.preflop_stats) == 30
        assert len(stats.postflop_stats) == 216
        assert stats.vpip.total == 0

    def test_calculate_pfr_empty(self):
        stats = PlayerStats(player_name="Hero", table_type=TableType.SIX_MAX)
        positive, total = calculate_pfr(stats)
        assert positive == 0
        assert total == 0

    def test_calculate_aggression_empty(self):
        stats = PlayerStats(player_name="Hero", table_type=TableType.SIX_MAX)
        positive, total = calculate_aggression(stats)
        assert positive == 0
        assert total == 0

    def test_calculate_wtp_empty(self):
        stats = PlayerStats(player_name="Hero", table_type=TableType.SIX_MAX)
        positive, total = calculate_wtp(stats)
        assert positive == 0
        assert total == 0


class TestBetSizingCategory:
    def test_bet_sizing_small_bet(self):
        category = calculate_bet_sizing_category(30, 100)
        assert category == BetSizingCategory.BET_0_33

    def test_bet_sizing_medium_bet(self):
        category = calculate_bet_sizing_category(50, 100)
        assert category == BetSizingCategory.BET_33_66

    def test_bet_sizing_large_bet(self):
        category = calculate_bet_sizing_category(75, 100)
        assert category == BetSizingCategory.BET_66_100

    def test_bet_sizing_over_pot(self):
        category = calculate_bet_sizing_category(150, 100)
        assert category == BetSizingCategory.BET_OVER_100

    def test_bet_sizing_pot_sized(self):
        category = calculate_bet_sizing_category(100, 100)
        assert category == BetSizingCategory.BET_OVER_100

    def test_bet_sizing_zero_pot(self):
        category = calculate_bet_sizing_category(50, 0)
        assert category == BetSizingCategory.BET_OVER_100

    def test_bet_sizing_boundary_33(self):
        category = calculate_bet_sizing_category(33, 100)
        assert category == BetSizingCategory.BET_33_66

    def test_bet_sizing_boundary_66(self):
        category = calculate_bet_sizing_category(66, 100)
        assert category == BetSizingCategory.BET_66_100

    def test_add_sample_with_sizing_categories(self):
        ads = ActionStats()
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_0_33)
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_33_66)
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_66_100)
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_OVER_100)
        
        assert ads.bet_0_33 == 1
        assert ads.bet_33_66 == 1
        assert ads.bet_66_100 == 1
        assert ads.bet_over_100 == 1
        assert ads.bet_samples == 4
        assert ads.bet_raise_samples == 4

    def test_backward_compatibility_bet_raise_samples(self):
        ads = ActionStats()
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_33_66)
        ads.add_sample(ActionType.BET, sizing_category=BetSizingCategory.BET_33_66)
        ads.add_sample(ActionType.RAISE)
        ads.add_sample(ActionType.RAISE)
        ads.add_sample(ActionType.RAISE)
        
        assert ads.bet_samples == 2
        assert ads.raise_samples == 3
        assert ads.bet_raise_samples == 5


class TestParsedActionPotPercentage:
    def test_bet_pot_percentage(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.BET,
            amount=50,
            pot_size_before_action=100,
            call_amount=0,
        )
        assert action.pot_percentage == pytest.approx(0.5)

    def test_raise_pot_percentage(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.RAISE,
            amount=300,
            pot_size_before_action=100,
            call_amount=100,
        )
        assert action.pot_percentage == pytest.approx(1.0)

    def test_raise_pot_percentage_small_raise(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.RAISE,
            amount=150,
            pot_size_before_action=150,
            call_amount=50,
        )
        assert action.pot_percentage == pytest.approx(0.5)

    def test_raise_pot_percentage_small_raise_1(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.RAISE,
            amount=150,
            pot_size_before_action=150,
            call_amount=50,
        )
        assert action.pot_percentage == pytest.approx(0.5)

    def test_fold_returns_none(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.FOLD,
            amount=0,
            pot_size_before_action=100,
            call_amount=0,
        )
        assert action.pot_percentage is None

    def test_call_returns_none(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.CALL,
            amount=50,
            pot_size_before_action=100,
            call_amount=50,
        )
        assert action.pot_percentage is None

    def test_zero_pot_returns_none(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.BET,
            amount=50,
            pot_size_before_action=0,
            call_amount=0,
        )
        assert action.pot_percentage is None

    def test_raise_no_increment_returns_none(self):
        from bayes_poker.player_metrics.builder import ParsedAction
        
        action = ParsedAction(
            street=Street.FLOP,
            player_name="Hero",
            action_type=ActionType.RAISE,
            amount=100,
            pot_size_before_action=100,
            call_amount=100,
        )
        assert action.pot_percentage is None
