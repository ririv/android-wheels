# 包索引地址迁移

## 仓库与地址

主仓库由 `ririv/android-wheels` 改名为 `ririv/py-extra-wheels`，为未来支持其他平台预留命名空间。当前已实现的构建平台仍为 Android。

| 用途 | 地址 |
| --- | --- |
| 主仓库 | https://github.com/ririv/py-extra-wheels |
| 主包索引 | https://ririv.github.io/py-extra-wheels/ |
| 兼容包索引 | https://ririv.github.io/android-wheels/ |

新增配置建议使用主包索引。旧地址继续返回可被 pip 读取的完整索引，不依赖浏览器跳转或 JavaScript。

## 发布与同步

主仓库的 `pages.yml` 工作流根据 `wheels` 分支生成索引，发布到自身的 `gh-pages` 分支。生成的下载链接使用改名后的仓库地址。

旧索引由 `ririv/ririv.github.io` 仓库的 `android-wheels/` 目录承接。主仓库读取兼容站点已发布的 `sync-state.json`，将其记录的源 Git 树与当前 `gh-pages` Git 树比较，仅在尚未同步时调用兼容站点的 `sync-wheel-index.yml` 工作流。该工作流只同步索引 HTML，不复制 wheel 二进制；没有定时扫描，也可手动触发。

同步会校验包页面完整性与下载链接的仓库归属。源数据异常时直接失败，不提交异常索引。同步提交后显式请求用户站点的 Pages 构建，避免 `GITHUB_TOKEN` 提交不会自动触发 Pages 发布的问题。

同步脚本、测试与工作流位于 `ririv/ririv.github.io`。接收端使用该仓库自带的 `GITHUB_TOKEN` 完成内容提交和 Pages 发布，现有首页和主题保持原样。

## 跨仓库通知凭据

发送端 `py-extra-wheels` 需要配置 `LEGACY_INDEX_DISPATCH_TOKEN` Secret。细粒度 token 仅选择 `ririv.github.io`，授予 `Actions: write`；不需要内容写入权限。内置 `GITHUB_TOKEN` 限于所属仓库，不能代替此跨仓库触发凭据。

发布工作流先校验通知凭据，再生成与发布索引。凭据缺失、过期或权限不足会明确失败，不回退到定时扫描。

## 验证

兼容索引的 `https://ririv.github.io/android-wheels/sync-revision.txt` 记录对应的主仓库 `gh-pages` 提交。该值应在同步完成后与同步时的主仓库提交一致。`sync-state.json` 另记录源 Git 树，因此文件树相同、提交 SHA 不同不会重复同步；通知失败后的重跑则会继续补发，直到公开状态一致。

迁移验收包括新旧索引的根页面、包页面、实际 wheel 下载，以及同步工作流和 Pages 构建结果。GitHub 仓库旧地址由平台重定向保留；不要另建同名 `android-wheels` 仓库覆盖该重定向。

主索引的 `index-state.json` 同样记录已发布的 wheels Git 树。汇总提交与索引通知互不混淆：即使 wheels 已提交，重跑发布任务仍会补发未完成的索引通知。状态只在事件中读取，没有定时扫描。
