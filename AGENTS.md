# Agent Guide
中文输出
pokerkit 文档:https://pokerkit.readthedocs.io/
使用logging日志库，在关键部分添加日志，src/bayes_poker/config/settings.py配置日志等级
## Project
- Python project managed with uv.
- Entry point: `main.py`.

## Environment
- Create and sync env: `uv sync`
- Run: `uv run python main.py`

## Dependencies
- Add a dependency: `uv add <package>`
- Update lockfile after edits: `uv sync`

## Notes
- Keep changes minimal and focused (KISS/YAGNI).
