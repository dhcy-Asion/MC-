# Steve 动作资产路线：2026-10-12 接续

## 2026-10-16 最新：动作路由检索纠正，取消黑臂等待

A2已恢复且实际41文件保持，用户要求继续真正动作而非黑臂对照。旧PAA前缀筛选遗漏了animmeta和motionblending目录；
本轮7个精确查询全部命中，未压缩basic_stride_walk已取得字段级四动画引用，均为不同basic_片段。
两项直接相关压缩配置的正式提取请求中止、无产物，此轮按最新委托只报告，不重复审批或执行；不认作用户撤销任务／拒绝。
详见 [2026-10-16动作路由证据与阻碍](steve-motion-routing-20261016.md)。MC动作仍未实现；下文为此前阶段记录。

当前 M4a 第一阶段仍进行中。用户授权优先完整 Steve 和 MC 动作；本轮根据新的公开源码，
转向 PAA 资产路线，不追此前 144B 的 callee/global/vtable，也不重开 44B 共享缓存路线。
没有应用 MC 走路，没有修改或安装动画。本次委托要求新外部工具逐次确认；用户已批准固定旧版
codec的一次无改动往返，现已完成。离线检查不需要游戏运行。

## 最新：可逆资源视觉A–B–A路线，无须先取得骨API

用户最新要求明确用可回滚资产＋视觉实验验证；实际clip未知保留为假设，不将未存在的同帧骨API再次设为本路线前置。
原精确语义oracle/MC动作验收仍有其要求，本次视觉正负反馈只定义以下有限结论。**未安装或启动游戏。**

[实际原件核验](../build/steve-paa-visual-20261012/root-audit/source-installed-readback.json)证明当前安装索引
0009/0.pamt SHA c561ae…的record78421，字面资源character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa。
实际0009/16.paz大小920591056B，offset377952160、compressed32444、orig41592、archiveflags2，
encodedSHA EA067…与此前原B5解码提取关联，双读/stat/index/收据稳定；只直接解一条记录，没有codec或新decode。
首Windows分隔符baseline键查错早停，未读PAZ；r1/失败保留，修正key规范化后同范围通过。
[resource审阅](../build/steve-paa-visual-20261012/resource-review/report.json)79静态断言与
[combined15合同](../build/steve-paa-visual-20261012/resource-review/combined15-contract.json)确认底层支持opaque PAA：
flags2=已知LZ4 block(store_size=False)、nonencrypted；不需要PAAcodec。校验是PA lookup3-family而非CRC32，
必须沿现有inprocess checksum override，避免自动native accelerator。PAA不增加PATHC项。

**当前项目CLI未直接支持这项PAA**：通用loader只接crimsonmc_新名与固定Steve替换路径；SteveFLAGS/报告集合/owner
没有motion。下一实现只允许这一个字面原路径、41592B、origB5/candidate909、flags2和97-key/776B合同，
不能放开任意原名/路径。strict15资源/13报告保留旧69a计划14项encoded/hash/flags/orig_size逐字保持。
推荐同结构A=原B5/B=Y5，先标准闭游戏restore当前f6169f/0041，再新receipt安装；每段restore→fresh install。
[事务审阅](../build/steve-paa-visual-20261012/transaction-review/review.json)明确singleactive/sharedlock不支持直接0042叠装，
不得换state_root/复用旧UUID/覆盖0041。逻辑只新增这一PAA，物理2meta＋3owned文件；原34sourceIndexes/0009 PAZ不写，
PATHC-after A/B/currentSteve一致。最后返回原14资源Steve模式时用标准恢复及新合法收据，保留最新存档。

