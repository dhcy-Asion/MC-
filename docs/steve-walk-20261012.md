# 2026-10-12 骨架与步态：有界收束

第一阶段未完成。用户实机通过身体观测姿势的对齐及头部五官保持；全身MC颜色、头比例、原装备隔离、
MC刚体动态动作与持续重载仍未通过。f6169f/69a身体包继续installed/0041；两代备份和退出最新存档保留。
本轮无native调用/写内存、原包变更、游戏/生产服务重启、未知工具安装或上传。

## 44字节路径实际证明了什么

固定EXE 1.0.0.2976/SHA57da…，从已证Skinned调用2D992A4→2D98D50出发。
精确unwind准入失败时正文读0B；单独入口分类确认E9→精确102B的10DC76B0。
最后消费者2DD4D70精确1372B/297指令完整解码，独立16/16通过，并停止全部下游。

输入44B被重排到一个handle链选定的stride0x110共享buffer记录：

| 输入偏移 | 记录偏移 | 可证明操作 |
| --- | --- | --- |
| 00/04/08 | 00/04/08 | DWORD复制 |
| 0C/10/14 | 10/14/18 | DWORD复制 |
| 1C/20/24 | 20/24/28 | DWORD复制 |
| 18 | 30 | DWORD复制 |
| 28/2A | 34 | 两u16移位/OR合成DWORD |
| 无输入 | 38 | 写0 |

另有12个float lane从其它0x110记录复制、handle创建/登记、0x50记录两字段和标记更新。
正式资源类型及辅助调用语义未知；不能将44B或float复制命名为TRS、world transform、bounds或骨姿态。
调用RCX=current R10；早先由Skinned+B8载入，但跨两未读helper后的保留关系未证。RDX为44B地址，
内容正式类型未证。不可据此调用或写入。

## 排除与未准入的候选解释

- 该正文没有逐骨loop/count、PAC/PAB palette引用或矩阵/TRS计算，未建立typed骨姿态消费者。
- 两u16在此只打包进记录+34，不作为骨索引；记录slot来自receiver handle链，不能当输入骨号。
- “RCX一定是当前Skinned+B8”不成立为已证前提；本轮明确降为current R10未证receiver。
- 早前2DBDCB0的1570B只闭合父上下文/依赖绑定，不提供可用pose入口；旧r3实际13函数，旧prose14
  已在新索引纠正。Generic bool、+110 capacity8、同UV重试、删HKX/猜flags等旧停止路线没有重开。

没有可用姿态消费者，也没有最小单肢写入入口。ABI、线程、所有权/同帧寿命和恢复合同均未闭合。
未读辅助调用仍可能有间接行为，因此负结果只针对当前合同，不是“所有移植方法不可行”的证明。

证据：[完整消费者结果](../build/steve-native-pose-boundary-20261012/pose-terminal-consumer-20261012/RESULT.md)、
[receiver注记](../build/steve-native-pose-boundary-20261012/pose-skinned-entry-classification-20261012/RECEIVER-NOTE.md)、
[16项独立审阅](../runtime/steve-body-walk-20261012-native-independent-review.json)。失败准入和成功分类均保留。

## 已完成的独立MC路线

固定Java1.21.1/Yarn build.3/classic wide；单次现有缓存offline隔离世界、正常stop/exit0。
未连接/未登记/未生成的ServerPlayer经公开setVelocity保留y/z，16帧x=.04再16帧x=0；完整
world.tickEntity→playerTick自然推进，11预热+32采样。实际x1.5→2.1400000000000006，峰speed .15995486，
停步16后4.5125016e-05、pos2.5599322；没有手写age/prev/limb/phase或额外updateLimbs/travel。
独立30/30核所有43tick与rawbits、.4平滑/三delta；生产MC源2/build118/world46、41游戏文件及9既有工具保持。
这是冲量位移驱动的真实LimbAnimator，未证明正常connected walking输入、client/20Hz生命周期或native应用。

