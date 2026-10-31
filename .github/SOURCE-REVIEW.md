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

## Alibaba family review, 2026-10-11

Following the user's request for one complete Alibaba family subscription,
added `Rule/Alibaba.list` rather than separate new Taobao/Alipay/XianYu files.
The six preferred sources were checked in their existing priority order.
Full BM7 Alibaba, AliPay, XianYu and DingTalk classifications and Yuu Alibaba
and AlibabaCloud are merged. The BM7 small Alibaba variant also supplies the
brand TLD rules absent from its All variant. Sukka's explicitly classified
Alibaba block is cross-checked against its native generated domestic feed;
customer endpoints compacted under unrelated parent services stay scoped to
the classified endpoint. Conners Alibaba/Umeng sections are retained. Rabbit
and Loyalsoldier contribute only domains within the confirmed classification.

Existing XianYu rules and device evidence are preserved and checked against
the compacted output. Unlike the independent XianYu subscription, the new
full-family set intentionally includes shared Alibaba cloud/CDN suffixes and
overseas IP ranges; third-party tenants on those networks can match. Details
and subscription order are documented in `Rule/Alibaba-Sources.md`.

The new updater follows XianYu in the existing daily 00:17 Beijing pipeline.
All source/output validation occurs before writing. Counts, core domains,
source format and every merged rule's retained semantic coverage are checked;
source failure or abnormal drift leaves the committed rule and snapshot intact.
Selected source counts, rather than unrelated domestic-list churn, are stored.

Local live generation produced 1,449 rules: 1,389 suffixes, three exact hosts,
53 IPv4 networks, one IPv6 network, one process name and two User-Agent rules.
A second live rebuild left the rule and snapshot byte-identical. All 46
existing rule files remain byte-identical. The repository now validates 47
rule files and 82,030 rule lines. All 122 regression tests pass, including the
new preservation, classification isolation, brand TLD, source failure and
snapshot drift checks. Cross-file overlaps remain informational and retained.
YAML, shell syntax, whitespace and actionlint checks pass using the same narrow
`queue: max` schema exception described above. These are source/local checks;
current phone execution is not verified.

## AIGC growth review, 2026-10-29

Reviewed main at `7f5f9de6c835baa76ce990a2b9bdb5da02e05af3`. The last
three scheduled rule updates stopped at the media snapshot guard, before
publication. Sukka's AI IP feed grew from 24 to 401 parsed rules; the
compacted AIGC output grew from 175 to 552. All 377 added output rules are
IP prefixes covered by the union of the prefixes in OpenAI's official
https://openai.com/chatgpt-voice.json, creationTime
`2026-10-27T22:28:21.782457+00:00`. Adjacent official /32 entries are
collapsed before comparison, so the two generated /31 entries are checked
without broadening coverage. All 175 previous AIGC rules remain unchanged.
The other four AIGC source counts remain unchanged.

Refresh the reviewed AIGC snapshot baseline together with its generated
output. Keep the existing 65% decrease and 2.5x increase bounds, fixed
sources, schedules and all-or-nothing publication. Future unreviewed large
changes still stop publication. The guard now reports every anomalous count
in one error rather than masking later anomalies behind the first one.
Regression tests cover both threshold boundaries, simultaneous growth and
shrinkage, and preserving output and snapshot on a failed update.

Validation: all 14 rule updater scripts and the existing Telegram shell
synchronization completed successfully against live sources locally. The
full regenerated tree validated at 47 files / 82,752 rules. Unrelated
generated changes were then excluded from this focused fix. The final
five-file diff retains 47 rule files / 82,727 rules; all files except AIGC
keep their committed rule bodies and source snapshots. All 116 non-module
regression tests pass, including the three new guard tests. Workflow YAML,
embedded shell syntax and git whitespace checks pass; workflows and modules
are unchanged. These are local checks, not published Actions or device tests.

## Post-publication Apple coverage review, 2026-10-29

Fix commit `39576acfc0ecf004de49a85203bc54fc04ecaa79` passed both push
checks. Rerun attempt 2 of Actions run `40769333182` checked out that fix,
completed all source updates and Telegram synchronization, validated 47
files / 82,752 rules, and published `c0b3c486284cfa09243dbf778afd13598303dd56`.

The resulting Apple diff removed `DOMAIN-SUFFIX,icloud.cn` because the BM7
and Rabbit general Apple feeds removed it. BM7's dedicated iCloud feed
still contains it, as does this repository's independent iCloud list.
Merge that existing preferred provider's specialist feed into the Apple
total to preserve the previous coverage while upstream classifications
disagree. Live comparison of its 61 rules adds exactly this one suffix;
no other Apple rule is removed. This is a conservative source-conflict
resolution, not an independent claim of domain ownership. Record and guard
the specialist feed count like every other source.

