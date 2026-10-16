# Steve 动作路由：2026-10-16 配置字段、路径修复与自然加载实采

## 路径表示修复与父动作表（本次接续）

接续开始时游戏进程为0，原ASI `9d5cdc8e…`、A2收据 `83d8dd96…` 与实际41文件保持。
修改前7份源码／文档备份并回读至 `backups/steve-motion-paths-20261016-before`。
本次继续M4a动作前置，不编辑PAA、不扩大旧5°候选，也不把黑臂观察作为动作验收。

### 固定EXE路径合同及可复现的漏报

只读磁盘EXE，版本1.0.0.2976，SHA256
`57da440d72f4db974f25fef047cf84c4dadd999a88cb2a3c5af4c9bd67fde1e7`；不访问运行中进程。
在PE的实际.pdata边界内反汇编已知函数，并末读核对来源：

- ResourceLoader.load `[0x12d00b0,0x12d02c3)`：原R8保存在R14；
  `0x12d020e/0x12d0211` 连续取 `[r14]`、`[rax]`，得到字符地址。
- PathNormalizeCtor `[0x12c6a80,0x12c6c62)`：StringData holder写入目标，holder首项存字符指针。
- 其已知直接调用child `[0x1328050,0x13280f8)` 可见反斜杠转斜杠、大写转小写、重复斜杠折叠；
  未检查两个下级callee，不声称已经证明完整规范化／前缀规则。

[两函数报告](../build/steve-motion-paths-20261016/loader-static.json) SHA
`f979666aa31b60347ec780957338373be980f0ff6b0ea5c2acd35e255787ed9c`；
[直接child报告](../build/steve-motion-paths-20261016/loader-normalize-static.json) SHA
`12bf8535fdddf89d76ee2908f8bc32ce8ddab57038bc0c98142563350c3032f0`。

旧观察器先尝试把holder内容当ASCII；字符地址 `0x0000010041414141` 的小端字节以 `AAAA\0` 开头，
会被提前接受为未匹配字符串，遗漏真正的第二跳路径。固定旧头文件实际C++回归输出
`matched=0 unmatched=1 reads=2`、预期exit42；证明存在该漏报，不证明此前实机零命中都由此造成。
新逻辑只接受 `path → holder → chars`，单入口最多8+8+199=215字节，真实NUL／ASCII／指针范围门禁保持；
新增直接一跳拒绝、ASCII指针回归，最终17/17实际C++检查通过。

另外只读查找固定EXE的 `.motionblending` 字面量，唯一已确认完整NUL字符串在RVA0x55cf020，
引用0xae154a所在片段 `[0xae1030,0xae1792)` 仅支持尾部比较候选；没有直接调用上述loader或ctor。
另一原始字节命中没有确认完整NUL字符串，不提升为加载证据。
[字面量报告](../build/steve-motion-paths-20261016/literal-xrefs.json) SHA
`76d6c80963ebaf4864dcd450e5459b23cf690d0f2fc6563795c8a2c43ea7a0b5`。

### 上级PAAC与新PAA完整路径

固定A2的35份PAMT（共68152692字节）只读解析／完整末读：actionchart/bin__下共558项PAAC，
其中PHM目录96项（lower37、upper59），未超过128记录预算。
[索引报告](../build/steve-motion-paths-20261016/paac-index.json) SHA
`93638e3c3eb257b91da86f2b297afdd96fd542333a8a57c3aeac9a68a793c50e`。

只提取 `actionchart/bin__/loweraction/1_pc/1_phm/basic_lower.paac`：0010/0.pamt record280241，
PAZ0区间 `[150403024,150483307)`，flags2，stored80283／decoded520618字节。
索引／收据／压缩区间双读、固定LZ4 4.4.5三个模块导入前后摘要及来源末读均保持。
stored SHA `e3fc67820adb7b7928d5bc59f0efbbbb758d55cf639c3586213bb9c90c16ebe2`，
decoded SHA `515926c857715df0657c57bc668e2ae1cf18d3b758c3118e35820e8950597ff7`；
[提取报告](../build/steve-motion-paths-20261016/basic-lower/readback.json) SHA
`b83a3b3839e8ff6903856f9f676bb02f57f891712db409bcdc08f76eb7444058`。

