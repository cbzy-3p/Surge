# Apple 下载规则

`AppleDownload.list` 用于 App Store / Mac App Store 安装包、应用更新、系统 OTA、IPSW 与恢复系统下载、运营商配置包、开发者工具下载和 Apple 资源下载（含 GarageBand 音色、Xcode 组件、Swift Playground、航拍屏保与壁纸）。保留更新目录与下载调度端点。规则基于域名，无法保证识别未来新增域名或第三方 App 自有服务器中的下载。

## 来源与边界

按 SukkaW、blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier、Yuu518 的现有 Apple 来源顺序检查。SukkaW 使用现行 `domainset/apple_cdn.conf`；旧 `non_ip/apple_cdn.conf` 已废弃，且 CDN 集合本身还含账号、证书、地图等服务，不能整份导入。其他来源也只提取已审阅的下载域名及其专用 CDN 别名，不因关键词包含 Apple 或 download 就直接加入。

Apple 官方基准为 [企业网络端点清单](https://support.apple.com/en-us/101555) 的 Software updates、Carrier updates 与 App Store 部分。系统下载、恢复、更新目录及 Rosetta 端点作为固定底线保留；开发者与媒体下载端点由上述固定上游交叉补充。所有来源地址写入规则头，拉取量和筛选量写入 `.github/apple-download-source-snapshot.json`。通用总集中被 `apple.com` 覆盖而省略的精确端点不能用总集压缩结果反推，因此此脚本读取原始上游。

不导入整个 `apple.com`、`cdn-apple.com`、`itunes.apple.com`、`apps.apple.com`、Akamai / Cloudflare IP 段。账号、购买、StoreKit、地区检测、签名与 DRM 仍使用现有 Apple 策略；`gs.apple.com` 等恢复签名依赖不属于下载数据端点，故需保留现有 Apple 总集。iCloud 照片、云盘和备份继续由 `iCloud.list` 负责。

`mzstatic.com` 同时提供商店图片和媒体资源。音频、视频下载与在线播放共用部分域名，域名规则无法按离线下载与播放动作进一步区分。Apple Music / Apple TV 若要使用独立策略，应把对应专项放在此规则之前。第三方 App 安装后的游戏资源包不一定由 Apple 提供，不纳入保证范围。

## 使用

放在 `Apple.list`、China、CN-Additional、Proxy 和 FINAL 前面。现有 App Store 地区检测规则继续优先；如有不同策略的 AppleMusic / AppleTV，也放在此规则前面。推荐下载数据直连，按需要将 `DIRECT` 改成自己的策略组。

```ini
RULE-SET,https://raw.githubusercontent.com/cbzy-3p/Surge/main/Rule/AppleDownload.list,DIRECT,extended-matching
```

按现有每天北京时间 00:17 的统一流程更新，不新增定时任务。拉取前验证旧规则；拉取后检查来源格式、最低数量、异常增减、去重、父子域覆盖和规则计数，再与其他规则一起提交。任一来源失败不发布部分结果。规则语法依据 [Surge Rule Set 手册](https://manual.nssurge.com/rules/ruleset.html)。此次检查不包含真实设备上的商店、下载及恢复操作。
