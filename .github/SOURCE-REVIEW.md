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
