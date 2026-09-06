# 工具模块

- `Tools-recommended.sgmodule`：推荐合集，包含 BoxJs、Script Hub（β）和 Sub-Store（β）。在 Surge 里只需添加这个文件。
- `boxjs.sgmodule`、`script-hub.sgmodule`、`sub-store.sgmodule`：保留的单独版本，适合只使用其中一项功能时安装。

## 前置条件

三个工具都依赖 Surge MITM 证书。Sub-Store 的默认跨域白名单、定时同步和落地测试参数沿用上游默认值；在写入订阅或 Gist 凭据前，请先确认你信任其脚本来源。

## 更新

这些文件由仓库的 `Update Surge Modules` 工作流每天检查并同步固定上游。同步失败不会覆盖当前模块。上游地址记录在 `.github/scripts/update_modules.py`。
