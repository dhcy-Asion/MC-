# MC 与红沙原生资产：可复建的离线管线

2026-10-06。离线准备工具已生成并检查真实资产，输出留在忽略上传的 `build/`。
后面的临时探针另有可恢复安装与实机步骤，当前验证结果见进度文件。正式桥接仍使用
蓝色方块代理，受控角色仍是原角色；候选资产不等于全部 MC 内容或 Steve 模式已接通。

## Steve 的原版几何

```powershell
python tools/build_steve_asset.py
python tools/check_steve_asset.py
```

复用哈希固定的官方 MC Java 1.21.1 客户端，调用真实模型构造。输出
`build/steve-1.21.1/steve.gltf`、顶点二进制、64×64 皮肤及来源清单。
六个刚性关节、外层、UV、绕序、逆绑定矩阵和原版渲染比例经过 13 项检查。
官方资源缺失时可使用 `--download` 获取固定依赖，不能随意更换客户端版本。

## 方块模型与纹理

```powershell
python tools/build_block_assets.py
python tools/check_block_assets.py
```

输出在 `build/block-assets-1.21.1/`。覆盖清单解析客户端的 1062 个 blockstate 资源文件、
6766 个模型选项、2071 个模型和 1012 个纹理依赖，缺失依赖为零。
这是资源清单，**不是已验证的全部注册方块或全部合法状态表**。

目前导出六种已有基线：橡木原木、橡木木板、圆石、泥土、石头、工作台。
保留原木三轴、泥土四方向及石头四个普通/镜像选项，共 14 个 glTF、9 张原版纹理、84 个面。
顶点、默认 UV、UV 旋转及状态旋转通过固定官方 Java 模型类计算。
随机模型选项和权重都保留，没有假称执行了原版的位置随机选择；独立纹理不使用 atlas 的 UV 缩边。

7 组检查从客户端资源独立比对依赖、纹理字节、几何、UV、三轴端面、绕序及输出保护。
141 个资源 ID 的 158 个选项没有 JSON cuboid elements，包括流体、箱子、床、告示牌、
旗帜等特殊渲染类型；工具没有拿立方体或空模型冒充它们。
原生 PAC/材质、透明、动画、光照、碰撞和实际放置仍须逐类实现。

## 红沙真实模板和 Steve PAC 候选