在固定decoded中复核32条PHM locomotion完整路径，均核对前置u8长度和尾NUL。
`basic_move_walk.motionblending`位于 `[288891,288968)`，相对路径是同一字符串的后缀，不算第二处引用；
旧walk、basic_stride_walk完整名均无匹配。lv2／lv3及其他邻接字符串不被解释成W输入或速度状态。
只证明字符串引用，未解析完整动作图或受控角色的图选择。
[引用报告](../build/steve-motion-paths-20261016/basic-lower-references.json) SHA
`64294db651207a9921492c11e7c174174ecb408061808f6917f75f3be464f0db`。

新PAA完整路径由已解析basic_move_walk的 `_animationFileNames[13]`（原始字节 `[2345,2399)`）
及固定CDMW路径规则得到，再用35索引精确全名查询确认唯一记录：
`character/motion/1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_ing_00.paa`，
0009/0.pamt record81242／PAZ16／offset475714496／stored21425／decoded25710／flags2。
[单路径索引报告](../build/steve-motion-paths-20261016/index-basic-walk-paa.json) SHA
`c0d6663c52ad4fa3d954ec7d5731e47d08c08af159c270e95acb1a0442483f69`。
没有读取这个PAA的PAZ payload、运行PAA codec或生成动作修改。

### 修复后六路径诊断会话

保留原四条路径并加入上述父PAAC和新PAA，不添加任意路径或重启接口；
600秒／3000000入口／128匹配硬预算保持，最坏语义读取总量降为645000000字节。
严格两跳修复与路径扩展同时发生，新旧样本差异不能全部归因于其中一个修改。
入口仍在ResolveGame成功后启用，不能覆盖更早预加载；未移动hook或新增原生调用。
任何命中仅证明这个全局入口收到了请求，不能证明受控actor使用、包字节被选取或MC播放。

`python -X utf8 -B tools/check_motion_observer.py` 17/17通过；独立诊断构建成功，ASI SHA
`62f56f40c47c761586294c3b2bfc5fc3383d047f112d29bc9a5bf667218c0c0c`、12773888字节。
维护头文件与vendor副本一致，默认构建和发布artifact未替换。
逐字复用已验8项安装／恢复事务入口（SHA `3778687179f628d6d93ac1047d344cd86e35903b808d0d8415d33d0491330df9`）
到独立本轮目录；新捕获客户端只更新候选ASI固定摘要，SHA
`7984c45f2fc28d1295902077cfb4dbdc6d0d0c4447923da21ca8173d7ce1858a`。
2026-10-16T09:07:47Z新备份后安装exit0，A2的41文件、最新存档、完整MC和原点保持；
备份 `backups/steve-motion-observer-20261016T090747.324632Z`，安装后会话为installed；实采／恢复终态见下文。

### 六路径实采：父动作表首次命中，已退出恢复

用户反馈“已进入并走动”后，主控实际执行本轮 `capture_observer.py` exit0。
[行走后快照](../build/steve-motion-paths-20261016/natural-load-20261016T091220.604473Z.json) SHA
`3a8bf328b4235a59ce6759abe78dd3f2331d15b2067c28bd4f5aed9271c74f05`。
前后进程身份一致，pid66456／creationTime100ns134366153957657539，EXE固定摘要匹配，
两HTTP响应instanceId匹配；A2的41项、收据、ASI及清单前后保持。

hookInstalled=true、state=observing；128779入口、4164丢弃、5读取失败、0非法路径、
124609未匹配、1匹配、inFlight=0，计数闭合。唯一命中为
`actionchart/bin__/loweraction/1_pc/1_phm/basic_lower.paac`，相对观察起点34062ms，flags4／thread66528。
另外三份motionblending、旧walk PAA、新basic_walk_ing PAA各0次。
这证明修订后入口能捕获该父动作表请求；没有W前快照，不能把34062ms请求归因于W动作，
也不能证明属于当前受控actor或实际选中的包字节。相同四条路径仍0命中，不能把此前零命中全部归因于指针误判。
采集仍运行解决窗口早停问题；丢弃、早期预加载、缓存与其他入口仍未排除。

