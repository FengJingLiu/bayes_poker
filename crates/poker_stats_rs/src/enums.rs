#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum TableType {
    HeadsUp = 2,
    SixMax = 6,
}

impl TableType {
    pub fn from_u8(v: u8) -> Self {
        match v {
            2 => TableType::HeadsUp,
            _ => TableType::SixMax,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Street {
    PreFlop = 1,
    Flop = 2,
    Turn = 3,
    River = 4,
}

impl Street {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "preflop" => Street::PreFlop,
            "flop" => Street::Flop,
            "turn" => Street::Turn,
            "river" => Street::River,
            _ => Street::PreFlop,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum Position {
    SmallBlind = 0,
    BigBlind = 1,
    UTG = 2,
    HJ = 3,
    CutOff = 4,
    Button = 5,
}

impl Position {
    pub fn from_index(idx: usize, total: usize) -> Self {
        if total == 2 {
            if idx == 0 { Position::SmallBlind } else { Position::BigBlind }
        } else {
            match idx {
                0 => Position::SmallBlind,
                1 => Position::BigBlind,
                i if i == total - 1 => Position::Button,
                i if i == total - 2 => Position::CutOff,
                i if i == total - 3 => Position::HJ,
                _ => Position::UTG,
            }
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum ActionType {
    Fold = 0,
    Check = 1,
    Call = 2,
    Bet = 3,
    Raise = 4,
    AllIn = 5,
}

impl ActionType {
    pub fn from_str(s: &str) -> Self {
        match s.to_lowercase().as_str() {
            "fold" => ActionType::Fold,
            "check" => ActionType::Check,
            "call" => ActionType::Call,
            "bet" => ActionType::Bet,
            "raise" => ActionType::Raise,
            "allin" | "all_in" | "all-in" => ActionType::AllIn,
            _ => ActionType::Fold,
        }
    }
    
    pub fn is_raise_action(&self) -> bool {
        matches!(self, ActionType::Bet | ActionType::Raise | ActionType::AllIn)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
#[repr(u8)]
pub enum PreflopPotType {
    Limped = 0,
    #[default]
    SingleRaised = 1,
    ThreeBetPlus = 2,
}

impl PreflopPotType {
    pub fn from_raise_count(count: i32) -> Self {
        match count {
            0 => PreflopPotType::Limped,
            1 => PreflopPotType::SingleRaised,
            _ => PreflopPotType::ThreeBetPlus,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum BetSizingCategory {
    Bet0To40 = 0,
    Bet40To80 = 1,
    Bet80To120 = 2,
    BetOver120 = 3,
}

impl BetSizingCategory {
    pub fn from_pot_percentage(pct: f64) -> Self {
        if pct < 0.40 {
            BetSizingCategory::Bet0To40
        } else if pct < 0.80 {
            BetSizingCategory::Bet40To80
        } else if pct < 1.20 {
            BetSizingCategory::Bet80To120
        } else {
            BetSizingCategory::BetOver120
        }
    }
}
