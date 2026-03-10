# Preflop Parse 子模块

GTOWizard 风格翻前策略解析子模块。**在 v2 中, 它不再承担运行时主查询路径**，而是主要负责：

1. 解析策略 JSON。
2. 预计算 mapper 所需字段。
3. 构建/重建 SQLite 策略库。

## 当前角色定位

### 保留的 v2 关键路径

- `parser.py`: 解析 JSON, 生成节点记录与动作记录。
- `records.py`: 定义导入 SQLite 所需的中间记录结构。
- `importer.py`: 把策略目录导入 SQLite, 当前 `format_version=2`, 且构建时采用**新库重建**语义。
- `loader.py`: 打开 SQLite 仓库并在 v2 路径上做 `format_version` 守卫。
- `serialization.py`: `PreflopRange` / EV blob 的序列化。

### 不再作为 v2 主链路的部分

- `query.py`: 旧的内存 fallback 查询器。
- `models.py` 中依赖 `PreflopStrategy` 的内存索引查询主路径。

## 文件职责

| 文件 | 当前职责 |
|------|----------|
| `parser.py` | 解析 GTOWizard JSON, 推导 `action_family/actor_position/aggressor_position/call_count/limp_count/raise_size_bb/is_in_position` |
| `records.py` | 定义 `ParsedStrategyNodeRecord` / `ParsedStrategyActionRecord` |
| `importer.py` | 以 `format_version=2` 重建 SQLite 库 |
| `loader.py` | 打开 sqlite 仓库并拒绝旧 format_version |
| `serialization.py` | 序列化/反序列化范围与 EV |
| `query.py` | 旧内存 query 参考实现, 不再是 v2 运行时主路径 |
| `models.py` | 旧内存策略对象, 保留兼容与参考用途 |

## v2 注意事项

- `strategy_engine` 运行时 **不得** import `preflop_parse.query`
- v2 允许继续复用 `parse_file_meta()`、`parse_strategy_node_records()` 等 ingest 逻辑
- 若 loader 发现任何 source 的 `format_version != 2`, 应 fail fast 并提示重建数据库

## 顶层导出

旧导出仍保留, 用于兼容与参考：

```python
STRATEGY_VECTOR_LENGTH, PreflopStrategy, StrategyAction, StrategyNode
normalize_token, parse_all_strategies, parse_bet_size_from_code
parse_file_meta, parse_strategy_directory, parse_strategy_file
parse_strategy_node, split_history_tokens
```

但请记住: **这些导出不再代表 v2 运行时主链路**。
