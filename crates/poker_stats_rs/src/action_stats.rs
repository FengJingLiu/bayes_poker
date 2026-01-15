use crate::{ActionType, BetSizingCategory};
use byteorder::{LittleEndian, ReadBytesExt, WriteBytesExt};
use std::io::{Read, Write};

#[derive(Debug, Clone, Default)]
pub struct ActionStats {
    pub bet_0_40: i32,
    pub bet_40_80: i32,
    pub bet_80_120: i32,
    pub bet_over_120: i32,
    pub raise_samples: i32,
    pub check_call_samples: i32,
    pub fold_samples: i32,
}

impl ActionStats {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn bet_samples(&self) -> i32 {
        self.bet_0_40 + self.bet_40_80 + self.bet_80_120 + self.bet_over_120
    }

    pub fn bet_raise_samples(&self) -> i32 {
        self.bet_samples() + self.raise_samples
    }

    pub fn total_samples(&self) -> i32 {
        self.bet_raise_samples() + self.check_call_samples + self.fold_samples
    }

    pub fn add_sample(
        &mut self,
        action_type: ActionType,
        sizing_category: Option<BetSizingCategory>,
    ) {
        match action_type {
            ActionType::Fold => self.fold_samples += 1,
            ActionType::Check | ActionType::Call => self.check_call_samples += 1,
            ActionType::Bet | ActionType::Raise => match sizing_category {
                Some(BetSizingCategory::Bet0To40) => self.bet_0_40 += 1,
                Some(BetSizingCategory::Bet40To80) => self.bet_40_80 += 1,
                Some(BetSizingCategory::Bet80To120) => self.bet_80_120 += 1,
                Some(BetSizingCategory::BetOver120) => self.bet_over_120 += 1,
                None => self.raise_samples += 1,
            },
            ActionType::AllIn => self.raise_samples += 1,
        }
    }

    pub fn append(&mut self, other: &ActionStats) {
        self.bet_0_40 += other.bet_0_40;
        self.bet_40_80 += other.bet_40_80;
        self.bet_80_120 += other.bet_80_120;
        self.bet_over_120 += other.bet_over_120;
        self.raise_samples += other.raise_samples;
        self.check_call_samples += other.check_call_samples;
        self.fold_samples += other.fold_samples;
    }

    pub fn serialize<W: Write>(&self, writer: &mut W) -> std::io::Result<()> {
        writer.write_i32::<LittleEndian>(self.bet_0_40)?;
        writer.write_i32::<LittleEndian>(self.bet_40_80)?;
        writer.write_i32::<LittleEndian>(self.bet_80_120)?;
        writer.write_i32::<LittleEndian>(self.bet_over_120)?;
        writer.write_i32::<LittleEndian>(self.raise_samples)?;
        writer.write_i32::<LittleEndian>(self.check_call_samples)?;
        writer.write_i32::<LittleEndian>(self.fold_samples)?;
        Ok(())
    }

    pub fn deserialize<R: Read>(reader: &mut R) -> std::io::Result<Self> {
        Ok(Self {
            bet_0_40: reader.read_i32::<LittleEndian>()?,
            bet_40_80: reader.read_i32::<LittleEndian>()?,
            bet_80_120: reader.read_i32::<LittleEndian>()?,
            bet_over_120: reader.read_i32::<LittleEndian>()?,
            raise_samples: reader.read_i32::<LittleEndian>()?,
            check_call_samples: reader.read_i32::<LittleEndian>()?,
            fold_samples: reader.read_i32::<LittleEndian>()?,
        })
    }
}
