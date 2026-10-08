# 当前交接状态

更新：2026-10-08，Asia/Shanghai。历史证据见 [progress.md](progress.md)，完整验收见
[steve-character.md](steve-character.md)。开始／恢复时核对实际 Git、游戏进程与收据，
不能复用已结束会话的 PID 或地址。

## 当前目标与能力

持续目标 **active**。mod启用期间完整且跨重载显示Steve，**动作系统也用MC**；禁止
全部红沙装备，仅MC装备；目录点击加入真实MC背包；MC单击攻击及实际敌人伤害／击退。
全方块、原UI、真实状态HUD、禁用／卸载恢复及分发保持。旧身体反馈等待条件已解除，
受阻审计重新从零开始，完整目标仍未完成。

真实MC Java1.21.1管理36格Mod背包、六类方块与四格护甲存储。官方classic Steve几何／UV
及固定皮肤已导出，正在适配红沙骨骼／材质。九格HUD常驻／刷新／断线恢复已实测，
目录领取接口已有，实机按钮待验收；正式建造仍用蓝色碰撞代理，真实HP尚未接HUD。
完整MC schema3／revision25、选择格1、材料／建筑保持；四格护甲为空，人物装备应用未实现。

## 已成立的外观结果及边界

- 十一／十二资源仍显示原角色。十三资源注册v1进入闪退，恢复后原存档正常；新PAPPT行
  组件列表不匹配私有prefab，v2已改成各一项。旧v1勿重装。
- v2块体首次出现但错位、原部件混叠。原生头引用位置正常；MC共同父骨头曾错位／缺失。
  恢复完整原字节头PAMI后，用户确认方块头连接肩膀上方。仅缩小到完整材质合同差异，
  不能认定单一shader字段根因。
- 清空固定Macduff00000 app默认Armor，用户确认原服装消失，当次左手缺失、背装备重叠、
  头过大；收据 `2feb0ddf41b3488fba9eb226cf8fb672` 已恢复。
- 随后仅换完整原生身体PAMI，用户确认**左手出现、身体和四肢没有错位**；另确认
  “没有无关”指**头没有五官**，背部原装备仍在。只覆盖观测姿势；头比例、全MC皮肤、
  动作、重载与原装备禁用未通过。

## 身体对照已实测并恢复

- plan：`build/steve-body-native-material-probe-overlay`，14资源／严格8报告。
- SHA：`fa1f38ec686644fdebeddd53ad09429aab87083495da12155b5b6f3248b8e341`。
- receipt：`069425c3a6a0430fa9c576e3afe8f20b`，kind=steve-mesh-parameters，**restored**。
- recorder：`build/record-steve-body-native-material-20261008.py`；同名runtime前缀。
  五阶段各exit0，41安装文件、38恢复原文件、退出时36个最新存档、完整MC／原点／ASI保持。
  身体PAMI为50017字节原件，6变体×3draw；PAC／骨骼／scale／shrink及其余13资源保持。
- 人工结果和澄清在 `...-visual-result.json`，绑定收据、计划及三个采样摘要。受控owner的
  20成员双采样稳定，仅6槽标准primary RTTI，14槽未解析，控制器恰一次；目录存在不证明
  背部资源和owner回链，匿名槽不能猜类型。
- `probe_appearance_controller.py --render-input-paths` 双采样稳定但 **notReady／exit1**，
  Scene／选择／初始app可读，PAC/PAB声明不完整；没有descriptor／资源身份准入。
  未写内存、刷新、移除装备或修改装备存档。身体会话已结束。

## 最新头部主颜色贴图对照：皮肤未通过，已恢复

身体包恢复、实际游戏关闭并核对基线后，已串行安装下一项：

- plan：`build/steve-head-basecolor-probe-overlay`，14资源／严格9报告，PAZ770800字节。
- SHA：`29b813224b362f8d2e751a8ae31968846a55d96410f290ffd10deb00322078e5`。
- variant：`steve-kliff-original-head-body-material-empty-armor-head-basecolor-part-table-v2`。
- receipt：`bbdda1c5304f4cfe884a1e8ca1fdeed6`，kind=steve-mesh-parameters，**restored**。
- recorder：`build/record-steve-head-basecolor-20261008.py`；同名runtime前缀。
  五阶段各exit0，41安装文件／38恢复原文件、退出时36最新存档、完整MC／原点／ASI保持。
  用户反馈“头部没出现正确的史蒂夫五官、头的位置仍正常”；人工头位置通过，MC脸部
  未通过，本轮render-input双采样稳定而notReady。实际进程结束后已恢复，**无active
