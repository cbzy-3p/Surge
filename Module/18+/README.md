# 18+ 模块

本目录收录经过筛选的 18+ 相关 Surge 模块。默认不建议同时启用功能重复的模块。

## 推荐合集

- [`18+-recommended.sgmodule`](./18%2B-recommended.sgmodule)：One、porntube、黄豆短剧的组合版。

组合版没有纳入 `lzlukvca.sgmodule`，因为它与黄豆短剧模块处理同一个 `lzlukvca.cc` 服务，重复启用可能造成请求脚本重复执行。需要使用 7452323 版本时，请关闭组合版中的黄豆短剧功能后再单独启用它。

## 单独模块

| 模块 | 来源 | 说明 |
|---|---|---|
| `one.sgmodule` | [one-api.zzxu.de](https://one-api.zzxu.de/one/one.sgmodule) | One 点播去广告/增强 |
| `porntube.sgmodule` | [Yu9191/Rewrite](https://github.com/Yu9191/Rewrite) | porntube / 91porn 相关功能 |
| `huangdou.sgmodule` | [Yu9191/Rewrite](https://github.com/Yu9191/Rewrite) | 黄豆短剧功能 |
| `lzlukvca.sgmodule` | [7452323/QuantumultX](https://github.com/7452323/QuantumultX) | lzlukvca.cc 功能，和黄豆短剧二选一 |

## 使用前须知

这些模块都需要 Surge 的 HTTPS 解密能力，组合版和前三个单独模块包含远程脚本或 URL Rewrite。启用前请确认自己信任来源，并在 Surge 中安装和信任 MITM 证书。不要同时启用 `huangdou.sgmodule` 与 `lzlukvca.sgmodule`。

本目录只整理公开来源，不代表对上游内容作安全保证。上游脚本、域名和功能可能随时变化。
