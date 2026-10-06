# Steam 创意工坊分发准备

核实日期：2026-10-06（Asia/Shanghai）。此记录是发布前置事实，不是已获官方许可或
已经上传工坊的声明。目前只有 GitHub 源码／原型产物分发，未验证干净机器安装。

## 工坊支持状态

[红沙 Steam 商店](https://store.steampowered.com/app/3321460/Crimson_Desert/)的功能表和
[官方 Steam 社区](https://steamcommunity.com/app/3321460)导航，本次均未列出 Workshop。
未找到 Pearl Abyss 官方公开工坊支持声明；因此状态为**公开支持未确认**，不是
“永远不支持”。不能将工具无法访问某页或通用上传 API 的存在作为该游戏支持证据。

[Steamworks 工坊实施文档](https://partner.steamgames.com/doc/features/workshop/implementation)
要求游戏应用后台启用 ISteamUGC、配置存储配额，并由游戏处理订阅下载内容。
这些配置需要应用发行方完成，第三方 mod 仓库不能替发行方启用。
在游戏支持确认前，不生成虚假的 PublishedFileId、上传入口或订阅安装成功记录。

## 发布资格和资源范围

[红沙 EULA](https://store.steampowered.com/eula/3321460_eula_0)第 5 条对修改／逆向、
未经批准的程序和修改游戏文件设置限制，并保留适用法律例外。
[Fan Content Guidelines](https://crimsondesert.pearlabyss.com/en-US/Policy?_policyNo=130)
要求遵守服务条款及他人的 IP 权利。现有资料不能证明本 ASI 原型有官方发布授权；
免费、非官方声明或未收到答复均不能代替许可。

[Minecraft EULA](https://www.minecraft.net/en-us/eula)及
[Usage Guidelines](https://www.minecraft.net/en-us/usage-guidelines)没有提供本项目把
Steve 原版皮肤、方块纹理和导出模型整套随另一游戏模组分发的明确许可。
本地提取、官方下载和第三方工具 MIT 许可证不等于跨游戏资产分发授权。
当前原版／衍生资源继续留在 ignored downloads／build，不包含在 Git 或 ASI。
[Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/)第 6.D
要求上传者有足够权利授予工坊所需许可；上传成功本身不能证明资格。

这些是发布前置条件核查，不是对适用法律例外的最终判定。来源声明见
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。

## 后续发布验收

1. 游戏工坊支持、官方允许的 mod 路线及涉及资源的分发资格有可引用证据。
2. 发布包采用明确白名单：获准分发的本项目产物、安装／更新／卸载脚本、配置、文档、
   必需许可证；不含游戏程序／归档、MC 原版／衍生资源、凭据、个人存档和日志。
3. 干净 Windows 机器使用合法红沙安装完成下载、准备、启动、更新、卸载；检查必要
   Java／Python／后台依赖，不能要求开发机 ignored 缓存。兼容范围仍只证明 1.0.0.2976。
4. 工坊实际订阅后正确发现、安装、加载；更新和退订有证据，版本／校验及恢复原外观
   行为通过。GitHub push、打包和本机安装与这一验收分别记录。

以上四项均未完成。本轮不编写假定红沙已开放工坊的上传脚本，不主动发布工坊内容。
