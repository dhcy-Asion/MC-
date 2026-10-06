# MC 与红沙原生资产：可复建的离线管线

2026-10-06。以下工具已经生成并检查真实资产，输出只在忽略上传的 `build/`。
它们没有修改原版归档、安装模型、注册角色或调用游戏函数；游戏中仍是原角色和蓝色方块代理。

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
贴合和变形验证。原材质尚未绑定 Steve 皮肤，外层透明、动态装备、手持点、受控身体
外观选择、重载持续应用和禁用恢复均未验证。报告的集成标志全部为 false。
**PAC 可以解析不等于模型可在红沙加载。**

## 下一步与分发

先用一块真实原木验证静态原生材质/纹理、prefab 加载和既有碰撞，再接桥接 ID 映射；
Steve 继续验证材质、原生骨变换和安全可恢复的外观选择，不能直接覆盖生产归档。
全部原版/派生资源留在本机；Git 只发布转换代码、来源、许可证及检查摘要。
总体进度见 [progress.md](progress.md)，分发边界见 [workshop-distribution.md](workshop-distribution.md)。
