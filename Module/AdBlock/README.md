# 应用净化模块

推荐直接使用 [`AdBlock-recommended.sgmodule`](./AdBlock-recommended.sgmodule)，其中整合并去重了以下 Surge 模块：

- Google 搜索重定向
- 微信公众号去广告
- 微信小程序去广告
- 淘宝去广告
- 高德地图去广告
- 闲鱼去广告
- 微信外部链接解锁

Soul 去广告保留为独立模块，不纳入推荐合集。

Google、Soul、微信、淘宝和高德优先同步 QingRex/LoonKissSurge 的原生 Surge 版本；闲鱼规则由 ddgksf2013 的 Quantumult X 配置在更新时确定性转换为 Surge 的 Rule、URL Rewrite、Body Rewrite、Script 与 MITM 段。转换过程不会依赖 Script Hub 在线转换服务。

同步程序会统一移除 Loon 专属版本标记、修正重复脚本名称、去除完全重复条目并校验 MITM、远程脚本白名单及本地镜像脚本语法。更新先在临时目录完成，全部验证通过后才替换仓库内容。

> 使用前请在 Surge 中安装并信任 MITM 证书。此合集包含 `Body Rewrite` 的 JQ 规则，需要支持该功能的 Surge 版本。若同时安装本合集和其中的单项模块，会产生重复匹配，建议二选一。
