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
    pub aggressor_first_in: bool,
    pub hero_invest_raises: i32,
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
        aggressor_first_in: bool,
        hero_invest_raises: i32,
    ) -> Self {
        Self {
            table_type,
            position,
            num_callers,
            num_raises,
            num_active_players,
            previous_action,
            in_position_on_flop,
            aggressor_first_in,
            hero_invest_raises,
        }
    }

    /// 将当前参数映射为统计数组下标, 幽灵节点(不可能场景)返回 `usize::MAX`.
    pub fn to_index(&self) -> usize {
        if self.table_type != TableType::SixMax {
            return usize::MAX;
        }

        let r = self.num_raises;
        let c = if self.num_callers > 0 { 1 } else { 0 };

        if self.previous_action == ActionType::Fold {
            // 阶段一: 首次行动 (First-in), 21 个合法桶.
            if r >= 2 {
                return match self.position {
                    Position::CutOff | Position::Button => 19,
                    Position::SmallBlind | Position::BigBlind => 20,
                    _ => usize::MAX,
                };
            }

            return match self.position {
                Position::UTG => {
                    if r == 0 && c == 0 {
                        0
                    } else {
                        usize::MAX
                    }
                }
                Position::HJ => {
                    if r == 0 {
                        (1 + c) as usize
                    } else if r == 1 {
                        3
                    } else {
                        usize::MAX
                    }
                }
                Position::CutOff => match (r, c) {
                    (0, 0) => 4,
                    (0, 1) => 5,
                    (1, 0) => 6,
                    (1, 1) => 7,
                    _ => usize::MAX,
                },
                Position::Button => match (r, c) {
                    (0, 0) => 8,
                    (0, 1) => 9,
                    (1, 0) => 10,
                    (1, 1) => 11,
                    _ => usize::MAX,
                },
                Position::SmallBlind => match (r, c) {
                    (0, 0) => 12,
                    (0, 1) => 13,
                    (1, 0) => 14,
                    (1, 1) => 15,
                    _ => usize::MAX,
                },
                Position::BigBlind => {
                    if r == 0 && c == 1 {
                        16
                    } else if r == 1 {
                        (17 + c) as usize
                    } else {
                        usize::MAX
                    }
                }
            };
        }

        // 阶段二: 重入池 (Re-entry), 21 个战术桶.
        let is_oop = if self.in_position_on_flop { 0 } else { 1 };
        let is_react = if self.aggressor_first_in { 0 } else { 1 };
        let hr = self.hero_invest_raises;

        if r <= hr {
            return usize::MAX;
        }

        match self.previous_action {
            ActionType::Check | ActionType::Call => {
                // 1. 被动重入 (Passive), 9 桶.
                let hr = hr.clamp(0, 2);
                let base = 21usize;
                if hr == 0 {
                    if r == 1 {
                        base + is_oop // 21,22
                    } else {
                        base + 2 // 23
                    }
                } else if hr == 1 {
                    if r == 2 {
                        base + 3 + (is_react * 2) + is_oop // 24..27
                    } else {
                        base + 7 // 28
                    }
                } else {
                    base + 8 // 29
                }
            }
            _ => {
                // 2. 主动重入 (Active), 12 桶.
                let hr = hr.clamp(1, 3);
                let base = 30usize;
                if hr == 1 {
                    if r == 2 {
                        base + (is_react * 2) + is_oop // 30..33
                    } else {
                        base + 4 + is_react // 34,35
                    }
                } else if hr == 2 {
                    if r == 3 {
                        base + 6 + (is_react * 2) + is_oop // 36..39
                    } else {
                        base + 10 // 40
                    }
                } else {
                    base + 11 // 41
                }
            }
        }
    }

    pub fn get_all_params_count(table_type: TableType) -> usize {
        match table_type {
            TableType::HeadsUp => 0,
            TableType::SixMax => 42,
        }
    }
}
