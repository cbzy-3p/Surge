# Multi-source Surge Rules

所有自动更新由 `.github/workflows/update-rules.yml` 统一在每天北京时间 00:17 执行，按顺序拉取、合并、去重、校验后一次提交，避免多个工作流同时推送产生冲突。

所有可独立引用的分流规则均统一存放在 `Rule/`。`.list` 与 `.txt` 对 Surge 的匹配行为没有差别；本目录统一使用 `.list`，仅用于保持链接和命名一致。

来源固定按 `SukkaW`、`blackmatrix7`、`Rabbit-Spec`、`ConnersHua`、`Loyalsoldier`、`Yuu518` 的顺序检查。SukkaW 优先用于存在同等分类的原生 Surge 规则，blackmatrix7 负责细分类基线，其余四个来源补充和交叉核对。六个来源均没有对应分类或覆盖明确不足时，才使用其他持续维护的来源。

目标是轻量但不漏匹配。先合并可靠来源，再做不会缩小覆盖范围的精确去重、父子域压缩和 CIDR 合并；无法证明冗余的规则保留。小红书、抖音、微信和 Apple Intelligence 使用各自已核对过的专用来源。Soul 和 Web3 保留人工确认内容，不盲目合并宽泛的加密货币或云服务规则。

`Proxy.list` 使用 blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier 和 Yuu518 的明确代理服务分类，不以宽泛的全局规则替代。

`Apple.list` 是完整 Apple 服务总集，使用 SukkaW、blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier 和 Yuu518 合并生成，不拆分 Apple Music、Apple TV、iCloud 或地区服务。

`AIGC.list`、`GlobalMedia.list` 和 `ChinaCIDR.list` 在分类相符时优先使用 SukkaW，再按分类补充 blackmatrix7、Rabbit-Spec、ConnersHua 和 Yuu518。YouTube、Netflix、ChinaMedia、China 等更细分类不使用 SukkaW 的宽泛集合硬凑，改由 blackmatrix7 建立分类边界，其他固定来源补充。China 以域名为主，ChinaCIDR 专门合并并压缩中国 IPv4、IPv6 网段。

生成步骤保留 Surge 的规则类型语义。`DOMAIN-SUFFIX` 会移除它完整覆盖的精确域名和子级后缀，CIDR 会移除已被大网段完整覆盖的小网段；这些压缩不会放宽原有匹配范围。不同分类规则集之间允许保留相同规则，避免破坏独立订阅和策略顺序。每次更新都会检查来源数量、规则格式、CIDR、ASN、层级重复、逻辑规则内部覆盖、文件头计数以及输出数量变化，校验通过后才写入文件。

```ini
RULE-SET,https://raw.githubusercontent.com/cbzy-3p/Surge/main/Rule/Google.list,Google,extended-matching,no-resolve
```