[具体计划](../build/steve-paa-visual-20261012/root-audit/visual-experiment-plan.json)固定备份/异常路径：
每段改包前验证闭进程、version/receipt/owner/plan、两meta备份与SHA、34源索引、owned文件和最新save/MC/原点/ASI。
每次玩法后先记录最新保存，资源restore不覆旧saveBackup；普通异常按现事务有限回滚，metadata/owner/版本外改、
tmp/hardstop未知或进程未结束则停止，不强杀/盲覆盖。B崩溃只记兼容失败，确认进程结束后标准恢复，不重试B。
组合A/B包、专用入口和隔离故障/保存测试**尚未实现**；本轮准备计划，下一步骤先完成这些本地可验证项，之后父任务协调用户。

5°可测性见[视觉审阅](../build/steve-paa-visual-20261012/visual-review/feasibility.json)：旧A下左支133/348/349和
每LOD左臂/袖240顶点可能继承肩变化，肘参考位移约骨长8.7%；30–60像素上臂理想侧向投影仅约2.6–5.2像素。
这是量级示例，未校准世界单位、真实palette/约束/投影未知；保持5°，不擅增角度或第二资源。

父任务在包/恢复检查完成后，一次集中给用户以下动作，主控负责所有安装和恢复：
1. 同一安全平地起点、Steve/装备/移动状态；设近距后左斜镜头使左臂/手无遮挡，保持FOV/角度/距离。
2. A1录站2秒→仅W10秒→松2秒，不Shift/转鼠标/攻击/换装备；如W实际jog，记下并让三段一致。
3. 正常退出，主控核闭进程/最新保存，standard restore A→新receipt B；按协调重新进入同一存档。
4. B录完全相同动作；出现crash/几何或控制损坏立即停止B，不换片段/角度。
5. 正常退出或确认崩溃进程结束，主控restore B→A2；录同段验证恢复，再退出/清理并返回原14项Steve基线。
6. 对齐多组可见步态相位，比较左肩/臂/腕相对躯干轮廓，以右臂/头/躯干/腿作变化控制，保留三段录像。

**可见影响**：B独有可重复左支差异超过A1/A2自然变化，其他状态可比，A2返回；仅支持该resource在此配置有可见影响。
**无检出/无效**：无稳定变化或低于分辨率，不排除clip使用；cache/metabin/变体/blend/IK/投影/遮挡/5°小均可能。
**混淆**：A1/A2自身或镜头/状态/控制区域变动足以解释B，记不确定。
**crash/损坏**：停止B、保留日志/receipt/最新保存后恢复，不据此认定当前clip或乘法正确。
只有boot/W无crash也不证明PAA读取；视觉验证不记为MC动作/六刚体完成。本轮visual0，始态保护17/17、55备份保持，无上传。

## 最新：新阶段授权后的Y5诊断候选已经生成

父任务明确将下一阶段扩展到自写标准库候选生成，持续开发授权已覆盖此安全可逆实现；无需因之前自设编辑边界
再求用户确认。旧pending请求保持历史，仅该自写派生文件范围被新授权覆盖；不增加codec调用或游戏安装资格。
[授权及输入保护](../build/steve-paa-y5-20261012/root-audit/before-custody.json)17/17，原17dirty一致；
固定Python3.12 SHA4d6f…、writer fb0e…、41592B输入B5、轨表14c94856、已消费codec证据保持。

实际自写writer调用**2次**：
首[执行记录](../build/steve-paa-y5-20261012/root-audit/execution-record.json)exit1，未生成candidate；
原[失败报告](../build/steve-paa-oracle-20261012/root-audit/pending-y5-offline-candidate/writer-result.json)及marker/原稿保持。
明确失败原因是rawSha范围关联：owned_layout写digest(data[pos:end])，pos=valuesOffset15752。
970B keys SHA04d32fb2…，而972B count+keys SHAad99ab59…；初稿与此前纯静态审阅漏把后者当作前者。
这不是动画parse歧义或量化失败，也不放宽门禁。另存[修正说明](../build/steve-paa-y5-20261012/root-audit/corrected-writer-record.json)，
仅将键摘要范围改[15752,16722)、独立核u16count97并改新owned输出目录；fb0e原源码/失败目录不变。

