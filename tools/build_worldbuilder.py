"""Build the pinned World Builder with the installed UCRT64 toolchain.

Does not install anything into the game. A literal-only LZ4 block avoids
requiring Python packages; it uses the upstream resource format unchanged.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "vendor/world-builder"
SRC = UPSTREAM / "asi/cdmodkit"
BUILD = ROOT / "build/world-builder"
TC = Path("C:/msys64/ucrt64/bin")


def run(args, cwd=SRC):
    result = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True, errors="replace")
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode})\n{result.stdout}\n{result.stderr}")
    return result.stdout


def main():
    BUILD.mkdir(parents=True, exist_ok=True)
    resource_dir = SRC / "build"
    resource_dir.mkdir(exist_ok=True)
    run([sys.executable, UPSTREAM / "scripts/check_locales.py"])
    run([sys.executable, UPSTREAM / "scripts/patch_minhook.py", UPSTREAM / "tools/minhook/src/trampoline.c"])
    raw = (SRC / "data/prefabs.tsv").read_bytes()
    extension = bytearray()
    left = len(raw) - 15
    while left >= 255:
        extension.append(255)
        left -= 255
    extension.append(left)
    (resource_dir / "prefabs.lz4").write_bytes(b"CDK1" + struct.pack("<I", len(raw)) + b"\xf0" + extension + raw)
    run([TC / "windres.exe", "-O", "coff", "-o", BUILD / "resources.o", "cdmodkit.rc"])
    mh, im = UPSTREAM / "tools/minhook", UPSTREAM / "tools/imgui"
    sources = [SRC / name for name in (
        "cdmodkit.cpp playmode.cpp environment.cpp terrain.cpp terrain_research.cpp travel.cpp "
        "terrain_live.cpp terrain_physics.cpp gpu_research.cpp http_api.cpp diag.cpp overlay.cpp input.cpp "
        "editor.cpp thumbgen.cpp heap.cpp icons.cpp i18n.cpp proj_codec.cpp wb_group_math.cpp report_projection.cpp mc_panel.cpp mc_inventory_ui.cpp"
    ).split()]
    sources += [im / name for name in (
        "imgui.cpp imgui_draw.cpp imgui_tables.cpp imgui_widgets.cpp "
        "backends/imgui_impl_dx12.cpp backends/imgui_impl_win32.cpp"
    ).split()]
    sources += [mh / name for name in "src/buffer.c src/hook.c src/trampoline.c src/hde/hde64.c".split()]
    flags = ["-O1", "-w", "-DNDEBUG", "-D_CRT_SECURE_NO_WARNINGS", "-DMINGW_HAS_SECURE_API=1",
             "-DIMGUI_DISABLE_OBSOLETE_FUNCTIONS=0", '-DIMGUI_USER_CONFIG="cd_imconfig.h"',
             "-I" + str(SRC), "-I" + str(mh / "include"), "-I" + str(mh / "src"),
             "-I" + str(im), "-I" + str(im / "backends")]
    def compile_one(pair):
        i, source = pair
        obj = BUILD / f"{i:02d}_{source.stem}.o"
        compiler = TC / ("gcc.exe" if source.suffix == ".c" else "g++.exe")
        command = [compiler] + ([] if source.suffix == ".c" else ["-std=c++17"]) + flags + ["-c", source, "-o", obj]
        # Rebuild only when the source, local headers or command have changed.
        fingerprint = hashlib.sha256((str(command) + str(source.stat().st_mtime_ns) +
                                      str(max(p.stat().st_mtime_ns for p in SRC.glob("*.h")))).encode()).hexdigest()
        stamp = obj.with_suffix(".sha256")
        if not obj.exists() or not stamp.exists() or stamp.read_text() != fingerprint:
            run(command)
            stamp.write_text(fingerprint)
        print(f"compiled {source.name}", flush=True)
        return obj
    with ThreadPoolExecutor(max_workers=3) as pool:
        objects = list(pool.map(compile_one, enumerate(sources)))
    output = BUILD / "cdmodkit.asi"
    libraries = "user32 gdi32 imm32 comdlg32 shell32 d3d12 dxgi d3dcompiler version ws2_32 ole32 uuid advapi32 dwmapi winhttp"
    run([TC / "g++.exe", "-shared", "-static", "-static-libgcc", "-static-libstdc++", "-s",
         "-o", output, *objects, BUILD / "resources.o", *["-l" + x for x in libraries.split()]])
    metadata = {"world_builder_commit": run(["git", "rev-parse", "HEAD"], UPSTREAM).strip(),
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "bytes": output.stat().st_size}
    (BUILD / "build.json").write_text(json.dumps(metadata, indent=2))
    print(json.dumps(metadata), flush=True)


if __name__ == "__main__":
    main()