请求flags4仅是入口参数，不等于PAAC索引的存储flags2。独立审阅只复核报告的计数、同实例与41项前后记录一致，
未另读进程或实际游戏文件；丢弃不构成随机抽样，不能计算其余路径未使用的置信度。

用户正常退出后，固定入口确认进程0再实际执行 `observer_session.py --restore`，exit0。
会话现restored，SHA `74846cc97b01e589569e9cd570572842d0063202efb4befec2bc7e196bebb773`；
原ASI `9d5cdc8eebbad47010f4d6e15e3afe74d630ace00332cd7032ac216c3494efe7` 与原清单
`7fab3f5ad7601197369fa611d06e7d5954ad568531cef8efb435cca2deb5f65f` 恢复。
A2收据／41项保持，恢复前后退出最新存档为28+8=36文件，MC世界19项与原点保持，
MC／原点自安装以来也保持，savesRestored=false。主控另独立读取实际41游戏文件及ASI／清单／收据通过，
游戏进程0；没有把随后核对会话中的存档摘要称为再读一次源存档。
下一项只沿父动作表与混合配置的分流／引用入口继续静态核对，不重复同一六路径试验，也不据此改PAA。


## 2026-10-16 本机 Local 接续（先前中止记录保留在下文）

本轮实测 Windows 10.0.22631，工作目录为 `C:\Users\ASUS\Desktop\CrimsonMC`；
旧任务状态接口仍为 idle／completed，没有向旧任务发消息或在其中重跑提取。
A2 收据 `b35539f8…`／`83d8dd96…`、实际41项游戏文件与4份已有分析输入逐项匹配，
游戏与Python进程均为0。修改前27份已有工作／入口／收据已复制并回读到
`backups/steve-motion-local-handoff-20261016T074212.0739817Z`；6份原生源码／构建入口另存其中的 `native-before`。
此前87项最新安全备份和38项收据备份没有被覆盖。

既有LZ4目录在当前沙箱仍拒绝访问。对原固定 `read_compressed_configs.py` 正式申请一次权限后，
实际执行成功，exit0；没有切换解压通道、改ACL或自动处理授权。两份产物已独立核对大小与摘要：

| 配置 | 解压字节 | SHA256 |
| --- | ---: | --- |
| basic_move_walk | 16306 | `55d1603fb72a30b68ff39ee5e7ba5dbf4aa186698e92f589ed741b8bf7ac79f2` |
| walk | 19833 | `580b5441bbc9e16133eb826313f964224130bcc05b0e0e086beb58c59e5fd6aa` |

存储区间5889／8084字节也与报告匹配。[提取报告](../build/steve-motion-routing-20261016/compressed-configs/readback.json)
SHA `a8fcf4f0dd5c07c4afa8a5347b74aebd026d6eaa4eb3e649ec82c5979885edf9`。
库版本为4.4.5、导入来源为已有项目依赖目录，实际模块摘要前后保持；该脚本在导入后取摘要，
不能表述为导入前已按固定库摘要准入。未执行CDMW或PAA codec。

独立纯标准库字段核对确认 `_animationFileNames` 为23／66／4项：旧B片段属于walk[3]，
字符串半开区间 `[1705,1751)`，同配置示例3的 `_animationDataIndex[0]=3`。
basic_move[13]为 `cd_phm_basic_00_00_nor_move_walk_ing_00.paa`，stride[0]为
`cd_phm_basic_00_00_nor_move_walk_f_ing2_00.paa`。维度分别为右向／前向速度加坡度、
右向／前向速度；walk的第三维度声明是转向速度。
75／66／4个示例的索引数组均在范围内；未继续解释Delaunay区间或运行时条件。
首稿把索引假定为标量而停止，失败源码保留；修订稿按声明的uint32数组解析后exit0。
[字段报告](../build/steve-motion-routing-20261016/compressed-field-review/field-review.json)
SHA `4e5eec7cfcc16a1766f0686825d19f9d4af208e2c52592d31f24d41ac346bb14`。
这些字段证明静态引用，不证明W输入选择、当前actor贡献或MC动作已应用。

