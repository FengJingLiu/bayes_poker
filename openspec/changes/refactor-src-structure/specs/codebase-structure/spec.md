## ADDED Requirements

### Requirement: 源码包结构精简
系统 SHALL 保持 `src/bayes_poker` 仅包含可导入运行代码，不包含构建产物、缓存与开发笔记文件。

#### Scenario: 构建/发布包
- **WHEN** 构建或发布 Python 包
- **THEN** `src/bayes_poker` 内不包含 `__pycache__` 与 `*.egg-info`

#### Scenario: 开发笔记隔离
- **WHEN** 存放 Jupyter 笔记
- **THEN** 笔记文件不位于 `src/bayes_poker` 下

### Requirement: 通信 payload 序列化复用
系统 SHALL 为通信 payload 提供统一的 `to_dict/from_dict` 复用机制，以减少重复实现。

#### Scenario: Payload 序列化
- **WHEN** 任意 payload 调用 `to_dict()`
- **THEN** 返回包含其 dataclass 字段的字典
