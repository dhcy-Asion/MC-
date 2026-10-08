# 当前交接状态

更新：2026-10-08，Asia/Shanghai。这里只保留当前决定和下一步；历史证据见
[progress.md](progress.md)，完整范围见 [steve-character.md](steve-character.md)。
开始／恢复工作时重新核对 Git、进程和实际安装收据，不能把本文当作现场事实的替代。

## 当前交付点

优先让 Steve 在现有存档中实际显示，并证明可恢复原资源。完整目标还包括持续外观、
动画／两套装备、全方块、真实状态 HUD 与分发；当前交付点不缩减完整验收范围。

- 十一资源及十二资源头描述文件实测均仍是原角色。
- 已实读当前初始 app 为 Macduff 00000；运行时选项表有两私有名字，不代表加载成功。
- 原 PAPPT 两段缺私有名字。十三资源 v1 加注册表后，用户报告进入游戏闪退；恢复
  原资源后同一存档可正常进入。此包实机失败，不能继续安装旧十四资源包。
- 已确认静态缺陷：新增注册项沿用原版身体 2／头 7 个组件，而私有 prefab 各只有
  CD_Nude／CD_Head 一个组件；原版两者列表逐项相等。v2 已修正新行列表与跨资源检查。
- 修复只改 PAPPT 新行中的部件列表；模型、材质、骨架与 app 保持。静态缺陷成立，
  v2 本次实机正常进入且未重现闪退；没有异常堆栈证明唯一根因。
- 用户截图已出现 MC 方块头／蓝绿身体／紫色下肢，但位置错开并与红沙衣服、头发及
  装备混叠。**模型资源可见，完整外观装配失败**；不是原来的“资源没有显示”阶段。
  原衣服主要来自独立 Armor，头发来自 Hair，不足以证明旧 Nude／Head 重复。
  当前优先只换私有头的一个 PAC 引用到原生头，区分网格资源链和共同装配。

## 现场和恢复

- 2026-10-08 已核实游戏关闭，并恢复十二资源收据
  `64cefed193bc4014914e78495471dc67`；38 项原始哈希匹配，0041 和 active receipt 消失。
- 恢复前后 36 个最新红沙存档、MC 持久状态 revision 22、原点与 ASI 保持。
- 当时 MC／桥接后台已停止，本次恢复比较的是持久文件，未伪造在线 API 状态。
- 十三资源 v1 收据 `90cdf0fca1ce4095aedc43d3515a1525` 已在进程退出后实际恢复。
  当时无临时包、0041 或 active receipt；38 项原始哈希匹配，36 个最新存档、
  完整 MC 状态、原点与 ASI 保持。用户手动启动新会话后确认可正常进入、不再闪退；
  新会话再次核对完整 MC 状态不变。
- 十三资源 v2 收据 `045d94ec45d74007a5dfd1c53dd8e00a` 已实测并在用户正常退出后
  恢复。该阶段无 active receipt／0041；38 项原始哈希、36 个最新
  存档、完整 MC 状态、原点与 ASI 均核对保持。
- 原生头单引用对照已通过 9 项候选及 27 项完整包检查并安装。**当前 active receipt
  为 `57b18550c3e344c19278ecd6f0b9d2c6`，0041 存在，待实测及退出恢复**；variant
  `steve-kliff-native-head-part-table-v2`。安装前后原始基线／安装文件、完整 MC、原点
  与 ASI 核对通过。用户已收到手动进入并反馈原生头位置的请求。
- 游戏启动、进入和退出仍由用户手动完成；主控独占安装、游戏诊断与恢复操作。
- 本次恢复证据：`runtime/steve-part-table-v2-20261008-{before-restore,restored}.json`。
  闪退日志及恢复后用户对照记录：`runtime/steve-crash-20261008/`。日志在角色创建处
  中断，没有异常堆栈；指定时段 Windows 应用事件未找到匹配的崩溃记录。
- 持续目标未完成；最近工具元数据为 `usageLimited`，当前按用户明确指令继续执行。

## 本轮交接

| 工作 | 负责人 | 状态／验收 |
| --- | --- | --- |
| 闪退恢复、封装交叉检查与 v2 事务 | 主控 | v1 已恢复，原版进入正常；v2 十三／十四包分别 24/24、25/25 通过 |
| 原生头候选 | crash_asset_audit | 完成 9/9；只改引用及必需长度／指针，原 donor 首组件逐字一致 |
| 显示错位分析 | steve_position_audit | 未定位明确 palette／坐标错误；建议原生头引用对照，不盲目补骨或平移 |
| 原生头封装接入 | diagnostic_review | 独立五报告集合、固定单路径覆盖及 app 互斥；主控完成 27/27 包检查 |
| v2 游戏内对照 | 主控＋用户手动进出游戏 | 正常进入，目录双采样通过；截图显示错位及混叠，已退出恢复；十四包未安装 |
| 原生头游戏内对照 | 主控＋用户手动进出游戏 | 已安装，待原生头位置反馈；完成后退出恢复 |

目录成员与用户实际画面分别记录；探针不因为截图而回填 native rendered 成功标记。
HP 仍未接入 HUD，不在当前外观排障中扩展无关逆向支线。

旧十三包未取得 in-world 探针结果，不能补填成功记录；before-restore／restored 已完成。
v2 使用独立 `build/steve-part-table-v2` 与 `build/steve-part-table-v2-probe-overlay`，
variant 为 `steve-kliff-part-table-v2`，不能复用 v1 快照脚本中的固定计划／收据绑定。
新版脚本 `build/record-steve-part-table-v2-20261008.py` 及同名 runtime 证据前缀，
已完成 before-install／installed／in-world／before-restore／restored。
`runtime/steve-part-table-v2-20261008-catalog.json` 实读两表私有头／身均 present，
目录正确、原名基线正确、完整依赖与双采样稳定；新名称注册加载已得到直接证据。
`...-appearance.json` 再次确认 Macduff 00000 初始 app，PAB 声明存在、PAC 声明空，
整体仍为 notReady；没有 Steve 渲染／应用成功标记。读取时 PID 82292，后续须重新
核对实例，不能复用地址；该实例已正常退出。用户画面保存于 ignored
`runtime/steve-crash-20261008/v2-user-visible-overlap.png`，供定位与混叠分析。
计划 SHA256 为
`19b5ae4841a63795324f642a8332fec23aca1783ed4af3804affd1237fdd54dc`。

**当前包**：`build/steve-native-head-probe-overlay`，计划 SHA256
`043c8b22e074da3d24e2c6c2e25f388f4ce57865b289de97f365be508b7503a5`。
快照脚本 `build/record-steve-native-head-20261008.py` 和同名 runtime 前缀；已完成
before-install／installed。后续实读、正常退出、before-restore、
`install_steve_probe.py --restore`、restored。其余十二资源与 v2 完全相同，未启用 app
对照。原生头正确只能缩小到私有网格资源链，不能单独证明骨权重为根因。

## 协作规则

最多一个主控和三个子代理，按实际独立工作启用。子任务只带问题、必要文件、所有权和
验收条件，不复制完整聊天；交付结论、证据位置、修改文件、检查结果及剩余问题。
文件修改责任互斥，所有游戏资源操作由主控串行执行。每 30～45 分钟审视当前支线是否
改变下一步行动；没有新证据时收束并选择下一实验。向用户报告实际能力与阻碍，
检查数量不能代替功能验收。完成验证后更新进度、记录并正常提交／推送 GitHub。
