#[derive(Debug, Default)]
pub struct StatisticsQueryService;

impl StatisticsQueryService {
    /// 返回核心玩家统计 SQL。
    ///
    /// Returns:
    ///     用于按玩家聚合 VPIP/PFR/WWSF/WTSD/WSD 的 SQL 语句。
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

    /// 返回翻前 population 动作总量 SQL。
    ///
    /// Returns:
    ///     以 `(table_type, preflop_param_index, action_family)` 聚合的 SQL 语句。
    pub fn preflop_population_action_totals_sql() -> &'static str {
        r#"SELECT
    h.table_type,
    pa.preflop_param_index,
    multiIf(
        pa.action_type = 0, 'F',
        pa.action_type IN (1, 2), 'C',
        pa.action_type IN (3, 4, 5), 'R',
        'X'
    ) AS action_family,
    count() AS n_total
FROM player_actions pa
INNER JOIN hands h USING (hand_hash)
WHERE pa.street = 1
  AND pa.preflop_param_index IS NOT NULL
GROUP BY
    h.table_type,
    pa.preflop_param_index,
    action_family
HAVING action_family IN ('F', 'C', 'R')"#
    }

    /// 返回翻前已暴露底牌组合计数 SQL。
    ///
    /// Returns:
    ///     以 `(table_type, preflop_param_index, action_family, holdcard_index)` 聚合的 SQL 语句。
    pub fn preflop_population_exposed_combo_counts_sql() -> &'static str {
        r#"SELECT
    h.table_type,
    pa.preflop_param_index,
    multiIf(
        pa.action_type = 0, 'F',
        pa.action_type IN (1, 2), 'C',
        pa.action_type IN (3, 4, 5), 'R',
        'X'
    ) AS action_family,
    phf.holdcard_index,
    count() AS n_exposed
FROM player_actions pa
INNER JOIN hands h USING (hand_hash)
INNER JOIN player_hand_facts phf
    ON pa.hand_hash = phf.hand_hash
   AND pa.player_name = phf.player_name
WHERE pa.street = 1
  AND pa.preflop_param_index IS NOT NULL
  AND phf.holdcard_index IS NOT NULL
GROUP BY
    h.table_type,
    pa.preflop_param_index,
    action_family,
    phf.holdcard_index
HAVING action_family IN ('F', 'C', 'R')"#
    }

}

#[cfg(test)]
mod tests {
    use super::StatisticsQueryService;

    #[test]
    fn preflop_population_action_totals_sql_maps_action_family_correctly() {
        let sql = StatisticsQueryService::preflop_population_action_totals_sql();
        assert!(sql.contains("pa.action_type = 0, 'F'"));
        assert!(sql.contains("pa.action_type IN (1, 2), 'C'"));
        assert!(sql.contains("pa.action_type IN (3, 4, 5), 'R'"));
        assert!(sql.contains("HAVING action_family IN ('F', 'C', 'R')"));
    }

    #[test]
    fn preflop_population_exposed_combo_counts_sql_joins_holdcards_correctly() {
        let sql = StatisticsQueryService::preflop_population_exposed_combo_counts_sql();
        assert!(sql.contains("INNER JOIN player_hand_facts phf"));
        assert!(sql.contains("pa.hand_hash = phf.hand_hash"));
        assert!(sql.contains("pa.player_name = phf.player_name"));
        assert!(sql.contains("phf.holdcard_index IS NOT NULL"));
    }
}
