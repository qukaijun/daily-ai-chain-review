# 客户安装与使用说明

## 1. 环境要求

- Windows 10/11
- Python 3.11 或更高版本
- 可访问必要数据源的网络环境

## 2. 解压

将 `DailyAIChainReview-V1.zip` 解压到本地目录，例如：

```text
D:\DailyAIChainReview
```

路径尽量不要包含特殊符号。中文路径一般可用，但如遇到依赖安装问题，建议改到英文目录。

## 3. 安装依赖

双击：

```text
01_install_dependencies.bat
```

## 4. 配置密钥

复制：

```text
.env.local.example
```

重命名为：

```text
.env.local
```

填写客户自己的 `PERPLEXITY_API_KEY` 或 `DAA_LLM_API_KEY`。不需要的能力可以留空。

## 5. 检查环境

双击：

```text
02_check_environment.bat
```

## 6. 生成复盘

双击：

```text
03_generate_review.bat
```

如果网络或外部数据源不可用，可先用本地示例数据验证：

```text
03_generate_review_local_only.bat
```

## 7. 导出单文件 HTML

双击：

```text
04_export_single_html.bat
```

单文件报告输出到：

```text
output_files\share\
```

## 8. 查看报告

双击：

```text
05_open_reports.bat
```

## 9. 生成诊断包

遇到问题时双击：

```text
06_export_diagnostics.bat
```

将 `output_files\diagnostics\` 下最新的 `.txt` 和 `.json` 发给服务方。诊断脚本不会打印完整 API Key。