需要已安装的 Python 3.12。依赖源码固定为 CDMW
[`787680f97502522e90ec3dd1ea1889ca86452985`](https://github.com/Ratty123/CDMW-Full/tree/787680f97502522e90ec3dd1ea1889ca86452985)，
校验 ZIP、1663 份 Python 源码的树哈希及 MIT 许可证。干净环境先准备独立依赖目录：

```powershell
py -3.12 -m pip install --target build/cdmw-deps lz4==4.4.5 cryptography==50.0.2
py -3.12 -B tools/prepare_native_steve.py --download-source --game-root "E:\SteamLibrary\steamapps\common\Crimson Desert"
py -3.12 -B tools/check_native_steve.py --rebuild
```

已有固定源目录时省略 `--download-source`；可显式传入 `--cdmw-source`、`--deps`。
本机也可省略 `--game-root`，从 ignored 安装清单读取。`--template-only` 只提取并检查原生模板。
未知 EXE SHA、源码哈希或模板内容会停止，不能用替换固定哈希的方法跳过兼容验证。

工具只读原生 `0009/0.pamt` 与相关 PAZ，导出 Kliff 身体的 PAB、PAC、prefab descriptor、
材质、PABC 与 PAPR。已验证真实 447 根骨、189 项 palette、13162 个模板顶点，
原 PAC 无编辑重建字节完全一致。所有读取项在发布前复读，拒绝混用不同快照。

`build/native-steve/steve-rig-candidate.pac` 为 288 顶点、144 三角的离线候选。
保留原生 palette、三个 draw descriptor 及其它运行 metadata；四个 LOD 都保留完整方块几何。
15 项检查包括真实模板重建、全部权重边界、候选顶点/UV/刚性权重回读、LOD 和输出链接拒绝。

候选使用真实 Head、Spine_Sub、UpArmTwist、Thigh 等骨名；辅助/扭转骨映射仍需动画、
贴合和变形验证。本节 PAC 保留原材质；下文另生成皮肤候选。外层透明、动态装备、手持点、受控身体
外观选择、重载持续应用和禁用恢复均未验证。报告的集成标志全部为 false。
**PAC 可以解析不等于模型可在红沙加载。**

## 原木静态 PAM 与原生材质候选

```powershell
py -3.12 -B tools/prepare_native_block.py
py -3.12 -B tools/check_native_block.py --rebuild
```

真实蓝色代理来自 `0000/0.pamt`，使用 **PAM 静态模型**，不是角色 PAC。
工具固定其 24 顶点/12 三角、Standard PAMI、PAMLOD、HKX、meshinfo 和 binary prefab 指纹。
无编辑重建字节相同；候选保留原立方体位置/绕序/不明确的压缩着色字段，按真实 MC
三轴端面与侧面更新 UV。低 LOD 由原来的 13 顶点/6 三角补全为 24/12，材质名与 PAMI
一致；prefab 由完整结构解析后替换 PAMI 引用并重定位指针。

`build/native-block/native-block-report.json` 列出 21 个候选资源：三张 DDS，以及三轴各六项
模型/材质/碰撞/描述资源。两张原版 16×16 纹理组成 32×16 atlas，最近邻放大到 128×64，
共八层 mip。独立 Pillow 12.2.0 逐层解码；底层最大 RGB 误差 4，低 mip 最大误差 21，
并非无损贴图。13 项检查包含真实档案重建、MC 三轴映射、材质一致性及输出保护。
原生过滤、atlas 接缝、UV 方向、光照和实际碰撞加载仍未验收，不能推广为全部方块支持。

## Steve 皮肤与材质候选

```powershell
py -3.12 -B tools/prepare_steve_material.py
py -3.12 -B tools/check_steve_material.py --rebuild
```

独立解码器默认是 PATH 上的 `python`，须安装 Pillow 12.2.0 并匹配工具固定的 DDS plugin
源码 SHA；也可传 `--decoder-python` 指定已有运行时。CDMW 仍在独立 Python 3.12 进程中使用。
自有编码器将真实 Steve 皮肤最近邻放大为 256×256 DXT5/BC3，保留 alpha；normal 为
BC5U，材质常量图为 DXT1，各九层 mip。底层最大 RGB 误差 4、平均 1.479367、alpha
误差 0；低 mip 仍有量化误差，透明裁切与采样未验证。

真实身体 sidecar 的 18 个包装/6 组变体由 SkinnedMeshSkin 改为 Plain PBR，参数形状
来自已核对的原生剑 SkinnedMeshStandard 模板（3 纹理参数及 renderSettingFlag=4）。
包装外的变体/运行属性保持原文本；未知的 morph/wrinkle/physics 依赖没有假称已解决。
`build/steve-material/steve-material-report.json` 含五项资源及全部模板 SHA。
14 项含真实重建检查通过。这些新资源没有 actor 引用；材质转换不等于受控 Steve 外观。

## 独立资源包与索引预演

```powershell
py -3.12 -B tools/prepare_asset_overlay.py --report build/native-block/native-block-report.json
py -3.12 -B tools/check_asset_overlay.py --verify-game
py -3.12 -B tools/prepare_asset_overlay.py --report build/steve-material/steve-material-report.json --output build/steve-overlay-rehearsal
py -3.12 -B tools/check_asset_overlay.py --output build/steve-overlay-rehearsal --verify-game
```

预演只写 `build/native-asset-overlay` 或显式输出，不修改游戏。独立 overlay PAMT/PAZ
包含新路径，拟议 PAPGT 将其排在原版目录前面，拟议 PATHC 注册三张完整 DDS。实际
PAPGT 有 39 项，0036～0040 是已保留的可选挂载记录（本机未安装这些 payload）；
分配器因此选空闲 0041，不能照搬 CDMW 分发容器默认 0036。

保留全部原目录的顺序/语言 flags/checksum，以及 PATHC 原 291531 项、654 份 header、
12 份碰撞与名字数据；新纹理分别增加三项。完整 DDS 显式使用 raw flags=0，不继承
PartialDDS 模板的分块存储；材料 XML 按原生 LZ4/ChaCha flags 回编码。包解码与输入
字节逐项一致，PAZ 边界/校验、PAMT 无编辑回建、完整 mip 长度及原 metadata 保留已检查。
只使用固定 CDMW Python checksum 算法，不下载/调用额外 checksum helper。

13 项检查还拒绝坏 DDS/损坏包/有效校验下的挂载或纹理记录篡改/路径和输出链接。
报告路径与所有临时路径在首个写入前统一检查，包先在 build staging 解包审核后发布。
离线预演报告的安装/显示/加载标志保持 false。挂载与卸载另有新鲜预检、所有权收据和恢复验证；
原版 PAZ/PAMT 无须被改写。

## 可恢复的原木实机探针

```powershell
py -3.12 -B tools/check_asset_probe.py
python tools/check_native_block_probe.py
# 关闭游戏后安装；只接受本项目的 21 项原木资源
py -3.12 -B tools/install_asset_probe.py --install --plan build/native-asset-overlay
# 启动并进入世界，等待原生 ready/buildOk，再生成一块诊断原木
python tools/probe_native_block.py --spawn
# 同一游戏进程内清理，随后正常退出游戏
python tools/probe_native_block.py --cleanup
py -3.12 -B tools/install_asset_probe.py --restore
```

安装器重新核对游戏版本、原索引、可选挂载和空闲目录，先备份 metadata 与存档，再写
自有目录、PATHC，最后挂载 PAPGT；收据记录每个文件的哈希与所有权。恢复先解除挂载，
恢复原 metadata，再删除自有文件。遇到其它修改或游戏仍运行时停止，不覆盖后来存档。
断电、发布失败和恢复中断的隔离测试通过；实际安装与恢复结果另记在进度文件。

对象探针只通过已验证的游戏线程 API 放置诊断对象，不请求 MC 放置或消费材料。
登记受理、物理碰撞、实际画面分别验收；对象列表没有每 UID 原生 live 标志。
日志保存进程创建时间、UID、路径和变换，清理拒绝跨重启 UID 与外部对象。
红沙创建对象时会自动选择编辑项目，并可能创建空 Untitled 项目和更新设置；这项
上游行为不能称为完全无项目副作用。诊断不调用项目保存或修改 autoload，测试前要求
关闭项目自动保存，保留原有项目文件。临时资源验证不等于正式 MC ID 映射已接通。

下一步用真实原木验证 prefab 实际加载、显示与既有碰撞，再接桥接 ID 映射；
Steve 继续验证原生骨变换和安全可恢复的外观选择。
全部原版/派生资源留在本机；Git 只发布转换代码、来源、许可证及检查摘要。
总体进度见 [progress.md](progress.md)，分发边界见 [workshop-distribution.md](workshop-distribution.md)。
