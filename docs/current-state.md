# 当前交接状态

更新：2026-10-08，Asia/Shanghai。这里只保留当前决定和下一步；历史证据见
[progress.md](progress.md)，完整范围见 [steve-character.md](steve-character.md)。
开始／恢复工作时重新核对 Git、实际游戏进程和安装收据，不能以本文替代现场核实。

## 当前目标与已有能力

持续目标 active。优先完成现有存档中的真实 Steve 外观，完整目标保留：mod 启用期间
持续且跨重载显示 Steve、只能使用 MC 装备并禁止全部红沙装备、MC 单击攻击／实际敌人
击退、物品目录点击加入 MC 背包、全方块、真实状态 HUD、禁用／卸载恢复与分发。
不能把离线导出、四格护甲保存或单个头部对照当作完整人物完成。

当前使用 Minecraft 1.21.1 官方 classic Steve 几何／UV 与固定皮肤，正在转换红沙格式及
骨骼／材质合同。已有真实 MC 背包、六类方块与蓝色碰撞代理、常驻九格库存 HUD。
控制栏目录点击已接领取接口，实机按钮验收待做；真实 HP 尚未接 HUD。

MC 后台已部署 schema3、四格人体护甲存储与桥接，完整 ItemStack 转移／组件保存及
失败回滚已验证。最新36格、选择、方块与 revision25 保持，四个护甲槽为空；人物穿戴、
装备效果、红沙装备禁用与 MC 攻击仍未实现。摘要见
[equipment-validation.json](equipment-validation.json)。

## 外观结论

- 十一／十二资源实测仍为原角色。十三资源注册 v1 进入闪退，恢复后原存档正常。
  静态确认新 PAPPT 行组件列表不匹配私有 prefab，v2 改为 CD_Nude／CD_Head 各一项。
- v2 可正常进入，用户截图已显示 MC 块体，但头身／下肢错位并与原 Armor、Hair、装备
  混叠；完整装配未通过。运行时目录存在不等于显示成功。
- 原生头单引用对照：用户确认正常连接在肩膀上方，已退出恢复。
- MC 原生头模板／共同父骨122包：用户反馈“方块头仍错位或没有显示”，实机未通过，
  收据 `5dfe1a43fa9846d6a1f1399bd42a4e2d` 已 restored；保留退出时最新存档／schema3。
  该分组反馈无法进一步区分错位与缺失，不推断唯一根因。
- 头空间复核未找到确证静态错位：194/122中立差为毫米级，不重复安装弱 palette 假设。
  失败包将原生头专门 shader 改成 Standard，下一单变量核对完整原生 PAMI 合同。
  该原字节材质对照现已实测：用户确认方块头正常连接在肩膀上方；衣服与MC仍重叠。
  结果只缩小到完整材质合同差异，不证明某一个shader字段为唯一根因。

## 最新实测与恢复：原生头材质对照

新原字节头材质对照已实测，用户正常退出后核实实际进程结束并恢复；
该次恢复时无active receipt／0041；现在已安装下方衣服对照。用户启动、进入和退出均手动完成，主控独占安装、采样
和恢复。该会话实例 `69188:134359096823476439` 已结束，不能复用旧PID／地址。

- plan：`build/steve-head-native-material-probe-overlay`，13资源／严格6报告。
- plan SHA256：`991fa0fcf756bfec6138a3be13f651658721fb2a0a2b9f9e7dbe724871d39048`。
- variant：`steve-kliff-native-head-root-original-material-part-table-v2`。
- 收据：`5249d2f2339844f3a5b27b77d1353a66`，kind=`steve-mesh-parameters`，status=restored。
- recorder：`build/record-steve-head-native-material-20261008.py`；证据前缀
  `runtime/steve-head-native-material-20261008-`。五阶段均exit0，38项原文件／41项安装文件
  核对匹配，退出时36个最新存档、完整MC schema3/revision25、原点及ASI保持。
  人工头位置／衣服重叠反馈独立保存在`...-visual-result.json`，不是探针解码的渲染证明。
- 与失败共同父骨包相比仅替换私有头 PAMI，PAC／palette 与其余12资源逐字保持。
  原生 PAMI 16149字节、3变体×2draw，EyeCover与SkinWrinkle/Aging完整参数及纹理引用
  原字节保留。暂用原生头贴图作位置诊断，最终 MC 皮肤仍待完成。
- 生成器10/10、完整封装／隔离安装恢复28/28通过；人工头位置通过，动画、身体和装备未验收。
  旧11／12／v2注册／原生头／共同父骨计划仍可准入；旧v1 app包被组件合同拒绝，勿重装。

## 下一步

用户要求先去除原服装模块，并确认“原本服装和mc的建模一直在重叠”。固定Macduff00000
app仅清空Armor内12个默认／预览Prefab的可逆对照已经完成，保留外部XML及通过头位置
的13资源。生成器10/10、完整14资源封装／事务28/28通过，并已核实实际游戏关闭后安装。
**当前有active receipt／0041，衣服隐藏效果尚待用户手动进入反馈，之后须退出恢复。**
仅处理默认服装渲染，不删除装备存档、不冒称全部原游戏装备禁止。

- plan：`build/steve-clothing-control-probe-overlay`，14资源／严格7报告。
- plan SHA256：`6703890ac16748566f54b5dfd81ff95ca68ead3d2ba41e2b59602704cc0dc319`。
- variant：`steve-kliff-original-material-empty-armor-part-table-v2`。
- 收据：`2feb0ddf41b3488fba9eb226cf8fb672`，kind=`steve-mesh-parameters`，status=installed。
- recorder：`build/record-steve-clothing-control-20261008.py`；同名runtime前缀。
  before-install／installed各exit0，41安装文件、36存档／完整MC schema3/revision25／
  原点／ASI保持。现已请求用户手动进入反馈原服装是否消失及MC身体／四肢位置。
  当前不复用旧实例，收到进入后重新核实会话；退出恢复比较最新状态，阶段记录不可覆写。

服装优先之后再接回MC头贴图；已固定三个baseColor路径span及包内Steve DDS，对应
官方64×64 PNG和原编码，纯内存逆替换通过；尚未写皮肤候选或实测。原生装备
14条稳定记录仅证明只读观察链；共享apply并非安全写前禁装入口，表插入／删除的局部
拒绝也不证明全禁装或可逆恢复。伤害最新窗口209BDC0只有两独立形式输入，缺少具体
攻击者／敌人类型和owner回链，不能据此调用DamageApply或宣称击退完成。

## 协作与交付

一个主控、最多三个子代理；独立任务、文件所有权互斥。所有实际游戏资源操作由主控
串行执行。代码与文档经必要检查后正常提交／推送GitHub，游戏资源、存档、runtime、
研究输出及下载缓存保持忽略。持续目标未完成，检查数量不能代替游戏内验收。