[MC结果索引](../runtime/steve-body-walk-20261012-mc-movement-result.json)、
[30项独立核验](../build/steve-mc-movement-20261012/independent-review-r2.json)。r1筛查把==误判为赋值，
失败保留，r2含9允许比较/18拒绝mutation反例；capture不改、server不重跑。

新32×3六关节回放仅准备，未执行准入函数、javac/Java或输出pose。实际preferredHand=null；
现有正式Biped getter比较MAIN_HAND，null使RIGHT取opposite=LEFT；只限progress0/空手/standing，
新准备不注入swing/private实体字段。源码与元数据在build/steve-mc-movement-20261012/replay，
尚须新上下文复核，不计已实现/通过。

## 下一项能区分关键假设的实验

建议另开独立路线，从已有资源/骨架到renderer/evaluator的**带类型palette来源**入手，而不跟进本44B
buffer的下游。先只复核既有资料是否提供实际骨数组producer/consumer：

1. `build/steve-render-scene-research-20261007/mesh-container-static.json`：已有Skinned调用/对象来源。
2. `build/mc-pose-native-audit-20261008/fixed-windows-r3.json`：已有13条精确地址/片段记录与固定EXE契约。
3. `tools/probe_owner_skinned_object.py`：受控owner/Skinned身份及回链，不能把其匿名资源自动命名palette。
4. `tools/prepare_steve_segmented.py`、`tools/prepare_steve_current_rig.py`，以及
   `build/steve-body-basecolor-probe-overlay/reports/overlay-report.json`：实际1008顶点分段混合权重、
   447 PAB→189 palette映射/neutral补偿；最早六单骨表不是当前身体。

具体复核问题：是否有独立证据能绑定“这个typed buffer确实属于当前body/head资源并由骨evaluator逐骨
产生”，且说明count/stride/单位/矩阵空间与同帧寿命？如没有，只交准确缺口，不追加泛化扫描。
若找到，最小行为实验为**单肢只读捕获+离线顶点重放**：使用当前PAC真实权重，同帧矩阵预测该肢
顶点，区分“实际骨palette”与“对象/缓存记录”。先闭合此合同，再独立研究写ABI/线程/恢复；不先写内存。

MC可并行的新上下文问题：[回放准备元数据](../build/steve-mc-movement-20261012/replay/prepared-replay-scope.json)
和[待复核列表](../build/steve-mc-movement-20261012/review/mc-walk-replay-20261012-pending-review.json)已给出
固定helper/runner/输入及问题。复核通过后只评估一次离线96样本，核getter bits、null合同、腿cosine/
停步幅度和六part字段；arm有官方age idle bob，不能要求停步后所有arm角都零。仍不解决native入口。

## 2026-10-12 新上下文接续：资源到 palette 的实际结果

本轮有界离线路线已完成，第一阶段与MC native走路仍未完成。f6169f/69a包保留installed；
不重启整个工程、游戏/生产服务，不调用/写内存，不装未知工具，不提交或上传。
工程没有 `.agents/skills`；仅使用AGENTS、已签入交接与明确关联源码/本地证据，无受限会话目录读取。

| 当前资源事实 | 实际字节结果 | 证据边界 |
| --- | --- | --- |
| body PAC8f26d6…/236594B | 4LOD各1008顶点/504面；189局部slot→447 PAB；13个加权骨，每LOD752单骨/256双骨 | 是当前计划身体，不能用早期六单骨表或combined1056替代 |
| head PAC7c222d…/96505B | 3LOD各48存储/24引用顶点/12面；192局部slot；全部slot0/255→122 B_face_com | 24帽层顶点仍存储但不引用；旧head93缺PABC警告不适用 |
| PAB9c8a96…与声明PABC | 447完整bone名字/hash/bind/inverse；body420/head207表覆盖各自实际加权骨 | 本地资源映射闭合，运行时选择/合并/scale仍未证明 |
| 私有prefab/descriptor | 两prefab各一个正确PAC Skinned组件；两骨架字段实际为空；body显式PAB，head只在FacialBlendShapeSet引用PAB | 不能推定parent继承或头通用skin实际选择 |

