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

## 当前实际临时包：待用户手动进入

新原字节头材质对照已安装，**当前有 active receipt 和 0041，尚待实测及退出后恢复**。
安装前核实游戏关闭；用户启动、进入和退出均手动完成，主控独占安装、采样和恢复。
已发出手动进入同一存档、反馈方块头是否连接在肩膀上方并暂时保持运行的请求。
后续必须重新核实进程实例，不能复用旧 PID／地址。

- plan：`build/steve-head-native-material-probe-overlay`，13资源／严格6报告。
- plan SHA256：`991fa0fcf756bfec6138a3be13f651658721fb2a0a2b9f9e7dbe724871d39048`。
- variant：`steve-kliff-native-head-root-original-material-part-table-v2`。
- 收据：`5249d2f2339844f3a5b27b77d1353a66`，kind=`steve-mesh-parameters`，status=installed。
- recorder：`build/record-steve-head-native-material-20261008.py`；证据前缀
  `runtime/steve-head-native-material-20261008-`。before-install／installed均exit0，
  38项原文件／41项安装文件核对匹配，36个存档、完整MC、原点及ASI保持。
- 与失败共同父骨包相比仅替换私有头 PAMI，PAC／palette 与其余12资源逐字保持。
  原生 PAMI 16149字节、3变体×2draw，EyeCover与SkinWrinkle/Aging完整参数及纹理引用
  原字节保留。暂用原生头贴图作位置诊断，最终 MC 皮肤仍待完成。
- 生成器10/10、完整封装／隔离安装恢复28/28通过；实机位置、动画、身体和装备未验收。
  旧11／12／v2注册／原生头／共同父骨计划仍可准入；旧v1 app包被组件合同拒绝，勿重装。

## 下一步

收到进入反馈后核对同一新会话、收据及文件，再做必要的只读外观采样；用户正常退出后
等待实际进程结束，用新 recorder 的 before-restore／restored核对恢复。恢复须保持退出时
最新MC与存档，不能回写安装前状态；所有已有阶段证据不可覆写。

根据材质单变量结果确定下一项头部适配，不同时更改 palette／app／身体。原生装备
14条稳定记录仅证明只读观察链；共享apply并非安全写前禁装入口，表插入／删除的局部
拒绝也不证明全禁装或可逆恢复。伤害最新窗口209BDC0只有两独立形式输入，缺少具体
攻击者／敌人类型和owner回链，不能据此调用DamageApply或宣称击退完成。

## 协作与交付

一个主控、最多三个子代理；独立任务、文件所有权互斥。所有实际游戏资源操作由主控
串行执行。代码与文档经必要检查后正常提交／推送GitHub，游戏资源、存档、runtime、
研究输出及下载缓存保持忽略。持续目标未完成，检查数量不能代替游戏内验收。
