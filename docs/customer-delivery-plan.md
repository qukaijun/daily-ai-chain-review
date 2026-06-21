# 客户交付计划

## 交付目标

第一版客户交付做到 V1 绿色免安装包：客户不需要 Codex，不需要理解代码；解压后可配置密钥、检查环境、一键生成 AI 产业链复盘、导出单文件 HTML，并能导出诊断包给服务方排障。

## 分阶段

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| V0 报告交付版 | 服务方生成单文件 HTML/PDF 发客户 | 已具备单文件 HTML |
| V1 绿色客户包 | 解压即用脚本、配置模板、诊断、报告导出 | 当前建设目标 |
| V2 本地工作台 | 浏览器 UI、配置管理、历史报告、诊断中心 | 后续 |
| V3 Windows 安装器 | 桌面快捷方式、开始菜单、卸载入口、升级包 | 后续 |

## V1 验收标准

- 新 Windows 机器安装 Python 后，解压客户包可运行。
- `01_install_dependencies.bat` 可安装依赖。
- `.env.local.example` 可复制为 `.env.local` 并配置客户自己的 Key。
- `02_check_environment.bat` 可生成快速诊断。
- `03_generate_review.bat` 可生成完整日报。
- `04_export_single_html.bat` 可导出可直接转发的单文件 HTML。
- `06_export_diagnostics.bat` 可生成不暴露密钥的诊断报告。
- 客户无需安装 Codex。

## 非目标

- 不做自动交易。
- 不承诺投资收益。
- 不把 API Key 写入包内。
- 不在 V1 内置完整 Python 运行时。
- 不做复杂权限系统和多客户 SaaS。
