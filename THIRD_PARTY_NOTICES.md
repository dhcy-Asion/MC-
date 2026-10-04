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