[修订自写源码](../build/steve-paa-y5-20261012/root-audit/prepare_single_shoulder_candidate_r2.py)SHA1d170043…，
固定Python -I -S -X utf8 -B加--approved-offline-y5，在准确诊断后完成同一已授权目标；
[执行r2](../build/steve-paa-y5-20261012/root-audit/execution-record-r2.json)exit0/约0.123秒。
新[派生PAA](../build/steve-paa-y5-20261012/root-audit/candidate-r2/cd_phm_00_00_nor_move_walk_f_00.y5-diagnostic.paa)
为41592B，SHA909dd356f6087862e23a37596f4a229b310d87dc8d11ef04e88c8524e554b675。
实际547B变化，全在97个existing half-quaternion组件共776B允许集合中；范围外0差异，u16frames0..96、
header/flags/root/unit/duration/counts/scale/translation/其他全部原字节保持。
[writer结果](../build/steve-paa-y5-20261012/root-audit/candidate-r2/writer-result.json)SHA df80d2ab…，
最大量化角误差0.009823435°、norm误差0.000235124，均在原0.1°/0.0005阈值内；finite/hemisphere门禁通过，
input/table末读保持。独立原件/候选字节、原帧、quaternion及来源复核另存
[独立报告](../build/steve-paa-y5-20261012/independent-candidate-review/review.json)SHAea0d99ac…，
9资源+2保护=11/11通过、失败0；范围外40816B逐字同原件，全部97half组件与Y5逐条吻合，96对相邻同半球，
原件/表/两版源码/首失败保持。不执行writer/codec或重跑旧oracle。

候选只证明限定的派生字节/量化合同，**不证明实际walk_f_00选择、游戏乘法语义、引擎接受或MC动作**。
原Spine与全链2e-6阈值失败仍保持。下一最小实际验证优先未改原片段同epoch actor→有效contributing clip/
精确来源/cursor→PAB/PAC/PABC/receipt和101/71已知空间姿态、混合/IK/约束；frame7在两假设间约29.98°。
当前正式出口未知，不要求盲装候选或扩大扫描。“安装后无变化”无法分开未选中/未应用/语义或后处理。
游戏接受性必须另立可逆闭游戏/41文件/metadata/ownership/receipt/最新存档门禁，目前无安装计划准入。
新文件均ignored build；未启动游戏/MC、实采原生内存或调用、安装、上传，原输入与用户数据保持。
终态保护另存[after-custody](../build/steve-paa-y5-20261012/root-audit/after-custody.json)。

## 最新：语义oracle结果、旧工具意图A及新的条件请求

本节继续用户授权的自写离线分析。下方X5°方案保留历史，不再作为明显swing轴；没有候选生成或安装。
[自写oracle](../build/steve-paa-oracle-20261012/root-audit/oracle-result.json)仅读三份固定JSON，4有限数学夹具、97保存keys，
验证Hamilton xyzw rowR(a×b)=R(b)R(a)及独立cross-vector路径；
[独立r2](../build/steve-paa-oracle-20261012/independent-oracle-review/review-r2.json)16/16通过，保留r1自身边界误写。
A=q_bind×q_delta/B=q_delta×q_bind的预测角差0.916519°–29.976520°，缺真实求值标签不能只从自洽性选择。

新增明确来源：旧[local-tool inventory](../build/steve-paa-route-20261012/local-tool-audit/report.json)已盘点alpha.22 pose.py，
本轮仅git cat-file固定缓存blob28b3c98，禁lazyfetch，12577B/SHA66ff7fe2/OID逐字验证；
[源码文字](../build/steve-paa-oracle-20261012/root-audit/alpha22-pose-source.txt)及
[静态确认](../build/steve-paa-oracle-20261012/root-audit/cached-pose-text-review.json)证实旧compose L175–189采用
normalize(q_bind×q_delta)。这是旧离线实现意图A的主来源，补足此前只有新75e转述的缺口；未导入/执行源码，
既有MIT许可保持，不把工具实现当engine pose ABI、实际clip或MC应用。

