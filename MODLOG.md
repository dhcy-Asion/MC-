# CrimsonMC 持续开发日志

## 2026-10-06：依据 universal-modder 继续剩余功能

用户要求将桌面 `CrimsonMC` 的剩余工作设为持续目标并开始执行。目标已建立，尚未完成；
完整验收沿用 [docs/steve-character.md](docs/steve-character.md)，不能以一次构建或资产导出标记完整移植完成。

参考库固定在 `671544554523eb3ae8048c18d4eb8973f5f19652`：
[universal-modder](https://github.com/rehan-remade/universal-modder/tree/671544554523eb3ae8048c18d4eb8973f5f19652)。
本地 checkout 留在 ignored `vendor/universal-modder/`。使用 `mod-any-game`、`mashup-mods` 的
源码核对、最小功能实测、资产本地转换和验收记录流程。未安装全局插件或向参考库提交 PR。

### 路线与依据

- 继续真实 MC 1.21.1 权威服务 + 红沙原生内容适配，保留已有库存、建筑、地图和战斗。
- 参考库知识库没有红沙或 BlackSpace 专用记录。`um scan` 只识别为未知原生引擎、已有
  ASI loader；未列出 anti-cheat 信号不构成完整安全审计。游戏 EXE 门禁仍以项目的版本与 SHA 为准。
- GTA 示例使用另一 MC 版本的完整客户端及 D3D11/ReShade 颜色与深度合成；本项目是
  1.21.1 服务端与 D3D12 原生代理。示例没有可直接复制的红沙模型、骨骼、装备或方块转换器。
- 先验证九格 HUD 的真实渲染入口，再建立官方 MC 方块资产和红沙真实骨骼/PAC 的离线管线。
  资产可解析不等于游戏可加载；原生加载、动画、材质、装备和生命周期分别验收。

### 本轮发现

1. 快于一帧的建造请求可能绕过库存失效，短暂继续显示操作前快照。现已在提交修改时
   立即要求 MC 回读；新增用例先复现旧实现失败，再验证修复。
2. 上游 `OnPresent` 在菜单关闭且没有研究点时提前返回，导致九格栏与轮询均不执行。
   游戏实测发现后移除这一返回；关闭时的鼠标/键盘标志仍清零，HUD 使用 NoInputs。
   变更保存在 `red-side-patches/upstream.patch`，可从固定上游恢复。
3. 已验证本机原生身体模板能解析；完整结果和后续资产步骤在进度文件记录，不把
   候选骨骼绑定或未安装的 PAC 记作已在游戏显示 Steve。

### 实测保护与证据

更新插件前保存本机备份 `backups/before-hud-20261006/red-saves`，插件旧版由更新脚本按哈希备份。
用户已明确允许短暂接管红沙窗口、正常退出和重启进行 HUD 验证；没有消费材料或修改实验建筑。
原始截图、资源、进程记录和依赖留在 ignored runtime/build/downloads，公开摘要写入
[docs/progress.md](docs/progress.md)。

每个阶段完成相关验证后更新 CHANGELOG，再按 AGENTS.md 的既有授权提交并正常推送；
持续目标只有全部当前验收完成后才标记完成。本轮末 `get_goal` 返回 `usageLimited`，
后续开发须等待用户账户额度恢复/允许继续；没有改为 complete、paused 或 blocked。