主审计与不用项目解析器的回读核对全部4176存储顶点40B/权重；PAB weighted bind×inverse最大误差
5.9604634e-08。17810/8878是逐记录断言数，不是功能测试数或运行时验收。再次运行生成器明确拒绝
覆盖且旧输出保持。源码/版本/来源hash、逐顶点原始字节和偏移都在
[资源结果](../build/steve-typed-palette-20261012/resource-audit/RESULT.md)、
[资源报告](../build/steve-typed-palette-20261012/resource-audit/report.json)、
[原字节回读](../build/steve-typed-palette-20261012/resource-audit/independent-readback.json)。
资源报告SHA `41320bd33d5f49b3740fb06dab2a2712050cf3176c4e1579e3e0891b88a80450`。
第三独立stdlib源字节审阅34/34实质资源检查与5/5辅助门禁通过；精确分类见
[COUNT-NOTE](../build/steve-typed-palette-20261012/resource-independent-review/COUNT-NOTE.md)和
[独立资源审阅](../build/steve-typed-palette-20261012/resource-independent-review/review.json)。

### 原生已有窗口与唯一新准入

r3实际是13个地址/片段记录：10解析目标等于unwind begin、2coop地址为同一片段内部、1仅64B。
所有已有unwind记录标fragmentOnly，不能称13个完整函数。固定EXE与56次旧raw窗口、六个任务来源
片段逐字匹配；匿名owner对象、常数1、0x40容器和12字节复制仍不提供typed骨数组语义。

本轮确实定位Skinned PAC/PAB属性引用→同一resource job+D0/+D8→栈descriptor的callback2DA6720。
调度时RCX指栈wrapper，不证明实际callback receiver/ABI，正式资源类与当前渲染资源等价也未成立。
[原生审计](../build/steve-typed-palette-20261012/native-audit/RESULT.md)和
[精确来源合同](../build/steve-typed-palette-20261012/native-audit/callback-source-contract.json)保留字节与caveat。

主控对唯一callback只查固定EXE PE头、.pdata及旧caller字节。LEA rel32和调度call均回核，
精确或包含2DA6720的unwind条目均不存在：**首次正文读取0B，未准入，原实验未作fallback分类或callee追踪**。
[边界报告](../build/steve-typed-palette-20261012/root-audit/resource-callback-admission.json)15/15检查通过，
SHA `658f3da668ff117ef5ada769f2090e1000fa17e2703dd8e2db24e27f30fca09c`；只是停止合同被遵守。
其中allExceptionRowsValid仅检查每条begin<end，不声称完整unwind语义验证；源码保持原样供复核。
负结果限于这些窗口和当前准入合同，未证明全部方法不可行，也未关闭整个持续目标。

后来明确独立的5B分类合同经23/23静态预审，读取一次E9 e93b80feff，signed位移-98245，
目标2D8E760..2D8E7F0恰144B，唯一exact/containing条目，unwind010f0600/version1/flags0。
执行12项边界门禁通过，只另读4B unwind元数据，**目标正文0B/bodyReadAdmissionGranted=false**。
[分类证据](../build/steve-typed-palette-20261012/root-audit/resource-callback-classification.json)，
SHA `7f9a4425de24b45ab12990eb2d5e18ca7896620fd8571d335cd2d81b550dc12f`。
不是typed evaluator通过，不读第二跳。断线使分类postreview未保存、body-contract未写，恢复时确认两者不存在。
下一阶段仅在实际既有Capstone5.0.7 module/DLL摘要及独立预审闭合后完整解码这144B，不跟下游。

### 精确下一步与实机请求门槛