肩→肘回101local为(.320711772,2.4216e-6,1.3504e-6)，与+X偏0.000495344°。
在A下delta右乘X5°主要扭转，肘位移2.41885e-7；B预测.025120655。Y5°对照A .027978502/B .012375423，
全为未校准资产单位的rotation-only假设，父/scale/translation保持，不是人物真实位移或MC摆臂。
Spine16原3.395e-6以及7local链重组肩bind2.225e-6都超过2e-6；失败保持。
它不推翻101/71直接数学关系或hash映射，但不能用作完整绝对pose准入；相对实验应读取已知空间的同帧父输出。

**实际walk_f_00选择未通过，engine乘法未通过。**无需先改动画，原片段frame7的两个预测已差约29.98°；
最小游戏观测合同见[条件观察](../build/steve-paa-oracle-20261012/semantics-review/minimal-observation-contract.json)和
[clip审阅](../build/steve-paa-oracle-20261012/clip-review/review.json)。先要正式per-actor出口同epoch绑定有效clip/
确切来源/实际cursor/PAB/PAC/PABC/receipt及101/71姿态；非整数phase必须有可验证插值，语义判断还要无未解释混合/
IK/约束或其完整已知贡献。当前出口未知，不请求开游戏、不猜输入/ABI、也不扩大callee/global/vtable扫描。
“安装后没变化”无法区分未选中、没应用和语义/后处理；不能作为阳性或阴性选择证据。

下一离线候选已经具体化为新的
[批准请求](../build/steve-paa-oracle-20261012/root-audit/offline-candidate-approval-request.json)及
[DORMANT自写源码](../build/steve-paa-oracle-20261012/root-audit/prepare_single_shoulder_candidate.py)：
只拟在旧工具意图A下，对固定41592B副本的track29现存97rotation keys右乘Y5°，最大776B组件白名单，
其余u16 frames/root/scale/translation/header/flags/unit/duration/opaque和长度逐字保持，量化角误差≤0.1°、norm误差≤0.0005。
不使用第三方codec，不下载/启动/安装；原输入不写，新输出拒绝覆盖，失败也保留一次attempt和三态readback报告。
当前委托明确禁止动画修改，**该脚本未运行、候选不存在**；需主窗口另行明确允许这一次复制文件编辑。
这份离线候选只验证限定字节/量化，不决定实际clip、engine语义或MC走路；游戏安装仍未准入。
源码及请求可审查，不把新一般“继续”当既有单次codec授权续期，也不借此安装。

## 最新：保存轨表的肩骨映射与待执行单肩方案

本次用户明确允许保存表/固定PAB的只读与自写分析，禁止重跑codec、改动画或安装。
[主控映射](../build/steve-paa-shoulder-20261012/root-audit/mapping-result.json)：固定14c94856…轨表与
a1180fc7…447骨记录，72/72rawhash唯一对应，全部父链有效无环；独立13/13通过。
目标track29→PAB101 `Bip01 L UpperArm`/0x9b5df434；record15728..16740，rotation97keys/0..96，
countOffset15750、values15752..16722、stride10、原channel SHA04d32fb2…。
完整祖先101 UpperArm→71 LClavicle→40 Spine2→24 Spine1→16 Spine→13 Pelvis→0 Bip01→-1。
当前body的weighted slots51/82/92为133 UpArmTwist、348 Hand、349 Forearm_sub，均是101子孙且PABC覆盖；
101自身不直接加权。hash/子树兼容不证明运行时palette或MC六刚体动作。

只用stdlib读取固定PAB9c8a96…的7条已知record，原字节摘要/名称/父索引与骨表保持；
末40B的scale3/xyzw4/translation3复原第3local矩阵，7/7在预定2e-6内。肩101 normalized TRS误差3.753e-8、
local×parent71 global误差9.659e-8。全链global组合按同一阈值6/7通过（含root），Spine16为3.395e-6超限，
测量及false结果保留，不为通过而放宽阈值。它支持固定PAB本身的局部数学合同，不等于PAA delta左右乘、
世界轴/单位或原生ABI。旧三codec模块只序列化，没有pose；公开75e的q_bind*q_delta不可偷升为实际引擎证据。

