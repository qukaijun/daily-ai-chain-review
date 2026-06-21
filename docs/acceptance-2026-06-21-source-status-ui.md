# 2026-06-21 数据源状态页面验收记录

## Scope

在 HTML 报告中展示数据源状态和事件 Provider。

## Delivered

- `output/html_renderer.py` 增加数据源状态表渲染。
- `templates/dashboard.html` 增加“数据源状态”模块。
- 事件影响表增加 `Provider/文件` 列。

## Verification

- `python -m py_compile output\html_renderer.py main.py`
- `python main.py`
- `python main.py --fetch-market`
- `python scripts\health_check.py`
- `python scripts\screenshot_report.py`
- `python scripts\check_secrets.py`

## Expected

- 未启用自动数据源时显示本地事件提示。
- 启用自动数据源时显示 provider、状态、证据层级、获取时间、数量、错误。
- 自动事件显示 provider，手工事件显示来源文件。

## Result

通过。最新报告已显示 `akshare_market`、`eastmoney_flash` 状态，并在事件表显示 `Provider/文件` 列。
