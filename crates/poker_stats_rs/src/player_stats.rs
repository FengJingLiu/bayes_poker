use byteorder::{LittleEndian, ReadBytesExt, WriteBytesExt};
use std::io::{Read, Write};
use crate::{ActionStats, PreFlopParams, PostFlopParams, TableType};

#[derive(Debug, Clone)]
pub struct PlayerStats {
    pub player_name: String,
    pub table_type: TableType,
    pub vpip_positive: i32,
    pub vpip_total: i32,
    pub preflop_stats: Vec<ActionStats>,
    pub postflop_stats: Vec<ActionStats>,
}

impl PlayerStats {
    pub fn new(player_name: String, table_type: TableType) -> Self {
        let preflop_count = PreFlopParams::get_all_params_count(table_type);
        let postflop_count = PostFlopParams::get_all_params_count(table_type);
        
        Self {
            player_name,
            table_type,
            vpip_positive: 0,
            vpip_total: 0,
            preflop_stats: vec![ActionStats::new(); preflop_count],
            postflop_stats: vec![ActionStats::new(); postflop_count],
        }
    }

    pub fn merge(&mut self, other: &PlayerStats) {
        self.vpip_positive += other.vpip_positive;
        self.vpip_total += other.vpip_total;
        
        for (i, stats) in other.preflop_stats.iter().enumerate() {
            if i < self.preflop_stats.len() {
                self.preflop_stats[i].append(stats);
            }
        }
        
        for (i, stats) in other.postflop_stats.iter().enumerate() {
            if i < self.postflop_stats.len() {
                self.postflop_stats[i].append(stats);
            }
        }
    }

    pub fn serialize<W: Write>(&self, writer: &mut W) -> std::io::Result<()> {
        let name_bytes = self.player_name.as_bytes();
        writer.write_u32::<LittleEndian>(name_bytes.len() as u32)?;
        writer.write_all(name_bytes)?;
        
        writer.write_u8(self.table_type as u8)?;
        writer.write_i32::<LittleEndian>(self.vpip_positive)?;
        writer.write_i32::<LittleEndian>(self.vpip_total)?;
        
        writer.write_u32::<LittleEndian>(self.preflop_stats.len() as u32)?;
        for stats in &self.preflop_stats {
            stats.serialize(writer)?;
        }
        
        writer.write_u32::<LittleEndian>(self.postflop_stats.len() as u32)?;
        for stats in &self.postflop_stats {
            stats.serialize(writer)?;
        }
        
        Ok(())
    }

    pub fn deserialize<R: Read>(reader: &mut R) -> std::io::Result<Self> {
        let name_len = reader.read_u32::<LittleEndian>()? as usize;
        let mut name_bytes = vec![0u8; name_len];
        reader.read_exact(&mut name_bytes)?;
        let player_name = String::from_utf8_lossy(&name_bytes).to_string();
        
        let table_type = TableType::from_u8(reader.read_u8()?);
        let vpip_positive = reader.read_i32::<LittleEndian>()?;
        let vpip_total = reader.read_i32::<LittleEndian>()?;
        
        let preflop_len = reader.read_u32::<LittleEndian>()? as usize;
        let mut preflop_stats = Vec::with_capacity(preflop_len);
        for _ in 0..preflop_len {
            preflop_stats.push(ActionStats::deserialize(reader)?);
        }
        
        let postflop_len = reader.read_u32::<LittleEndian>()? as usize;
        let mut postflop_stats = Vec::with_capacity(postflop_len);
        for _ in 0..postflop_len {
            postflop_stats.push(ActionStats::deserialize(reader)?);
        }
        
        Ok(Self {
            player_name,
            table_type,
            vpip_positive,
            vpip_total,
            preflop_stats,
            postflop_stats,
        })
    }

    pub fn to_binary(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        self.serialize(&mut buf).unwrap();
        buf
    }

    pub fn from_binary(data: &[u8]) -> std::io::Result<Self> {
        let mut cursor = std::io::Cursor::new(data);
        Self::deserialize(&mut cursor)
    }
}