receipt／0041、无待恢复包**。用户手动启动、进入、退出，自动接管停止。
- 相对身体对照只换头PAMI三个主baseColor路径（16149→16134字节）；shader、EyeCover、
  SkinWrinkle／Aging参数、其他纹理和头PAC保持，固定已有DDS不新增。身体原PAMI及其余
  13项完整保持。人工结果与限制在 `runtime/steve-head-basecolor-20261008-visual-result.json`。
  文件匹配不证明renderer实际选择该PAMI或DDS；该次会话ASI尚无Steve头读取别名，未取得引擎读回。
- 候选10/10、完整本地封装／隔离事务31/31通过；固定源计划及六文件本地组合，不读取
  实际游戏元数据。标准安装仍核对active、游戏关闭、原始元数据与34个源索引。

## 当前现场：头UV实测未解决五官，已恢复

- 新包：`build/steve-head-uv-probe-overlay`，14资源／严格10报告；计划SHA
  `b27484b952059015920635a23cf489a2881d23ba86e554b0b80f7157a03e7c10`。
- 收据：`f4541cd031434b238e22b637efe64de2`，kind=steve-mesh-parameters，**restored**。
  已核实游戏退出并恢复，无active receipt／0041、无待恢复包。用户手动启动／退出偏好继续适用。
- 相对上一头baseColor包只翻三LOD共144个主UV V字段，头PAC从182fc…变为c0df7…；
  头PAMI／DDS及另外13项完整行和编码保持，几何位置、骨骼权重不变。UV候选不是已验证修复。
- 完整隔离事务／真实本地重建32/32通过，552.366秒；九个旧canonical计划纯准入通过。
  双计划头材质客户端46/46通过，82.870秒，含跨计划收据／variant拒绝。无需更换ASI。
- recorder：`build/record-steve-head-uv-20261008.py`，同名runtime前缀。
  五阶段均exit0；41项安装文件／38恢复原文件、退出时最新36存档、完整MC schema3/revision25、
  选择格1、原点／ASI保持。用户反馈“五官仍不正确，头的位置正常”，UV单变量未解决五官。
- 新会话in-world核对通过；固定`steve_head_pami`引擎读取首次实采成功：16134字节、flags50、
  storedSize1694，FNV `3a4d0e960a22bdf3`／head16与候选一致，ticket1、一次提交和一次读取，
  handler已释放；前后同实例、完整MC与41文件保持。报告为同名前缀`-material-read.json`，
  人工结果为`-visual-result.json`。成功只证明文件可解析，renderer选材质／DDS采样仍未证。
  用户正常退出后已核实进程结束，恢复时保持退出最新存档，旧会话PID／地址不得复用。

## 独立工作与剩余前置

MC动作由客户端算法生成。固定官方client／Yarn的PlayerEntityModel、BipedEntityModel与
PlayerEntityRenderer三个类摘要已匹配，含setAngles／animateModel／animateArms。
现有SteveModelDump仅导静态几何，glTF没有animations；红沙多骨蒙皮／合成弯曲不是MC刚体
动作。官方算法离线站立／转头／行走基准现已完成，9/9隔离重建检查通过；真实模型方法
各调用123次，三组各40tick＋endpoint、六部件TRS与原始字段完整保存。夹具为正常构造的
ArmorStandEntity，非Player，无World／tick；8个状态getter逐帧前后核对。固定client、21类、
46外部JAR；产物 `build/steve-pose-1.21.1`，独立JVM逐字一致。尚未覆盖蹲伏／挥击／持物等。
不能以离线输出代替实机。
原生API没有经过当前EXE验证、绑定受控owner的姿态／控制器应用入口。固定EXE有界审计
已排除旧coop两个落在指令内部的RVA；下一候选为精确Skinned+1C0的未命名owner-keyed对象，
仅vtable／弱owner／原owner回链有静态依据，骨骼palette、单位、ABI与线程未知。
最小只读身份诊断`probe_owner_skinned_object.py`已完成，主控复跑23/23离线检查通过；
11固定代码窗口，每样本最多97字节新增语义读取，统一依赖回读、双采样及同handle身份，
错误／变化清除成功标志。尚未实采，不为该诊断单独要求用户启动游戏；下次有必要会话再执行。
MC动作实时应用与完整系统未实现。
`+0x110`直接callee后续审计已辨明回调wrapper及弱句柄指针vector，常量8是容量，不能当骨骼数；
该分支未提供TRS／矩阵数组生产证据，不扩展现有只读工具的读取范围。