新增默认关闭的固定自然请求观察器；只观察三份已确认配置与旧完整PAA路径，不新增任意路径接口。
诊断构建使用 `python -B tools/build_worldbuilder.py --motion-observer`，输出独立
`build/world-builder-motion-observer`，原 `build/world-builder` 和发布ASI保持。
已有HookResLoad内只做有限路径读取，不访问out／handler／worker，不主动加载或新增hook；
600秒、100000入口、128匹配硬上限，锁竞争丢弃并计数，PlayMode／iotrace／已装worker hook污染即停止。
GET `/api/prototype/motion-load-observation` 无参数，输出instanceId、hookInstalled和采集状态；
快照含inFlight，调用方仍须绑定实际进程身份。默认构建返回disabled。

`check_motion_observer.py` 实际编译头文件的14项隔离检查已通过。初次仅测试夹具的自定义delete
触发GCC内联配对警告；给夹具delete加noinline后保留全部严格警告并通过，未弱化生产观察逻辑。
诊断ASI已成功构建，SHA `35a94ee4f50e6d6f7d25c8c5fcc9df7877368eb8bd339a481d75a0f4bd37f7c7`，
12774400字节；维护头文件与vendor副本摘要一致，补丁反向准入通过。
临时安装／恢复入口 [observer_session.py](../build/steve-motion-routing-20261016/observer_session.py)
8项隔离事务检查通过；覆盖正常恢复、安装失败回退、目标漂移、已知中断阶段和未知临时文件拒绝。

### 首次实采：窗口被启动请求耗尽，已恢复

第一次安装前用户已启动游戏，入口在备份后重新核对进程时拒绝继续，未替换ASI。
用户正常退出且进程归零后，固定入口实际安装诊断ASI成功，备份位于
`backups/steve-motion-observer-20261016T081039.121111Z`；A2的41项保持。
用户再次进入同一存档并按W行走约10秒后，固定只读采集绑定新进程身份，
读取 `/api/status` 与观察端点；前后进程身份、A2的41文件、ASI和安装清单均保持。
[首轮自然请求记录](../build/steve-motion-routing-20261016/natural-load-20261016T081544.607285Z.json)
SHA `04b0bccac2abed4a5bd6738c55eb4361649df9471a2736579abf7f58c02bd9f4`。
hookInstalled=true，但26.859秒即达到entry_limit：100000入口、4391丢弃、1读取失败、
95608未匹配、0匹配、inFlight=0；该窗口不足以覆盖用户之后的入场行走，不能据此排除任何目标路径。
此数值也不是玩家实际使用clip的证据。

用户正常退出后，`observer_session.py --restore` 实际exit0；原ASI `9d5cdc8e…`、
安装清单 `7fab3f5a…`恢复，A2收据与41项、退出最新存档、完整MC世界及原点保持，
savesRestored=false。主控另独立回读ASI／清单／active摘要匹配。
会话记录 `observer-session.json` 当前restored，SHA `f52103e2…`。
首轮候选ASI、build.json、头文件及测试保存在上述备份的 `diagnostic-v1`。

基于首次实测，仅将后续诊断请求硬上限调整为3000000，仍保600秒／128匹配和固定四路径；
每入口最多414字节语义读取，总最坏1.242GB，非固定内存分配或磁盘读取。
本次平均速率推算3百万约806秒，不能保证其他启动负载；仍须现场核对状态与丢弃数。
新增旧100000次后仍可匹配的回归检查，未修改动画资源或扩大路径范围。

### 第二次实采：窗口持续到行走结束，仍未确认路由