**实际walk_f_00选择仍未证**。installed f6169f/41文件、phm家族目录、72hash兼容、no-op均不绑定当前actor。
下一游戏门禁需要已有正式per-actor selector/evaluator出口，同epoch证明actor→非零active/contributing clip→
确切资源/PAB/PAC/PABC/收据。只有loaded/catalog/零权重blend不能准入；当前出口未找到，不要求开游戏或新扫描。

[最小单肩方案](../build/steve-paa-shoulder-20261012/root-audit/single-shoulder-proposal.json)已经固定目标、偏移和停止条件：
拟诊断局部+X5°，normalized q_delta右乘qX仅为待证假设；97个现存half quaternion的组件span共776B，
u16 frames、root、scale/translation、flags/unit/duration/counts/其他全部字节与41592长度保持。
拟使用新的自写stdlib raw-half patcher及独立矩阵oracle，**本次未实现/未执行patcher，未生成动画候选**。
先证明delta轴/组合并具体审查patcher，再另行确认动画编辑（当前指令禁止）；量化角误差拟≤0.1°、norm误差≤0.0005，
必须报告肩子孙继承和weighted限制。实际clip选择、引擎接受、41文件可逆安装/恢复各自独立准入。
已消费的一次codec不再调用，不因缺证回到144B/44B下游。结果已形成先交付；MC走路仍未应用，无上传。

## 最新：已确认的一次原件无改动往返

用户已明确允许原提案的单次测试；下方历史准备段落及旧提案中的执行／等待确认状态均属此前检查点，
由本节实际结果取代。旧证据文件保留原字节以供复核。
本轮批准只用于固定alpha.22三模块和固定副本，不能据此修改动画或安装游戏。

起始13:54:19Z游戏关闭，native/MC不可用；17dirty和12保护组与上一终态相同，55备份仍保持。
记录在[本轮before](../build/steve-paa-noop-20261012/root-audit/before.json)，含用户“允许”的授权上下文。
固定源materialize仅3py+MIT，manifestSHA4ab542e…，326逐项断言只验证来源/AST/字节。
LICENSE原1086B/CRLF保持，首额外GitLF门禁失败保留；详见
[源清单](../build/steve-paa-noop-20261012/source-audit/source-manifest.json)。

首wrapper e386…因stdlib未预载、post-call/partial留存、preflight失败状态、布局歧义四项被拒绝，
未执行codec。r1源及[blocked审阅](../build/steve-paa-noop-20261012/execution-review/executor-pre-review.json)保留。
修后aee71f2f…不改三源、不增依赖；
[r2准入](../build/steve-paa-noop-20261012/execution-review/executor-pre-review-r2.json)SHAf289d850…，
13静态/5新fake通过，旧13profile fake只在AST保持后复用。这些不是实际codec的重复运行。

唯一命令：固定 `C:/Users/ASUS/AppData/Local/Programs/Python/Python312/python.exe` 加
`-I -S -X utf8 -B build/steve-paa-noop-20261012/root-audit/execute_once.py`。
14:20:45Z exit0，parse1/encode1/read_tracks1(pos108/wide=false/packed=false/root_full=true)，scan0/rebuild0。
自有stdlib原字节walk先证表108/首轨116、70+2/216通道、40756key bytes、完全消费与无重复hash；
根half替代布局不能完整通过，float padding逐轨保持。没有轨道编辑、pose或retiming操作。

