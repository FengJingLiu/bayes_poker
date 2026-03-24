#[derive(Debug, Default)]
pub struct StatisticsQueryService;

impl StatisticsQueryService {
    pub fn core_stats_sql() -> &'static str {
        r#"SELECT player_name, count() AS hands,
           avg(is_vpip) * 100.0 AS vpip_pct,
           avg(is_pfr) * 100.0 AS pfr_pct,
           avg(if(is_saw_flop = 1, is_winner, NULL)) * 100.0 AS wwsf_pct,
           avg(if(is_saw_flop = 1, is_went_to_showdown, NULL)) * 100.0 AS wtsd_pct,
           avg(if(is_went_to_showdown = 1, is_winner_at_showdown, NULL)) * 100.0 AS w_sd_pct
           FROM player_hand_facts
           WHERE player_name = ?
           GROUP BY player_name"#
    }
}
