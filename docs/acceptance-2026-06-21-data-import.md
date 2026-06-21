# 2026-06-21 数据导入门禁验收记录

## Scope

研报摘要、小作文验证池、公告/交易所文件导入准备。

## Delivered

- `data_sources/_templates/research_report_event.template.json`
- `data_sources/_templates/xiaozuowen_event.template.json`
- `data_sources/_templates/announcement_event.template.json`
- `data_sources/announcements/.gitkeep`
- `scripts/validate_events.py`
- `docs/data-import-guide.md`

## Verified

- `python -m py_compile config.py data\event_loader.py scripts\validate_events.py scripts\health_check.py`
- `python scripts\validate_events.py`
- `python scripts\health_check.py`
- `python main.py`

## Result

通过。模板目录不参与报告生成，真实事件仍为 3 条；新增公告目录已进入事件加载链路。

## Next

- 真实公告/交易所文件抓取或导入索引。
- 研报摘要批量导入助手。
- 小作文验证状态追踪。