修订头文件SHA `454a2fdb…`与vendor副本一致；实际C++隔离检查15/15通过，
`python -B tools/build_worldbuilder.py --motion-observer` 成功，候选SHA
`f3f0a3c49a7aff4048942fdf2e0e68bc529d52cd9189b6397afc31d18467d903`。
安装恢复入口逐字复用到独立 `build/steve-motion-routing-v2-20261016`，
先新备份至 `backups/steve-motion-observer-20261016T081937.677294Z` 后安装；首轮记录未覆盖。

同一新进程的启动样本为72790入口／4571丢弃、state=observing、ready=false。
该样本客户端最初误带首轮硬编码humanReport；原文件和客户端保留，
`startup-capture-annotation.json`明确纠正：当时尚未收到第二轮用户完成反馈。
随后删除硬编码，改为userActionValidatedByClient=false；进程／文件／观察器字段是真实读取，
人工行走完成仅以聊天中用户之后的“已进入并走动”单独关联。

收到该反馈后，同一进程的[行走后快照](../build/steve-motion-routing-v2-20261016/natural-load-20261016T082232.479693Z.json)
SHA `29310ad2289706d822b1b629a50f58c3f331f0f753290777877dc58e9a2eb38f`。
ready／hookInstalled为true，state仍observing，134249入口、5031丢弃、2读取失败、
129216未匹配、0匹配、inFlight=0；从启动样本增加61459入口、460丢弃、2读取失败、60997未匹配。
前后实际进程身份与两HTTP响应token一致，A2的41项、收据、ASI及安装清单保持。
此轮解决了首轮过早耗尽，但固定路径仍未被观察到；因并发丢弃、路径呈现方式、缓存或其他加载入口尚未排除，
零匹配不能证明三配置或旧PAA未使用，更不能选出应替换的clip。

用户再次正常退出，核实进程0后 `observer_session.py --restore` 实际exit0。
第二会话现restored，SHA `c804d6800b77405e01c301d64ed71cfbb905d9a36a4b817dafb65b56852155aa`；
原ASI `9d5cdc8e…`和清单 `7fab3f5a…`恢复，A2收据 `83d8dd96…`／41文件保持。
退出最新36存档、MC世界19文件与原点在恢复前后相同，MC／原点自安装以来也保持，savesRestored=false。
主控另独立回读41游戏文件及ASI／清单／收据通过；不把会话保存的存档摘要对比称作第二次源存档读取。

收尾验证：character只读夹具13/13、Python语法、补丁反向准入与git diff --check通过；
文档相对链接96项通过（补充本段后的总数另以收尾检查为准）。发布artifact与默认ASI构建保持，
没有PAA编辑／codec、MC材料操作或新增动作候选。下一项先对固定已知路径验证加载入口／路径表示，
必要时只沿当前三份配置的明确父引用继续；不重复相同四路径启动观察，不扩大角度，也不根据零匹配改动画。
实际受控actor的clip选择与MC六关节原生播放仍未验证。

这一路径最多证明全局自然加载请求。预加载、缓存、NPC或未实际播放都可能产生同名请求；
未命中也不能排除窗口外已缓存或路径读取失败。它不验证实际选取的覆盖包字节或人物clip权重。

## 以下为Local接续前的历史中止记录

用户纠正优先级：“黑笔从来不是重点，重点是动作。”取消等待黑臂对照反馈。
当前继续目标为真正 MC 走路；本轮只收敛原 B 无明显动作变化的选择／加载缺口，未宣称动作已实现。
后续两次明确接续已各去重检查并正式申请一次固定提取，均再次中止；最新委托要求立即报告阻碍，停止重复申请，不修改游戏文件。

## 较早中断时状态（已由上方Local接续覆盖）

中断后只读复查：CrimsonDesert／Python进程0；A2 active仍为
`b35539f80bb1430eae80823a62ff988d`，receipt SHA
`83d8dd966363a5a9d298c7c94ad4e6bb71721d7fa00cbee2ef47099b7abe4578`。
实际41文件全匹配，原plan-a SHA `d2c6c10d5b4ef76bdca748a9d56242c115df78868339f3fc15167db692322d54`。
本轮没有安装、动画编辑、游戏写入、存档回滚、MC操作或ASI构建／替换。
A2可回退路径、之前87项最新安全备份和38项收据备份保留；不要求用户再次观察黑臂或录屏。