A new integration test also exposed a missing-output case: when Apple.list
was absent, two empty comparison strings prevented its creation. Explicitly
write when the target is missing. Tests cover specialist inclusion on an
empty target and unchanged prior files on source-fetch failure.

## Pre/post-fetch and MagicRule review, 2026-10-31

Fixed missing-target creation in the iCloud and Proxy updaters. Regression
tests cover creation and preservation of both output and snapshot when a
source fails. The update job now validates committed rules before fetching
and runs the cross-file audit after output validation, before publication.

Reviewed the MagicRule Surge index and 32 available category manifests.
Kingsoft, GoogleVoice and OKX have verified artifact hashes and rule bodies
identical to the existing merged outputs, and now use index/manifest discovery.
The adapter rejects wrong clients/categories, missing or duplicate artifacts,
unexpected hosts, hash mismatches and count mismatches before any rule write.
Existing drift thresholds and all-or-nothing publication are retained.

Five downloaded artifacts (GitHub, Facebook, China, ChinaIPs, Telegram) did
not match the manifest bytes_sha256. The cause is not established; this is
not evidence that their rules are malicious. Crypto and Proxy had no exact
category match. Other categories have semantic or coverage differences
requiring review, so their existing sources remain active. This is a staged
migration, not a completed replacement of every BM7 feed. Machine-readable
metadata and results are recorded in .github/magicrule-review.json.

Local validation: all 129 non-module regression tests pass. Live execution
of the baseline updater fetched all configured sources and regenerated the
three migrated categories without changing their rule bodies. Yuu's TikTok
feed additionally supplied tiktokshop.com, tiktokstaticb.com and
tiktokvapp.com; the previous 60 TikTok rules remain present. Final output
validation covers 47 files / 82,748 rules. Cross-file auditing, workflow
YAML parsing, embedded bash syntax and git whitespace checks pass. No
module files, schedules or subscription paths were changed.

## Focused Proxy review, 2026-10-31

Live source review found exact-only normalized entries (not semantic unique
coverage): BM7 0, Rabbit 6520, Conners 122, Yuu 16. All existing sources
remain active; one snapshot cannot establish that a source stays redundant.
Loyalsoldier remains a cross-check instead of a wholesale import.

Added only oaistatic.com and oaiusercontent.com, each confirmed as a
DOMAIN-SUFFIX in both BM7 OpenAI and Yuu openai live feeds. These are
reviewed supplements, not an import of the broad MagicRule Global feed.
The old files.oaiusercontent.com suffix is compacted under its parent;
all previous Proxy coverage remains. Output changes from 7,125 to 7,126.
Evidence feeds:
- https://raw.githubusercontent.com/blackmatrix7/ios_rule_script/master/rule/Surge/OpenAI/OpenAI.list
- https://raw.githubusercontent.com/Yuu518/Yuu-rules/rule-set/surge/geosite/openai.list

Removed the legacy source-set migration exemption from output size checks.
It searched for Loyalsoldier in the old header, which is always present and
therefore bypassed this independent drop check; the separate snapshot guard
was still active. Output checks now independently guard both drops and
growth, even without a snapshot. Validate existing output before network
fetches and rendered output before writing. Added regression coverage for
the legacy-header bypass, growth without a snapshot, and the narrow scope
of supplements. 132 tests pass; 47 files / 82,752 rules validate locally,
and an independent old/new comparison confirms retained Proxy coverage.

## CN / NonCN review, 2026-10-31

Rebuilt all media categories live, including China and ChinaCIDR, and
CN-Additional against its retained source. Existing domestic rule bodies
remain unchanged. CN-Additional no longer silently discards invalid source
lines; it aborts before writing. Committed output size is independently
checked if the source snapshot is missing. Tests reproduce both failures
and verify unchanged output/snapshot.

Added an independent NonCN.list from the preferred Yuu518 geolocation-!cn
Surge feed. 26,626 distinct source entries compact to 26,616 rules. Only
DOMAIN and DOMAIN-SUFFIX are accepted; formats, output counts and snapshot
drift are checked before writing. Exact hosts remain exact. Missing targets
are created. This classifies domains, not the complement of CN IP space.
It does not replace or expand Proxy.list. Existing source priorities are
retained and no module files or schedules change.

Boundary review found 118 NonCN entries equal to or under a China.list
domain, 19 under CN-Additional and 48 under iCloud. These reflect differing
classifications and may be affected by policy order; they are not proof of
a conflict in the user's unseen profile. Report examples and counts in
.github/non-cn-overlap-review.json. Retain cross-file overlap for independent
subscriptions and document domestic/service precedence. The update job now
generates NonCN alongside the existing rules and runs its regression tests.

Local checks: 138 non-module tests pass; 48 rule files / 109,368 rules
validate; media and CN-Additional live rebuilds pass. Source failures, malformed
lines, format shifts, missing snapshots and suffix compaction have regression
coverage. These are local checks before publication, not device tests.