左臂LOD0主层144..263、袖648..767共240顶点；实际三个local slots51/92/82分别为
PAB133 UpArmTwist、349 Forearm_sub、348 Hand。预先可用的源数据和空间注意事项见
[单肢只读合同](../build/steve-typed-palette-20261012/resource-audit/single-limb-readback-contract.md)。
只有当前owner/头身实际资源、typed evaluator输出、slot索引/矩阵空间/单位、count/stride/完整边界、
inverse-bind组合及同帧epoch/所有权寿命全部独立成立后，才能读这三矩阵和同帧consumer顶点做离线预测。
若buffer已是skin矩阵不得重复inverse-bind；外部双采样稳定、PABC neutral或合成弯曲不能替代该合同。

本轮没有可靠接口，未执行单肢捕获或runtime矩阵顶点重放，没有可审批的写ABI/线程/恢复实验。
下一静态工作必须先提供明确source锚点和入口/边界证据，限定一个窗口，不重开44B、generic bool、
+110capacity8或匿名child扫描。没有这些新证据时应保持本轮负结果，不要求用户为离线复核开游戏。
未来必要采样由父任务在主窗口只请求进入同一测试存档并做一次指定动作；当前不用发该请求。

10:03Z历史查询确认游戏仍在同一11208实例，native ready/buildOk=true但MC8766超时，组合notReady不代表
角色不在世界。未按E/截图/启动/强杀/restore；fixed3.12程序在默认sandbox受执行限制，允许的只读
升权运行成功，未安装依赖。首次custody的空树问题保留before.json/错误记录，before-r2才是完整基线。
41游戏文件、36当前存档、MCsrc2/build118/world19、两代各38备份和receipt/plan/ASI/EXE/原点的前后
保持记录在root-audit；已有14项dirty的原字节另存original-dirty，不回滚或覆盖用户历史改动。

12:13Z连接恢复后fresh游戏0进程、native/MC均超时，未为离线研究启动。14项dirty全与old-before相同，
不确定保存的postreview/bodycontract/blocker说明实际均不存在。补做old-after-r2结果13/14保持，
唯一不相同是存档组：slot1/lobby.save、save.save及Steam remotecache.vdf在断线间更新，原差异与
assert失败报告保留；没有把旧比较改成通过，也没有还原这些最新文件。
resume-before以最新36存档/19生产世界作55份副本，源与复制后末读全部一致；新备份在
backups/steve-typed-palette-resume-20261012T121600Z。后续保护只按新基线比较，旧两代各38备份、41游戏
文件、MCsrc2/build118/world19、receipt/plan/ASI/EXE/原点仍与old-before匹配。


## 2026-10-12 恢复后：唯一144B终端结果与停止范围

前文目标正文0B指断线前分类检查点；本节才是恢复后的最新实际读取。第一阶段、完整Steve与MC走路
仍未完成。没有启动游戏、生产服务或安装候选，也没有runtime矩阵捕获/顶点重放/native调用/写内存。

连接恢复先补未做的保护复核：原14dirty逐字保持，41游戏文件/生产MC/两代备份保持；old-after-r2
为13/14，存档组的slot1两save及Steam remotecache在断线间更新，原差异与assert失败保留，未回滚。
最新36存档和19世界复制55份并完整末读匹配；新resume-after15/15保持。12:13Zfresh游戏0、native/MC
超时，未借10:03Z旧ready/PID。五补录文档65链接/围栏/AST21/JSON26/逆还原和git diff检查通过。
这些检查不等于新游戏内行为验收；备份根和全部摘要见
[新基线](../build/steve-typed-palette-20261012/root-audit/resume-before.json)、
[15项保持](../build/steve-typed-palette-20261012/root-audit/resume-after.json)。

依赖采用既有固定Python3.12和实际Capstone模块/DLL，无安装或下载。binding声明5.0.7、dist标签5.0.9、
native API返回5.0，不能把目录名或API返回当DLL补丁证明。65文件前后保持，其中58包payload与安装
RECORD的hash/size一致；module94571d13…、DLL76958e18…、Python EXE4d6f5f81…、BSD license404bd0…。
首预检因合法空REQUESTED元数据早停，r1源码留存，修后只放行这个空marker。
[完整依赖manifest](../build/steve-typed-palette-20261012/root-audit/decoder-dependencies.json)，SHAdd5b0cef…。