## 已完成的有用证据

旧索引脚本把 `character/motion/` 前缀同时用于筛选 `.paa_metabin` 和 `.motionblending`，
会漏掉 `actionchart/bin__/animmeta/` 与 `character/binary/motionblending/`。
因此旧 `phmRelatedMotionMetadata=[]` 不能证明不存在配套配置。

自写纯标准库入口 [inspect_routing.py](../build/steve-motion-routing-20261016/inspect_routing.py)
只在当前34原索引＋0041覆盖索引中全等匹配7个明确路径，核每个固定SHA和末读，全部命中。
没有扫描进程或读取PAA payload，没有执行第三方模块或PAA codec。
[精确索引结果](../build/steve-motion-routing-20261016/exact-resource-index.json) SHA
`015afb4f3fbbc882d0cf71c101b839f6be6dde504ba6e320386f8fa7b720875f`。

其中旧目标的配套元数据确实是
`actionchart/bin__/animmeta/1_pc/1_phm/cd_phm_00_00_nor_move_walk_f_00.paa_metabin`，
位于0010/0.pamt record10970、0010/0.paz offset101323744，402B、flags0。
另6个motionblending均在0009/0.pamt，包含walk、basic_move_walk、basic_stride_walk等，具体区间见上述报告。

已只读提取两份未压缩原字节：basic_stride_walk 2584B，SHA
`04cb98998a70fd1cbff0c860c3fbb1f4772259cb44bce092cf3e3491ad2c3e2c`；上述metabin 402B，SHA
`03eeb4f8ea530d104ca54abc54e705c1dead96928640f46bb9f64946668a8412`。
每份均验证索引、PAZ区间双读／stat保持和本地副本末读。
[原字节回读报告](../build/steve-motion-routing-20261016/raw-configs/readback.json) SHA
`d31baa72b0fb993fbcc1f404e6e50e33c228011d9875dae0f9268876d3beb728`。

独立审阅固定 `prefab_binary.py` 源码并以自写字节读取复核后，basic_stride_walk的四个名称可明确归属
`ParameterizedMotionSpace._animationFileNames[0..3]`，不是仅有字符串共现：

| 下标 | 字符串区间 | 值 |
| --- | --- | --- |
| 0 | 1541..1598 | `1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_f_ing2_00.paa` |
| 1 | 1602..1661 | `1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_b_stride_00.paa` |
| 2 | 1665..1724 | `1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_l_stride_00.paa` |
| 3 | 1728..1787 | `1_pc/1_phm/cd_phm_basic_00_00_nor_move_walk_r_stride_00.paa` |

区间为半开；每项有u32长度前缀，1533处count=4；前一字段为phm_01.pab，后一字段为motionPhaseType="locomotion"。
粗略字符串扫描末尾的分号其实是下一项长度59的低字节0x3B，不属于路径。
[字段报告](../build/steve-motion-routing-20261016/stride-fields.json) SHA
`c6a787327603e8159bbd29ce3d677d7052117da3e3999978b84739db81d98a77`；
格式规则源码SHA `00e722d184c4cc9340aae06053900f7837c2c256e93cf1e3d3f9476775cb8f4f`。
只验证前三声明字段，不声称完整文件解析或运行时条件含义。四条均不含旧B目标，但不能证明按W正在使用basic_stride_walk。

## 两份未完成的压缩配置读取

| 精确资源路径 | 0009/0.pamt record | 0009/0.paz区间 | 压缩／原始字节 |
| --- | --- | --- | --- |
| `character/binary/motionblending/phm_locomotion/basic_move_walk.motionblending` | 37624 | 33920768..33926657 | 5889／16306 |
| `character/binary/motionblending/phm_locomotion/walk.motionblending` | 37810 | 34358784..34366868 | 8084／19833 |

