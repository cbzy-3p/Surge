# Multi-source Surge Rules

所有自动更新由 `.github/workflows/update-rules.yml` 统一在每天北京时间 00:17 执行，按顺序拉取、合并、去重、校验后一次提交，避免多个工作流同时推送产生冲突。

所有可独立引用的分流规则均统一存放在 `Rule/`。`.list` 与 `.txt` 对 Surge 的匹配行为没有差别；本目录统一使用 `.list`，仅用于保持链接和命名一致。

BM7 `blackmatrix7/ios_rule_script` 作为主来源，按类别补充 `v2fly/domain-list-community`、`Rabbit-Spec/Surge`、`Loyalsoldier/surge-rules`、`MetaCubeX/meta-rules-dat` 和 `Yuu518/Yuu-rules`。小红书、抖音、微信和 Apple Intelligence 使用各自已核对过的专用来源。Soul 和 Web3 保留人工确认内容，不盲目合并宽泛的加密货币或云服务规则。

`Proxy.list` 使用 BM7、Rabbit-Spec 和 Yuu518 的明确代理服务分类。v2fly 与 MetaCubeX 没有可直接用于 Surge 的同类分类，因此不以其他宽泛规则替代。

`Apple.list` 是完整 Apple 服务总集，使用 SukkaW、BM7、Yuu518 和 MetaCubeX 合并生成，不拆分 Apple Music、Apple TV、iCloud 或地区服务。

`AIGC.list`、`YouTube.list`、`Netflix.list`、`ChinaMedia.list`、`GlobalMedia.list`、`China.list` 和 `ChinaCIDR.list` 使用 Rabbit-Spec 为主来源，按分类补充 BM7、Yuu518 和 MetaCubeX。China 以域名为主，ChinaCIDR 专门合并并压缩中国 IPv4、IPv6 网段。

生成步骤保留 Surge 的规则类型语义。`DOMAIN-SUFFIX` 会移除它完整覆盖的精确域名和子级后缀，CIDR 会移除已被大网段完整覆盖的小网段；这些压缩不会放宽原有匹配范围。不同分类规则集之间允许保留相同规则，避免破坏独立订阅和策略顺序。每次更新都会检查来源数量、规则格式、CIDR、ASN、层级重复、逻辑规则内部覆盖、文件头计数以及输出数量变化，校验通过后才写入文件。

```ini
RULE-SET,https://raw.githubusercontent.com/cbzy-3p/Surge/main/Rule/Google.list,Google,extended-matching,no-resolve
```