原件、副本、输出均41592B，**逐字差异0**，共同SHA
`b5b5d5aeb0e9751242dbbe5bcf5d7f9f69e4329d08ee6cb8e2ff7d2796218085`。
完整[no-op结果](../build/steve-paa-noop-20261012/root-audit/no-op-result.json) SHA
`ee78e6a25455553225c14197c6a8b5396aceda14b562b81a41e00e29f2365f87`，failure=null/readbacks=[]，
输出写入及末读通过，私有module内存执行只用三个原字节源及批准标准库。一次marker保留，**不重跑**。
[输出副本](../build/steve-paa-noop-20261012/root-audit/output/cd_phm_00_00_nor_move_walk_f_00.noop.paa)
只在ignored build；source manifest/早期proposal的未执行状态是历史记录，不回写为新结果。

这只证明一份标准nonpacked原件的codec忠实性；没有新动画或MC动作应用，未验收游戏接受性。
下一最小离线步骤：从已保存[原字节轨表](../build/steve-paa-noop-20261012/root-audit/owned-layout.json)
读取hash，与明确phm_01.pab/9c8a96…的447骨记录核唯一肩骨/父链；不需要再解析此PAA或重新执行codec。
肩骨存在、当前模型关系和bone-local轴未证前，不改rotation；之后才准备单肩现存rotation差分，保持
timing/root/flags/rest，实际walk路由与可逆安装另立门禁。当前没有新安装包，也不重开144B/44B下游。

独立保存字节复核12/12、身份与范围门禁10/10通过，共22组：
[独立结果](../build/steve-paa-noop-20261012/result-independent-review/review.json)。
另存[保护回读](../build/steve-paa-noop-20261012/root-audit/after.json)，18/18通过；原17dirty中仅本轮5文档变化，
最新55备份、41游戏文件、36存档、生产MC及原非本轮改动保持。角色诊断13/13通过(mock)，MC/server和游戏未启动，
没有VM实采/native调用/写入或上传。当前M4a完整Steve/MC走路仍进行中。

## 历史准备检查点（执行状态由上方最新no-op结果取代）

以下各段记录批准及执行前的准备过程，其中“未物化／未执行／等待确认／no-op未验收”均为当时状态。
固定旧提案不回写，单次授权已用完；当前结果和剩余门禁以上方最新节为准。

## 本地实际工具，不从包名推断能力

本地 `vendor/research/model-path-cdmw` 的 origin 是 Ratty123/CDMW-Full，HEAD
`787680f97502522e90ec3dd1ea1889ca86452985`，README/固定包版本为 `0.11.0-alpha.22`。
vendor 工作树不是完整可运行安装；`build/cdmw-fixed-source` 和固定 ZIP 是 `LICENSE+cdmw`
裁剪提取，不含 standalone tools/docs/tests。1663 个包内 Python 源码的固定 fingerprint
`4eae434238c1fae03450774820150f82d0969288ed9506ce19578faa4a480f41` 与项目门禁匹配，
MIT 许可证 SHA `e5ee37a74e136d5edd8c0991c138a5a40465f4a10a5f5dbc4809f7edda64efd1` 保持。

**完整旧 Git 树实际已有 PAA reader/writer/test**：3581 个路径中的明确 Git blobs 本地可读，
检查禁用 lazy fetch。`parse_paa`、`encode_paa`、`rebuild_is_exact` 都存在，不能继续写
“整个固定 CDMW 提交没有 writer”。这些模块没有被本工程物化、导入或执行；测试源码存在
不代表本机测试通过。11794 是逐文件/hash/GitOID/ZIP断言数量，不是 codec 功能验收。

| 拟执行的旧缓存模块 | 字节 | SHA256 |
| --- | ---: | --- |
| tools/paa_motion/__init__.py | 436 | fe9612743c32f477c89b9ad2d37e57d4ab9734cf6a754623b3369f2c07140d61 |
| tools/paa_motion/format.py | 20855 | 0a0d21afe87a57364bb31c5fd4a0e035002e77f999e72ecca1ad04cb4b2ba185 |
| tools/paa_motion/encode.py | 9869 | 6f10805323f5a2cd01f128ece0127126ba33114f23a6014224ff64f4259dbf85 |

