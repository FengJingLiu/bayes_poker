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
            let raise_idx = self.num_raises.min(4) as usize;
            return if self.position == Position::SmallBlind {
                raise_idx
            } else {
                5 + raise_idx
            };
        }

        if self.previous_action == ActionType::Fold {
            // 阶段一: 首次行动 (First-in)
            let a0 = self.position as usize;
            let a1 = match (self.num_raises, self.num_callers > 0) {
                (0, false) => 0, // RFI (Unopened)
                (0, true) => 1,  // Facing Limper(s)
                (1, false) => 2, // Facing Open
                (1, true) => 3,  // Facing Open + Caller(s) (Squeeze 场景)
                _ => 4,          // Facing 3Bet/4Bet+
            };
            return (5 * a0) + a1;
        }

        // 阶段二: 二次行动 (Re-entry)

        // 动态设置 Base Offset
        let base_offset = match self.table_type {
            TableType::SixMax => 30, // 5 * 6
            _ => 50,
        };

        let a0 = match self.previous_action {
            ActionType::Check | ActionType::Call => 0, // 被动入池后重入
            _ => 1,                                    // 主动加注后重入
        };
        let a1 = if self.in_position_on_flop { 0 } else { 1 };

        // 消除幽灵桶, 对极端稀疏场景进行物理折叠
        let a_combined = if a0 == 0 {
            // 之前是 Call/Limp
            match self.num_raises {
                1 => {
                    let mw = if self.num_active_players > 2 { 1 } else { 0 };
                    let callers = if self.num_callers > 0 { 1 } else { 0 };
                    (mw * 2) + callers // 分配 0, 1, 2, 3
                }
                _ => 4, // 面临 Squeeze 或 3Bet+
            }
        } else {
            // 之前是 Bet/Raise (此时 num_raises 必然 >= 2)
            match self.num_raises {
                2 => {
                    let mw = if self.num_active_players > 2 { 1 } else { 0 };
                    let callers = if self.num_callers > 0 { 1 } else { 0 };
                    (mw * 2) + callers // 分配 0, 1, 2, 3
                }
                _ => 4, // 面临 4Bet/5Bet+
            }
        };

        // 维数: a0(2) * a1(2) * a_combined(5) = 20 个桶
        base_offset + (10 * a0) + (5 * a1) + a_combined
    }

    pub fn get_all_params_count(table_type: TableType) -> usize {
        match table_type {
            TableType::HeadsUp => 10,
            TableType::SixMax => 30 + 20, // 50
            _ => 100,
        }
    }
}
