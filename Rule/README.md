# Multi-source Surge Rules

所有自动更新由 `.github/workflows/update-rules.yml` 统一在每天北京时间 00:17 执行，按顺序拉取、合并、去重、校验后一次提交，避免多个工作流同时推送产生冲突。

BM7 `blackmatrix7/ios_rule_script` 作为主来源，按类别补充 `v2fly/domain-list-community`、`Rabbit-Spec/Surge`、`Loyalsoldier/surge-rules` 和 `MetaCubeX/meta-rules-dat`。小红书、抖音、微信和 Apple Intelligence 使用各自已核对过的专用来源。Soul 和 Web3 保留人工确认内容，不盲目合并宽泛的加密货币或云服务规则。

生成步骤保留 Surge 的规则类型语义。`DOMAIN-SUFFIX` 会覆盖同值的 `DOMAIN`，精确域名不会被擅自放宽。每次更新都会检查来源数量、规则格式、CIDR、ASN、重复项、DOMAIN 与 DOMAIN-SUFFIX 冲突以及输出数量变化，校验通过后才写入文件。

```ini
RULE-SET,https://raw.githubusercontent.com/Rongwuyou/Surge/main/Rule/Google.list,Google,extended-matching,no-resolve
```
