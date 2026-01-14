use crate::{ActionType, Position, TableType};

#[derive(Debug, Clone)]
pub struct PreFlopParams {
    pub table_type: TableType,
    pub position: Position,
    pub num_callers: i32,
    pub num_raises: i32,
    pub num_active_players: i32,
    pub previous_action: ActionType,
    pub in_position_on_flop: bool,
}

impl PreFlopParams {
    pub fn new(
        table_type: TableType,
        position: Position,
        num_callers: i32,
        num_raises: i32,
        num_active_players: i32,
        previous_action: ActionType,
        in_position_on_flop: bool,
    ) -> Self {
        Self {
            table_type,
            position,
            num_callers,
            num_raises,
            num_active_players,
            previous_action,
            in_position_on_flop,
        }
    }

    pub fn to_index(&self) -> usize {
        if self.table_type == TableType::HeadsUp {
            if self.position == Position::SmallBlind {
                self.num_raises.min(4) as usize
            } else {
                5 + self.num_raises.min(4) as usize
            }
        } else if self.previous_action == ActionType::Fold {
            let a0 = self.position as usize;
            let a1 = match (self.num_raises, self.num_callers > 0) {
                (0, false) => 0,
                (0, true) => 1,
                (1, false) => 2,
                (1, true) => 3,
                _ => 4,
            };
            (5 * a0) + a1
        } else {
            let a0 = match self.previous_action {
                ActionType::Check | ActionType::Call => 0,
                _ => 1,
            };
            let a1 = if self.in_position_on_flop { 0 } else { 1 };
            let a2 = if self.num_active_players == 2 { 0 } else { 1 };
            let a3 = match (self.num_raises, self.num_callers > 0) {
                (1, false) => 0,
                (1, true) => 1,
                _ => 2,
            };
            30 + (12 * a0) + (6 * a1) + (3 * a2) + a3
        }
    }

    pub fn get_all_params_count(table_type: TableType) -> usize {
        if table_type == TableType::HeadsUp { 10 } else { 54 }
    }
}
