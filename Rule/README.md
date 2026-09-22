# Multi-source Surge Rules

所有规则的定时更新由 `.github/workflows/update-rules.yml` 统一安排在每天北京时间 00:17，按顺序拉取、合并、去重、校验后一次提交。GitHub Actions 的定时任务可能延迟，实际完成时间以运行记录为准。

手动更新建议选择 `Update All Surge Rules`。旧的 Apple Intelligence、CN Additional、DouYin、WeChat、XiaoHongShu、Twitter 和 Telegram 手动入口仍保留，但都调用同一套完整规则更新流程，不再单独生成和提交部分规则。规则和来源快照一起校验、提交；任一更新步骤失败，本次不会提交已生成的部分结果。抖音和小红书原有的 PR 检查仍保留。

规则更新与模块更新共享目标分支的写入并发组；任务取得执行资格后再检出分支最新内容，避免这两类任务互相竞争推送。模块更新时间保持不变。使用 `queue: max`，允许最多 100 个任务等待，避免新触发的任务替换已经等待的规则或模块更新。

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

`CN-Additional.list` 是例外：它使用纯域名集合格式，以 `.` 开头的条目匹配该域名及其子域名，必须通过 `DOMAIN-SET` 引用。不要将下面这一行改成 `RULE-SET`，也不要在同一配置中用两种类型引用同一个 URL。文件格式、原有链接和覆盖范围均保持不变。

```ini
DOMAIN-SET,https://raw.githubusercontent.com/cbzy-3p/Surge/main/Rule/CN-Additional.list,DIRECT,extended-matching,update-interval=86400
```

格式依据：[Surge DOMAIN-SET 官方说明](https://manual.nssurge.com/rules/domain.html#domain-set-file-format)。跨规则集重复保留，以支持独立引用和不同策略；需要单独分流的细分类规则应放在可能覆盖它的总集之前。