背部具体组件→prefab/PAC链未定位。14条raw装备记录只为观察；共享apply和表增删局部拒绝
不等于安全全禁装／恢复。攻击者／敌人类型、owner链和伤害／击退ABI尚缺，不调用候选函数，
不以移动NPC代替击退。头UV方向候选已离线完成，11/11重建检查通过；只翻三LOD共144个
V half字段，逐字逆恢复，其余PAC／PAMI／DDS保持。旧脸域若直接按DDS行序采样为透明，
翻V后落在有眼鼻嘴的非透明区域，但shader是否再反V仍未证明。产物
`build/steve-head-uv-control`，PAC SHA `c0df7b6e6fbe90038b8e277839ef59b26aa4cbba560f30770d82eec9acf50b55`，
report SHA `56790fa5efb6a2b38ed5938f217d4ddc25b11d5b87c18a6640721fd15ae3a3af`。
该单变量已接入严格10报告／14资源可逆封装，实测并恢复；翻V未解决五官。离线审计确认
同一main draw含内头与外帽，帽UV六区共6144texel全RGBA0，内头六区alpha255；原生材质
是否discard透明alpha未知。仅去掉透明帽面索引的离线候选已完成，保留内头／全部
顶点／UV／材质，用于检验遮挡假设，避免重复相同UV对照。孤立PAC仍不能
单独安装。正确五官、头比例、背部原装备及完整人物尚未验收。

下一候选：`build/steve-head-visible-layer/steve-head-visible-layer-report.json`，报告SHA
`6d68aa3eff9428fe9f7c63838fdbed10097a4c17ef0da940648b24ea972e6501`；PAC96505字节／flags1，
SHA `7c222d1cb2d475d7e487c8cad87967afc63d27a1fa14b99d35c62a24f762d9ca`。
`check_steve_head_visible_layer.py --rebuild` 12/12通过（10.781秒），独立MC／BC3／三LOD
CDMW解析、保守bbox、完整字段／索引逆恢复、纯准入和来源／报告篡改拒绝覆盖。没有安装。
下一步从固定十报告b27484…本地计划组成严格11报告／14资源整包，仅替换一个头PAC，验证
其他13项编码／flags／orig_size保持；为新包明确记录composition，不沿用旧headUvComposition
作为当前变更断言。完成安装恢复检查、绑定新完整计划的PAMI读取后，才准备下一实机测试。
用户目前无需启动游戏。

主控独占游戏安装、采样、恢复、后台和Git；最多三个子代理按独立范围执行。完成相关检查、
文档和普通GitHub推送后交付。游戏资源／存档／runtime／build保持忽略。

新固定头PAMI读取诊断已实现：仅一个steve_head_pami别名，16KiB／flags50、分别固定九／十报告计划／
active收据／实际41文件／同EXE实例／完整MC门禁。双计划客户端46/46、原生23/23及旧客户端27/27
检查通过；固定上游重放45份源码经CRLF规范化一致，ASI构建并已更新实际安装及发布artifact，
SHA `9d5cdc8eebbad47010f4d6e15e3afe74d630ace00332cd7032ac216c3494efe7`。原ASI备份保留，
38原文件、最新存档／MC／原点保持。新诊断已在十报告UV会话实采成功，只证明路径可读取，renderer
材质选择／DDS采样保持未验证；不为诊断开放任意路径或增加DDS／PAC读取上限。
