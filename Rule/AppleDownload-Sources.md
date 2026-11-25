# iPhone、iPad 安装包与系统更新下载

App 安装包沿用 AppStore.list 已收录的两条精确主机。移动系统更新下载采用 Apple 企业网络清单列出的 appldnld.apple.com、updates.cdn-apple.com 和 updates-http.cdn-apple.com。两条 updates 的 akadns 别名仅在优先来源中出现时纳入。所有输出使用精确域名。

每天检查 SukkaW、blackmatrix7、Rabbit-Spec、ConnersHua、Loyalsoldier 和 Yuu518。上游的宽泛后缀只用于验证已审阅主机，不扩大到其所有子域。来源地址和选中数量分别见规则头及 .github/apple-download-source-snapshot.json。

商店页面、鉴权、地区检测、更新目录、Mac 安装包和恢复系统、共享的 apps.mzstatic.com 均交给后续分流规则。下载如果改走未收录的共享主机，也会使用后续策略。Apple 同时列明这三个系统更新主机可提供运营商配置更新，域名分流无法在同一主机上区分所下载的文件。

将 AppleDownload.list 放在 Apple 总集和兜底规则之前。域名用途见 [Apple 企业网络端点清单](https://support.apple.com/en-us/101555)。
