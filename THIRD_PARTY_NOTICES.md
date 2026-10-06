# Third-party notices

The native adapter and published `artifacts/native/cdmodkit.asi` are based on
[Crimson Desert World Builder](https://github.com/Moon-yungg/crimson-desert-world-builder)
commit `4dcedc8dfe1592fdee0528894389221291900b8d`, copyright (c) 2026 Moon-yungg,
under the MIT license. Its complete upstream attribution document is retained in
[licenses/World-Builder-THIRD-PARTY.md](licenses/World-Builder-THIRD-PARTY.md).

The accompanying license texts are in `licenses/`:

- World Builder — MIT.
- Dear ImGui 1.91.5 — MIT, copyright (c) 2014–2024 Omar Cornut.
- MinHook 1.3.3 — BSD, copyright (c) 2009–2017 Tsuda Kageyu.
- stb_image and stb_image_write — MIT / public-domain alternatives, as stated in their headers.
- GCC libgcc/libstdc++ — GPLv3 with the GCC Runtime Library Exception.
- MinGW runtime and winpthreads — licenses reproduced from the build toolchain.

The read-only character diagnostic profile in `config/character-probe-2976.json`
uses signature/layout research from [gugi97/Trinity](https://github.com/gugi97/Trinity)
commit `e0d287e002a1947a74eacedc21b95bb021d9f5fe`, copyright (c) 2026
XeTrinityz, under MIT. Its license is retained in `licenses/Trinity-MIT.txt`.
The world-root signature and transform layout use the World Builder commit above.
This diagnostic does not install Trinity, call its game functions or enable its
gameplay modifications.

The preparation script downloads Ultimate ASI Loader, Java, Gradle, Fabric and
Minecraft dependencies from their upstream sources. These downloads and Minecraft
game binaries are excluded from this repository. Minecraft and Crimson Desert
remain the property of their respective owners. No original game assets or
personal saves are included.

Simplified Chinese item names use the Minecraft 1.21.1 language asset listed in
[official asset index 17](https://piston-meta.mojang.com/v1/packages/9b16298b1dc0697878cec88bb2d96168f5239e4f/17.json),
SHA-1 `f87510f4509890eaf176e0de1430f6bb326a6800`. Setup downloads and verifies
this data into ignored `downloads/`; it is not distributed in the plugin JAR or
this repository. Minecraft's ownership and EULA continue to apply.

Local item type previews use the Minecraft 1.21.1 enhanced renders from
[TinyTank800/MinecraftAllImages](https://github.com/TinyTank800/MinecraftAllImages/tree/8888a461f088c6b907f13c14f25a12d90a481ae3),
commit `8888a461f088c6b907f13c14f25a12d90a481ae3`. The gallery/export tooling is
MIT, copyright (c) 2025 TinyTank800; the license is retained in
[licenses/MinecraftAllImages-MIT.txt](licenses/MinecraftAllImages-MIT.txt).
The images are Minecraft game renders, not original CrimsonMC art; Minecraft
assets remain the property of Mojang/Microsoft. Setup verifies archive SHA-256
`ccd08c21dce8fdc16985784329ea73a4dfa3e885342d94afd6b47fb68442dab8`
and prepares 1332 ID-specific local files, including seven explicitly documented
same-type component previews. The downloaded ZIP/PNGs are ignored and are not
redistributed in Git or the ASI. Names/counts/components remain MC-authoritative.

The offline Steve preparation tool uses the verified official Minecraft Java
1.21.1 client and invokes its model constructors in a separate local Java process.
Version, client/class hashes and the wide Steve skin hash are pinned in
`config/steve-asset-1.21.1.json`. The helper and conversion code are project source;
the client, skin, engine geometry dump and derived glTF/binary remain in ignored
`downloads/` and `build/`. They are not included in Git, ASI or any distribution
package. A local export is not a redistribution license or native game integration.
See [distribution status](docs/workshop-distribution.md) for the separate release
requirements.

The offline native preparation tool downloads/uses CDMW-Full, MIT copyright
(c) 2026 Ratrider, pinned to
[787680f97502522e90ec3dd1ea1889ca86452985](https://github.com/Ratty123/CDMW-Full/tree/787680f97502522e90ec3dd1ea1889ca86452985).
Its ZIP, Python source tree and license are verified before import; source/dependencies
remain in ignored build. The MIT text is retained in `licenses/CDMW-MIT.txt`.
Crimson Desert skeleton/model/material templates and the derived Steve PAC are
local game assets and are not included in Git or the ASI. The block preparation
tool uses the same verified official MC client and original model constructors;
its blockstates, models, textures and derived glTF files likewise remain local.

The development workflow references
[universal-modder 671544554523eb3ae8048c18d4eb8973f5f19652](https://github.com/rehan-remade/universal-modder/tree/671544554523eb3ae8048c18d4eb8973f5f19652).
Its MIT license is retained in `licenses/Universal-Modder-MIT.txt`; its checkout is
ignored and its GTA-specific runtime is not bundled into this plugin.

Native texture candidate checks use [Pillow 12.2.0](https://github.com/python-pillow/Pillow/tree/12.2.0)
as an independent decoder, under MIT-CMU. The license is retained in
[licenses/Pillow-MIT-CMU.txt](licenses/Pillow-MIT-CMU.txt). Its DDS plugin source
SHA256 is checked, and the decoder binary fingerprint is recorded locally;
Pillow is not bundled in the ASI. The PNG reader and BC1/BC3/BC5 encoder are
project source, checked against the independent decoder. DDS format references
are Microsoft's [DDS guide](https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dx-graphics-dds-pguide)
and [block compression specification](https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression).
Compressed native textures, generated PAM/PAMLOD/PAMI/prefab resources, PAC/material
candidates and local archive overlays remain ignored local derivatives of game assets; none
are distributed in this repository.
