# App Store 安装包与固件下载

本规则仅将 App Store / Mac App Store 的 App 安装包（包括重新下载、应用更新）以及系统 OTA、IPSW、恢复系统下载端点独立分流。链接和文件名不变，替换原先范围较宽的 Apple 下载分类。

## 来源与筛选

按 SukkaW、blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier、Yuu518 的现有 Apple 来源检查，具体地址写入规则头。SukkaW 使用现行 `domainset/apple_cdn.conf`，不导入完整 CDN 或 Apple 集合。仅采用审阅过的安装包、固件下载命名空间和上游出现的对应 CDN 别名，禁止通过 download 等关键词泛选。

App 安装包保留 `iosapps.itunes.apple.com`、`osxapps.itunes.apple.com`、`apps.mzstatic.com` 及专用 aaplimg 别名。固件数据保留 appldnld、updates、swcdn、swdownload、oscdn 和 osrecovery 等下载端点。来源量、筛选量及输出量记录于 `.github/apple-download-source-snapshot.json`。

系统下载用途以 [Apple 企业网络端点清单](https://support.apple.com/en-us/101555) 中 Software updates 为基准，其他固定来源交叉核对。官方列出的更新目录、签名、账号、商店 API 并非下载数据，因此不整段照搬。此次用户主动收窄范围，重新生成来源快照作为后续自动更新的数量基线；没有取消异常增减检查。

## 排除与限制

不包含整个 apple.com、itunes.apple.com、apps.apple.com、mzstatic.com 或 cdn-apple.com，也不包含共享 CDN 的 IP 段。商店页面、地区检测、bag/init/StoreKit、购买、登录、签名、下载调度、更新目录和检测继续使用原有配置。具体移除 mesu、gdmf、configuration、swscan、swdist、swcatalog、downloaddispatch、su 等接口。

移除音乐视频与在线播放、商店图片、GarageBand 音色、Xcode / 开发者工具、Swift Playground、屏保壁纸、模型及其他资源的专用端点。iCloud 仍由已有配置处理。第三方 App 安装后的自有资源下载不属于 App Store 安装包。

固件与其他系统资源可能共用 updates 等 CDN。域名分流无法在同一个 HTTPS 主机内按固件文件、字体、语音等资源类型严格区分；本规则不进行 HTTPS 解密，不能承诺只命中某类文件。这不意味着整个 Apple 服务或其他独立资源域名都走直连。

## 使用和更新

将本规则放在 Apple 总集和 China / CN-Additional / Proxy / NonCN / FINAL 等兜底规则前面。原有账号和商店接口保持原策略，无需为了本规则新增商店地区分类。

```ini
RULE-SET,https://raw.githubusercontent.com/cbzy-3p/Surge/main/Rule/AppleDownload.list,DIRECT,extended-matching
```

沿用现有每天北京时间 00:17 的统一更新，不新增定时任务。拉取前验证旧规则；拉取后检查来源格式、最低数量、异常增减、去重、父子域覆盖和规则计数，与其他规则一起提交。来源失败不发布部分结果。语法依据 [Surge Rule Set 手册](https://manual.nssurge.com/rules/ruleset.html)。本次未进行真实设备的下载验证。