用户给出的新实现 `75e55037b571c891cc44cafee9fa5745b0d01163` 不在本地 Git 对象中；
公开网页可以阅读，但没有下载、安装或执行该新版。旧 cached codec 与新版不能静默互换。
详见[本地源码审计](../build/steve-paa-route-20261012/local-tool-audit/RESULT.md)及
[来源清单](../build/steve-paa-route-20261012/local-tool-audit/report.json)。

## 已观测的 walk 资源与一份原件

根使用自写标准库 PAMT 元数据读取器，只检索收据中固定的 35 个索引，逐份来源摘要及末读一致。
初始 phm+walk 名称规则在 0009 超过 2000 候选预算；前两次早停、第三次有限诊断均保留。
没有增加预算或把有限例子写成完整覆盖。随后把规则缩小到已实际观测的目录与 basename：
`character/motion/1_pc/1_phm/cd_phm_00_00_nor_move_walk`。
完整固定索引范围得 9 个候选：b/bl/br/f/fl/fr/l/r/s，均在 `0009/0.pamt` 的记录78418..78426。
精确筛选下无重复路径，配套 `.paa_metabin/.motionblending` 未匹配。

这些只证明目录、名字和档案记录存在。不能从命名认定当前玩家实际选用、空手状态、循环或方向。
全索引累计条目含不同 archive 中的内容，不是当前唯一活跃 clip 总量。
[索引报告](../build/steve-paa-route-20261012/root-audit/walk-candidate-index.json) SHA
`07cc04135b24c56395beccad220e32f819e6734e11d56f5b26d98bcc2c0c0e16`；
[有限早停诊断](../build/steve-paa-route-20261012/root-audit/walk-candidate-bounded-diagnostic.json)
属于部分覆盖。独立元数据复核16/16通过（12元数据合同+2身份+2范围），保存于
[独立索引结果](../build/steve-paa-route-20261012/index-independent-review/RESULT.md)，
不读取 PAZ 载荷；不是动画或功能验收。

唯一原件选择为 `cd_phm_00_00_nor_move_walk_f_00.paa`，使用**此前已验证的固定归档读取器**
和既有 LZ4，仅读取 `0009/16.paz` 的 `377952160+32444` 区间并回读，解压41592B到 ignored build。
没有运行 standalone PAA codec。来源索引、区间、stat、固定源码和实际 LZ4 模块末读保持。
原件 SHA `b5b5d5aeb0e9751242dbbe5bcf5d7f9f69e4329d08ee6cb8e2ff7d2796218085`。
PAMT flags2 是归档压缩标记；该 PAA 自身 flags7，不能混用。

只按精确 header 布局检查：PAR2.3、tail0..9、PAA非packed，duration声明
3.200000286102295秒，70 skeletal+2 root，key_bytes40756，预测tracks起点116。
`116+72*10+40756=41592`；前言没有 skeleton_path。
这不是完整 channel/稀疏键/骨 hash 校验，也不证明引擎30Hz时序或原字节重建成功。
[归档抽取报告](../build/steve-paa-route-20261012/root-audit/donor-archive-extraction.json)与
[header预检](../build/steve-paa-route-20261012/root-audit/donor-header-preflight.json)分别保留。

## 公开源码支持与限制