两项flags均为2（既有archive LZ4），并非需要重跑PAA编解码器。
已准备 [read_compressed_configs.py](../build/steve-motion-routing-20261016/read_compressed_configs.py)，SHA
`f83dc6efed7d14551e2e0809068828844d613e3345132c4c08d7f1c6b97b1f4c`；Python3.12语法静态解析通过。
它固定上述两条索引、区间和尺寸，以工程现有LZ4 4.4.5解压，仅写ignored build，拒绝覆盖，不导入CDMW或PAA模块、不改游戏或存档。

中断的具体命令为：

```powershell
& 'C:\Users\ASUS\AppData\Local\Programs\Python\Python312\python.exe' -I -S -X utf8 -B 'C:\Users\ASUS\Desktop\CrimsonMC\build\steve-motion-routing-20261016\read_compressed_configs.py'
```

审批原因：沙箱读取现有 `build/cdmw-deps/lz4/block` 及相关库文件返回Access denied，固定原生Python此前也受沙箱启动限制；
需要正式沙箱外执行权限，而非新的外部PAA codec授权。没有尝试替换解释器、复制库、改ACL或启用其他通道绕过限制。

先前库文件哈希请求原始返回 `aborted by user after 591.9s`；旧提取请求原始返回
`aborted by user after 482.9s`。父会话给出的该次审批标识为
`manager:bc2ce9a3dffe4fee90070734d24d6366:3`，已结束。
随后按两次明确继续／打开任务窗口的委托，分别先检查同名输出目录不存在、无游戏／Python进程，再为同一固定命令正式申请一次。
两次新请求分别返回 `aborted by user after 862.3s` 和 `aborted by user after 31.9s`。
这属于工具调用中止，没有明确deny、没有exitCode／stdout成功结果，也没有仍待审批的已知请求；本次返回没有AbsolutePathBuf错误。
用户明确说明“不是我暂停的，我把他的闪电开启之后自己停的”：保留此用户陈述，不能把工具用语认作用户撤销任务或拒绝审批，
亦无证据将原因归为闪电设置。

中断后 `compressed-configs` 目录不存在，只有准备脚本；没有可读的两份解压产物。
这支持“没有完成证据”，不能反推该脚本绝对没有执行过任何读取。两次新增申请均中止，现按最新指令停止重复申请。
末次只读核对A2收据、实际41项游戏文件和四份既有分析输入摘要全部保持，报告
[approval-interrupted-readback-20261016-r2.json](../build/steve-motion-routing-20261016/approval-interrupted-readback-20261016-r2.json)，SHA
`1e37920155afbb83fbff348aad4bd83890682dee9616d8c8e4011bf6cc11c282`。独立子代理再次确认目录不存在及stride字段证据边界。

## 不重复审批可以继续做的分析，以及最小接续

本轮已独立完成上述未压缩basic_stride_walk字段映射，并核对现有原生源码的加载观察能力。
现有主动 `/resource-probe` 没有PAA别名，16KiB上限小于目标41592B，且主动加载不能证明玩家播放。
现有 `HookResLoad` 有已用ABI和guarded路径读取，可设计固定路径、限时限量的自然加载旁路；
默认日志不记录路径，现有iotrace会额外安装worker hook并含写选项，不能直接复用为本轮只读观察。
可行的最小旁路不调用reader、不释放自然handler、不读取vtable、不新增全局I/O hook；仍只证明全局加载，不证明actor贡献。
这需要源码修改、独立验证、ASI构建和单独安装恢复合同，本轮均未实施，不能称已有安全可运行接口。

当前停止在权限交互阻碍；主窗口先确认授权卡是否实际出现及客户端错误，不再次重启申请。当前不用进入游戏、录屏或做黑臂对照。
在受支持的权限交互恢复前，保留这两份配置未读的准确阻碍；不改用其他解释器、解压通道或更大动作角度绕过缺证。
后续若获得新的明确接续，仍须先查同名产物和进程，不复用已结束的请求。
获得两配置后只沿明确字段引用追一层，再决定自然加载观察或单片段可回退动作试验，不把5°无检出当作目标无效。
实际输入／装备状态→clip、资源优先级、骨绑定、MC六关节时序与原生播放仍未验证。未上传工程。