首body预审25/26，因取得body后异常/最终回读失稳不保留raw而拒绝；原报告/源码不覆盖。修后把decoder
初始化放到读前，post-read捕获错误并保存raw/partial和失败阶段，撤销format/localclosure等验收。
[r2预审](../build/steve-typed-palette-20261012/native-audit/body-decoder-pre-review-r2.json)30/30，
11/11纯fake故障用例通过（未加载DLL/读EXE）；仅grant固定脚本7879e216…单次144B。

实际`decode_resource_callback.py` exit0：只读取2D8E760..2D8E7F0一次144B，Capstone33指令连续覆盖，
两条je均前向到2D8E7D0，ret在2D8E7EF，整个区间无额外padding；源/EXE/65依赖末读稳定。
目标rawSHA `b1684037030da3e61574e36b54f1c97bdfc40de81fc1f5214e575e0d06053a0f`。
[完整body报告](../build/steve-typed-palette-20261012/root-audit/resource-callback-body.json)，
SHA `84ea16edcffee45a78fb1e5021fac4a47ee11c056f03479e8bc5bb4ef60cb1d4`。
只另查.pdata元数据2933328B和4B unwind header，没有重读5B入口或任何调用/分支目标。

| 本窗口已证操作 | 不能提升的语义 |
| --- | --- |
| incomingRCX被保存在RDI；读取receiver+D0与一个未知virtual返回的首qword比较 | callback正式receiver/类型/ABI未知，不把scheduler stack-descriptor RCX投影成job/Skinned/骨数组 |
| 读取receiver+D0所指对象+70 byte并与6比较 | 6只为此条件字节值，不是六关节/bone count证据 |
| C8/E8引用及payload+19/+20/+28组合成参数，调用2D1E8C0 | 参数正式类型/数量/语义未知，未证明PAB palette/矩阵输出 |
| virtual slot+260和随后2D8E7F0调用 | 三调用全部未解引用/未读取/未调用；返回值与效果未证，不称getter/加载/析构/骨播放完成 |
| 从stack-supplied pointer写byte2 | formal输出协议未知，2不能命名pose或任务完成标志 |

正文无逐骨循环、PAC/PAB slot索引消费、float/vector/matrix计算或同帧时钟/对象寿命合同。未展开调用
仍可能有间接行为，因此负结果仅限此144B窗口，不证明全部移植方法不可行。到此**终止所有下游**：
不追2D1E8C0/2D8E7F0/virtual+260/global对象/RTTI，也不重开44B、generic bool或+110capacity8。

下一项须先给新的独立formal evaluator/骨输出来源以及明确单窗口准入；不能因本窗口出现helper而
自动把它作下一候选。当前owner/所选头身/PAB slot、runtime count/stride、矩阵空间/单位/inverse-bind
组合及同帧epoch/寿命未闭合，所以左臂三骨240顶点只读捕获与离线预测仍未准入；不提出写入实验，
不要求用户为了这项离线研究开游戏。后续完整当前阶段结论须按新的证据再定，MC走路未应用。

独立终端审阅 **30/30通过**：只用报告留存raw逐条手工核opcode/ModRM/SIB/REX、33指令拼接摘要和
rel8/rel32目标，没有再读EXE、加载解码DLL或展开调用。此计数是字节与边界核对，不是功能验收。
[终端结论](../build/steve-typed-palette-20261012/native-audit/BODY-RESULT.md)与
[30项终端审阅](../build/steve-typed-palette-20261012/native-audit/body-terminal-review.json)，后者SHA
`f3c21a6c44ea028fe930c0368c6eba7d5180c117b3427f13c583f998df8974fc`。
最后的文档/保护核对另存root-audit终态报告；旧失败与各阶段0B检查点均保持，不覆写成通过。
