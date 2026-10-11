# 阿里巴巴总集来源与覆盖

核对日期：2026-10-11。`Alibaba.list` 是完整阿里系服务总集，重点覆盖淘宝、支付宝和闲鱼，同时包含天猫、1688、菜鸟、钉钉、优酷、高德、阿里云、共享 CDN 等固定上游已分类服务。支付宝采用专用分类，闲鱼继承独立集合及已有实机端点。全部通过同一个 `RULE-SET` 引用。

## 六个固定来源

按 SukkaW、blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier、Yuu518 的顺序检查与合并。

| 来源 | 使用方式 |
| --- | --- |
| SukkaW | 从 `Source/non_ip/domestic.ts` 的 `DOMESTICS.ALIBABA` 块确定分类，再对照原生 `List/non_ip/domestic.conf`。`Source/non_ip/domestic.conf` 的 Alibaba User-Agent 块同时保留。 |
| blackmatrix7 | 完整合并 `Alibaba/Alibaba_All.list`，再合并 `Alibaba/Alibaba.list` 中前者缺少的 `.alibaba`、`.taobao`、`.tmall` 等条目，以及 AliPay、XianYu、DingTalk 专用集合。 |
| Rabbit-Spec | `Rules/China.list` 只提取已被专用分类确认的域名及子域名，不导入整个 China 集合或泛化关键词。 |
| ConnersHua | 保留 `Surge/Ruleset/Direct+.list` 的 Alibaba 与 Umeng 块，不导入相邻腾讯、Google 或其他服务。 |
| Loyalsoldier | `release/direct.txt` 保留域名集合的精确/后缀语义，只提取已分类域名及子域名，不导入国内直连全集。 |
| Yuu518 | 完整合并 `surge/geosite/alibaba.list` 与 `alibabacloud.list`，包含前述基线以外的新增阿里系分类。 |

所有下载地址固定记录在 `.github/scripts/update_alibaba.py` 和生成文件头中。没有增加六个固定来源之外的规则源。

Sukka 的原生国内总集可能把阿里云承载的具体客户端点压缩进客户自己的大后缀。总集保留 Alibaba 分类中的精确端点，例如 `upos-sz-mirrorali.bilivideo.com`、`upos-sz-estgoss.bilivideo.com`，不会因此导入整个 `bilivideo.com`。分类源码仅用于选取边界，原生规则和分类逐项核对；格式变化或分类端点失去原生覆盖时停止生成。

## 淘宝、支付宝、闲鱼

淘宝主域、品牌顶级域名、短链、图片缓存、天猫购物与登录依赖由完整阿里总集覆盖。支付宝专用集合的所有规则保留，包括 `.alipay` 顶级域名及 `alipayobjects.com` 等资源域名。

更新顺序为先更新 `XianYu.list`，再生成 Alibaba。Alibaba 合入最新专用基线、原有闲鱼独立集合和更新器确认的业务依赖。闲鱼实机记录的 21 个端点及其他已有规则，即使被总集父域压缩，也会逐条核验匹配覆盖没有减少。详细证据见 [XianYu-Sources.md](XianYu-Sources.md)。原独立订阅继续保留；若闲鱼要用不同策略，应放在 Alibaba 前面。

## 去重、更新和检查

保留域名、后缀、User-Agent、进程名、IPv4/IPv6 网络的规则类型。后缀压缩仅删除已被父后缀覆盖的条目；CIDR 合并仅合并相邻或已覆盖网络。输出使用 `no-resolve` 网络规则，不依靠 DNS 主动解析来扩大 IP 规则匹配。每次生成都会反向核验所有合并输入的域名、网络及其他规则仍被输出覆盖。

接入现有每日北京时间 00:17 的统一更新。来源为空、数量大幅变化、核心分类丢失、格式异常或覆盖缩小时停止写入；文件与来源快照一起校验并提交。历史规则在生成时保留，减少上游临时缩减造成的覆盖损失；明确失效或误分类的历史条目需要另行复核后删除。来源快照只记录专用分类与选中的补充条目，国内总集无关条目的变化不会造成快照抖动。规则内容不变时保留原更新时间。

## 使用边界

这份总集有意覆盖阿里云、共享 CDN 和海外网络，因此托管于这些域名或 IP 段的第三方网站也可能命中。若全部指定 `DIRECT`，其中海外节点同样会走直连；需要其他策略的细分类应放在总集前面。`PROCESS-NAME` 与 User-Agent 是保留的上游补充，实际可用性取决于 Surge 平台和请求信息，iOS 主要依赖域名及网络匹配。

当前已核验全部合并来源与已有闲鱼实机证据的规则覆盖，不代表已验证当前手机全部操作。没有主机名/SNI 的裸 IP 连接、上游尚未收录的新服务，以及模块重写或广告拦截行为仍需结合 Surge 请求记录核对。
