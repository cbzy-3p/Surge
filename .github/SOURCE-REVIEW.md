# Rule supplement review, 2026-09-07

Preferred sources remain SukkaW, blackmatrix7, Rabbit-Spec, ConnersHua,
Loyalsoldier and Yuu518. Additional sources require a demonstrated coverage gap.

Live comparison found all 71 V2Fly DouYin rules covered by the union of
blackmatrix7 and Yuu518, and all 11 V2Fly XiaoHongShu rules covered by those
same preferred sources. Both redundant downloads were removed. Existing
DouYin rules remain preserved; XiaoHongShu retains its existing merge logic.

wresource contributes 16 domain suffixes beyond the two fetched XiaoHongShu
preferred feeds. bgpeer and dl123100 still provide corroborating domain data.
They remain provisional legacy exceptions: this comparison does not prove
absence from all six preferred sources. Their removal is not yet justified.
Their ASN and unrelated individual entries are not blindly merged.

CN-Additional was compared against these six principal domestic feeds:
SukkaW List/non_ip/domestic.conf (865 parsed entries), Rabbit-Spec China.list
(3700), blackmatrix7 China_Domain.list (3689), Yuu518 geolocation-cn.list
(5286), Loyalsoldier ruleset/direct.txt (111159), and ConnersHua Direct.list
(21). Of 43837 existing suffix rules, 18761 were not suffix-covered by
their union. Exact-domain entries do not replace suffix rules. Retain the
existing source: switching to these feeds would reduce current coverage.
This is a comparison of principal feeds, not every file in each repository,
and does not independently establish the legitimacy of each domain.

Generic domestic rules also cannot substitute for service-specific
XiaoHongShu classification. Retain its three legacy supplements under the
existing merge restrictions pending service-specific replacement evidence.

Bybit and N26 already prefer Yuu518, with
V2Fly used as fallback. Neither exception is newly introduced by this change.

## Repository health review, 2026-10-11

Reviewed main at `a760d9997912d574beb1f24b15de9886edc10d9a`. All 13 rule
updaters, the existing Telegram synchronization step and the module updater
were executed locally against their fixed live sources. The six preferred
rule sources, existing paths, independent subscriptions and schedules remain
unchanged. Publication of these reviewed changes was authorized by the user
on 2026-10-11; post-publication status is tracked by GitHub Actions.

Reproduced and repaired four updater behaviors: Goofish download/conversion
failure now retains a validated previous module; Bybit/N26 missing their
required domain now try the existing V2Fly fallback; selective V2Fly includes
fail before importing an unfiltered child; per-file update logs use that
file's own source counts. An invalid or absent fallback still aborts rather
than replacing valid output.

The live SukkaW IPv4 feed newly included `14.167.176.0/20`. Primary checks
returned APNIC allocation `14.160.0.0` through `14.191.255.255`, name
`VNPT-VN`, country `VN`, and RIPEstat prefix `14.167.176.0/20` with origin
`AS45899`. The live blackmatrix7, Rabbit-Spec and Yuu518 China feeds did not
cover this prefix. This combination supports treating the new entry as a
foreign-prefix anomaly; registry country alone is not proof of physical
location. The exact new prefix is excluded from ChinaCIDR before compaction,
without changing other categories or dropping any previously committed
ChinaCIDR coverage. Raw upstream counts remain in the snapshot. Revisit this
single exclusion if the primary evidence changes.

Primary evidence checked on 2026-10-11:

- https://rdap.apnic.net/ip/14.167.176.0
- https://stat.ripe.net/data/network-info/data.json?resource=14.167.176.0
- https://ruleset.skk.moe/List/ip/china_ip.conf
- https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/ChinaIPs/ChinaIPs.list
- https://raw.githubusercontent.com/Rabbit-Spec/Surge/Master/Rules/ChinaCIDR.list
- https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geoip/cn.list

Module limitations remain visible: porntube, huangdou and TgRedirect upstream
module URLs return 404, so their existing modules and mirrored scripts are
retained. The root `wloc.module` references two Yu9191/wloc scripts returning
404; the root `机场信息模块` references ljrgov/conf airport.js returning 404.
These root files are not covered by the scheduled Module updater, and their
sources have not been replaced. Sixteen external kelee.one script URLs
returned Cloudflare 403 from this environment, including a representative
request using a Surge user agent; this does not establish failure on the
user's phone. No device execution has been verified.

Validation uses the rule validator, updater regression tests, module
validation including hashes and Node syntax, cross-file overlap audit, YAML
parsing and shell syntax checks. actionlint v1.7.12 reports only the two
existing `queue: max` keys, which current GitHub documentation explicitly
supports; a second lint run ignores only that known schema mismatch and
passes. No workflow was changed for this linter limitation.

Final totals are 46 rule files and 80,581 rule lines, 19 module files and 14
mirrored JavaScript files. All 110 regression tests pass. An independent
comparison confirms every previously committed rule body remains identical;
cross-file overlaps remain intentional. No tracked files were added or
deleted, and git diff whitespace checks pass. These are local/source checks,
not a post-push GitHub Actions run or an iPhone execution result.

GitHub reference: https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
