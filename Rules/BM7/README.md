# BM7 多源 Surge 规则

这些文件由 `.github/scripts/update_bm7_rules.py` 生成，并由 GitHub Actions 每日同步。

## 来源策略

- BM7 `blackmatrix7/ios_rule_script` 是主源，保留其原始 Surge 规则类型。
- Rabbit-Spec 只补充 Google、Facebook、Instagram、TikTok。
- Loyalsoldier 只补充 Google。
- MetaCubeX 只接入直接对应的 `apple-music`、`apple-tvplus`、`binance` 和 `category-cryptocurrency` 数据。
- v2fly 只接入直接对应的域名分类。

补充源只转换为 `DOMAIN-SUFFIX`，不引入补充源的 IP、ASN、关键词或正则规则。相同域名会去重。同步脚本会校验 BM7 基线数量、规则类型和补充源非空，异常时不提交更新。

## 使用

```ini
RULE-SET,https://raw.githubusercontent.com/Rongwuyou/Surge/main/Rules/BM7/Google.list,Google,extended-matching,no-resolve
```

合并到 `main` 后使用 `main` 链接。PR 分支链接只用于测试，不建议长期写入生产配置。
