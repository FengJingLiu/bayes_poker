use sha2::{Digest, Sha256};
use std::fmt::Write;

pub const HAND_HASH_LENGTH: usize = 32;

pub fn compute_hand_hash(players: &[String], actions: &[String]) -> String {
    let players_str = if players.is_empty() {
        String::new()
    } else {
        players.join("|")
    };
    let actions_str = if actions.is_empty() {
        String::new()
    } else {
        actions.join("|")
    };
    let content = format!("{}\n{}", players_str, actions_str);
    let mut hasher = Sha256::new();
    hasher.update(content.as_bytes());
    let digest = hasher.finalize();

    let mut hex = String::with_capacity(64);
    for byte in digest {
        let _ = write!(hex, "{:02x}", byte);
    }
    hex.truncate(HAND_HASH_LENGTH);
    hex
}
