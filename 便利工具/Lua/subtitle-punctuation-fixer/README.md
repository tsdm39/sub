# TSDM字幕组标点校正 / Subtitle Punctuation Fixer by Angel Animes

一个 Aegisub 自动化脚本，根据TSDM字幕组标点规范，批量修正字幕中的中日文标点格式

An Aegisub automation script that batch-fixes CJK punctuation in subtitles

---

## 功能 / Features

- 成对直引号 `""` 与中文弯引号 `“”` → `「」`
- 中文问号 `？` / 感叹号 `！` → 半角 `?` /`!`
- 省略号统一为 `…`（支持修改 `...`、`……`、`..` 等写法）
- 逗号 `，`句号 `。`顿号 `、` → 半角空格
- 全角空格 → 半角空格，连续空格自动合并
- 去除保留标点（`? ! 「 」 …`）前后多余空格
- 句中标点（`?` / `!`）后自动补一格空格，句末、省略号后除外
- 修正统计报告

每条规则均可在对话框中单独开关

All rules can be toggled individually in the dialog.

## 环境要求 / Requirements

- Aegisub 3.x（Automation 4 Lua）

## 安装 / Installation

1. 将 `punct_fix.lua` 复制到 `Aegisub\automation\autoload` 文件夹

2. 重启 Aegisub（或 **自动化 → 重新加载自动化脚本**）

   Copy `punct_fix.lua` into the `autoload` folder, then restart Aegisub
   (or use Automation → Reload Automation Scripts).

## 使用 / Usage

1. 选中要处理的字幕行（或准备处理全部行）

2. **自动化 → 标点校正**

3. 在对话框中选择处理范围与规则，点击确定

4. 处理完成后会显示修正统计；可用 **Ctrl+Z** 撤销

   Select the lines, run Automation → 标点校正, pick scope and rules, confirm.
   A statistics report is shown afterwards. Press **Ctrl+Z** to undo.

## 规则示例 / Rule Details Sample

| 规则 / Rule | 示例 / Example                          |
| --------- | ------------------------------------- |
| 引号转换      | `"台词"` / `“台词”` → `「台词」`              |
| 半角问号感叹号   | `本当？` → `本当?`                         |
| 省略号统一     | `待って...` → `待って…`                     |
| 逗号句号顿号    | `そう、でも。` → `そう でも`                    |
| 句中补空格     | `本当?そう` → `本当? そう`（`そうか…そう`、`行く?` 不补） |

## 注意 / Notes

- 脚本暂不支持自定义批处理，修改规则仅适用于TSDM字幕组标点规范
- Not currently supporting custom batch processing; rule modifications apply only to Angle Animes punctuation guidelines.
- 请自行校对处理结果，脚本不保证对所有文本格式都适用
- Results should be proofread; the script may not fit every text style.

## 许可 / License

MIT
