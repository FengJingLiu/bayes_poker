use crate::{ActionType, Street};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Action {
    pub street: String,
    pub player: String,
    #[serde(alias = "type", alias = "action_type")]
    pub action_type: String,
    #[serde(default)]
    pub amount: i64,
    #[serde(default)]
    pub pot_size_before: i64,
    #[serde(default)]
    pub call_amount: i64,
}

impl Action {
    pub fn get_street(&self) -> Street {
        Street::from_str(&self.street)
    }

    pub fn get_action_type(&self) -> ActionType {
        ActionType::from_str(&self.action_type)
    }

    pub fn get_pot_percentage(&self) -> Option<f64> {
        if self.pot_size_before <= 0 {
            return None;
        }
        let action_type = self.get_action_type();
        match action_type {
            ActionType::Bet => Some(self.amount as f64 / self.pot_size_before as f64),
            ActionType::Raise => {
                let raise_increment = self.amount - self.call_amount;
                if raise_increment <= 0 {
                    return None;
                }
                let pot_after_call = self.pot_size_before + self.call_amount;
                Some(raise_increment as f64 / pot_after_call as f64)
            }
            _ => None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hand {
    #[serde(default)]
    pub players: Vec<String>,
    #[serde(default)]
    pub actions: Vec<Action>,
    #[serde(default)]
    pub raw_actions: Vec<String>,
    #[serde(default)]
    pub blinds: Vec<i64>,
    #[serde(default)]
    pub antes: Vec<i64>,
}

impl Hand {
    pub fn get_player_index(&self, player_name: &str) -> Option<usize> {
        self.players.iter().position(|p| p == player_name)
    }
}
