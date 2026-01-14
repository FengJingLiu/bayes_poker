use crate::{ActionType, PreflopPotType, Street, TableType};

#[derive(Debug, Clone)]
pub struct PostFlopParams {
    pub table_type: TableType,
    pub street: Street,
    pub round: i32,
    pub prev_action: ActionType,
    pub num_bets: i32,
    pub in_position: bool,
    pub num_players: i32,
    pub preflop_pot_type: PreflopPotType,
    pub is_preflop_aggressor: bool,
}

impl PostFlopParams {
    pub fn new(
        table_type: TableType,
        street: Street,
        round: i32,
        prev_action: ActionType,
        num_bets: i32,
        in_position: bool,
        num_players: i32,
        preflop_pot_type: PreflopPotType,
        is_preflop_aggressor: bool,
    ) -> Self {
        Self {
            table_type,
            street,
            round,
            prev_action,
            num_bets,
            in_position,
            num_players,
            preflop_pot_type,
            is_preflop_aggressor,
        }
    }

    pub fn to_index(&self) -> usize {
        let prev_action_mod = match self.prev_action {
            ActionType::Bet | ActionType::Raise | ActionType::AllIn => 0,
            ActionType::Call => 1,
            ActionType::Check => 2,
            _ => 0,
        };

        let pot_type_val = self.preflop_pot_type as usize;
        let aggressor_val = if self.is_preflop_aggressor { 1 } else { 0 };

        if self.table_type == TableType::HeadsUp {
            let base_index = match self.street {
                Street::Flop => 0,
                Street::Turn => 15,
                Street::River => 30,
                _ => 0,
            };

            let street_offset = if self.in_position {
                if self.num_bets < 2 {
                    if self.num_bets == 0 { prev_action_mod } else { 3 + prev_action_mod }
                } else {
                    if self.num_bets == 2 { 6 } else { 7 }
                }
            } else {
                let mut idx = 8;
                idx += if self.num_bets == 0 {
                    prev_action_mod
                } else {
                    self.num_bets.min(4) as usize + 2
                };
                idx
            };

            base_index + street_offset + (45 * pot_type_val) + (45 * 3 * aggressor_val)
        } else {
            let a0 = match self.street {
                Street::Flop => 0,
                Street::Turn => 1,
                Street::River => 2,
                _ => 0,
            };
            let a1 = if self.round == 0 { 0 } else { 1 };
            let a3 = self.num_bets.min(2).max(0) as usize;
            let a4 = if self.in_position { 1 } else { 0 };
            let a5 = if self.num_players <= 2 { 0 } else { 1 };

            let base_idx = a5 + (2 * a4) + (4 * a3) + (12 * prev_action_mod) + (36 * a1) + (72 * a0);
            base_idx + (216 * pot_type_val) + (216 * 3 * aggressor_val)
        }
    }

    pub fn get_all_params_count(table_type: TableType) -> usize {
        if table_type == TableType::HeadsUp {
            45 * 3 * 2
        } else {
            216 * 3 * 2
        }
    }
}