固定新[格式说明](https://github.com/Ratty123/CDMW-Full/blob/75e55037b571c891cc44cafee9fa5745b0d01163/docs/features/paa-motion-format.md)
和 reader/writer/pose/test 源码支持 PAA2.3、PAB名字hash、30Hz稀疏键与局部bind delta的离线读写路线。
这不是本机 codec 测试；上游12000 clips/45 flags及188提取原件的报道不替代本机一次逐字往返。
修改后游戏接受性未验证，CLI的PAA+PAB→GLB也不等于GLB/FBX动作导入。

首实验排除 packed：其 scale/translation 的单位仍是假设。解析回退/根精度尝试、float pad只取
首键、hash重复、未知passthrough必须显式门禁，不能只信parse成功。实际时长、帧号、root motion、
flags、bounds、unit与全部其他轨道保留，不能从未知header新建动画。
源码 `pose` 的 `q_bind*q_delta` 是骨局部组合，不是可直接写原生世界矩阵的ABI。
完整审阅与准备但未执行的单肩门禁见
[公开审阅](../build/steve-paa-route-20261012/public-code-review/PUBLIC-REVIEW.md)及
[单肩合同](../build/steve-paa-route-20261012/public-code-review/single-shoulder-contract.json)。

另只读参考 CharacterCreatorEnhanced 的
[identity.cpp](https://github.com/Khione95/Crimson-Desert-Character-Creator/blob/main/CharacterCreator/CharacterCreator/identity.cpp)
和[glide.cpp](https://github.com/Khione95/Crimson-Desert-Character-Creator/blob/main/CharacterCreator/CharacterCreator/glide.cpp)：
源码分别交换角色action/skeleton字段、按state选择action type变体。主控没有固定该main到release9.1.12
commit，也没有验证本机offset/ABI/状态对应；这些不是per-bone API，不能据此识别当前walk资源或安装hook。

## 下一项明确请求与停止条件

已准备[codec执行请求](../build/steve-paa-route-20261012/root-audit/codec-execution-proposal.json)，
状态 `awaiting_explicit_user_confirmation`。建议父任务在主窗口请求：
使用工程已缓存的 **alpha.22/787680f9** 三个固定模块，仅对这份41592B原件执行一次
`parse_paa→encode_paa` 无改动逐字比较，输出到新ignored目录。范围没有新依赖、下载、游戏操作、
动画编辑或安装。确认来源于本次委托“任何新外部工具执行需要报告准确来源、版本、动作、风险等待确认”；
当前尚未获得该次确认，故不物化/执行独立codec。

执行前固定实际Python3.12 EXE、三模块、许可证及所有导入来源；解析偏移必须等于116，不准fallback、
未知gap或歧义根精度。no-op比较不一致、未知布局、骨hash重复/缺失、输入变动都停止，保存原失败。
只有原字节往返通过后，才能另行核对 `phm_01.pab` SHA9c8a96… 与每轨原始hash。
当前PAB候选 `Bip01 L UpperArm` 为index101/hash0x9b5df434，**尚未证明该donor含此track**。
单肩候选需一条现存rotation通道的局部增量及精确差分，其他字段逐字保持；安装还须实际walk路由、
既有active收据互斥、游戏关闭、严格overlay/备份/正常退出恢复合同，不直接把PAA塞进当前包。

当前走路、完整rigid运动、动态装备禁用、攻击与碰撞/镜头均未验收；不把单肩对照称MC动作。
起始13:17:45Z游戏0进程、native/MC不可用，本轮没有启动、输入、VM采样、调用或写入。
原16dirty、最新36存档、41游戏文件、MCsrc2/build118/world19、两代原备份及最新55副本起始保持。
本轮没有提交或上传。后续保护与相关检查结果写入本轮根报告，不覆盖此前阶段的冻结报告。

## 本轮已运行的相关检查

- `python -X utf8 -B tools/check_character_probe.py`：13/13通过，仅诊断夹具，不是游戏实采。
- 独立索引脚本：12元数据合同+4辅助门禁通过，不import root/CDMW/codec，零PAZ载荷/EXE读取。
- 固定WindowsPython3.12运行本轮 `capture_final.py`：15/15保护通过，HEAD保持、原非本轮dirty保持，
  17dirty中本轮只改五文档，游戏41/最新36存档/MCsrc2/build118/world19/两代原备份/55新副本保持。
  [保护报告](../build/steve-paa-route-20261012/root-audit/after.json)留存，后续文档末读另存终态报告。
- Git差异、相对链接/围栏、JSON/Python语法在本轮根报告记录，不运行MC或消耗材料的检查。

本轮安装、单肩修改、no-op重建与当前walk选择没有验收；唯一需用户确认的下一动作是上述固定旧codec
的一次无改动离线执行，不因公开网页提供writer就跳过该次确认。
