"""Build local Steve DDS/material candidates from reviewed native templates.

Run with Python 3.12 after prepare_native_steve.py. No archive, process or game
state is changed. The small, deterministic BC encoder below is project code;
Pillow 12.2.0 in --decoder-python independently decodes every output mip. This
is a candidate resource package, not proof of shader alpha behavior or loading.
"""
from __future__ import annotations

import argparse
import base64
import collections
import json
import math
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
import zlib

import prepare_native_steve as native

ROOT = native.ROOT
MATERIAL_SHA256 = "65b217b938346cc47c1207263507eaef38a24ad605f2890a4b0845c9005fc7a4"
CANDIDATE_PAC_SHA256 = "430fa4685687d41082decec695a388661740954fab426f282719e0ffe962a974"
SHADER_TEMPLATE = "character/modelproperty/1_pc/1_phm/weapon/1_onehandweapon/cd_phm_01_sword_0001_02.pac_xml"
SHADER_TEMPLATE_SHA256 = "8583bdf1fa43af33fa100e81cd6d84309a1b11a2ae75d7a2b7e39e9c1e8df9bb"
TEXTURE_TEMPLATES = {
    "base": ("character/texture/cd_phm_00_cloak_hair_0008_03.dds",
             "c0d3ab739c534453ede7e4e8afcaf2d1862038aa2ac4f46107b252e4b613180d", "DXT5", 512),
    "normal": ("character/texture/cd_phm_00_head_00_0001_01_n.dds",
               "5878681b609c2e8260b3a805ff57c415b7457267487fc58a3f81df0645507d30", "BC5U", 1024),
    "material": ("character/texture/cd_phm_00_head_00_0001_01_sp.dds",
                 "768960ceee268a893fb23a1e450ea9fe5ab58eeea3ae8bf41a011d076a643552", "DXT1", 1024),
}
TEXTURE_PATHS = {
    "base": "character/texture/crimsonmc_steve_1_21_1.dds",
    "normal": "character/texture/crimsonmc_steve_1_21_1_n.dds",
    "material": "character/texture/crimsonmc_steve_1_21_1_sp.dds",
}
PAC_PATH = "character/model/1_pc/1_phm/nude/crimsonmc_steve_1_21_1.pac"
MATERIAL_PATH = "character/modelproperty/1_pc/1_phm/nude/crimsonmc_steve_1_21_1.pac_xml"
DRAW_NAMES = ("cd_phm_00_head_0001_01", "cd_phm_00_nude_0001_hand", "cd_phm_00_nude_0001")
PILLOW_VERSION = "12.2.0"
PILLOW_DDS_PLUGIN_SHA256 = "25184318584a5efa250220ff5f8fe7610dc3011a20bb686613602166e19cd364"
FORMAT_SOURCES = (
    "https://learn.microsoft.com/en-us/windows/win32/direct3ddds/dx-graphics-dds-pguide",
    "https://learn.microsoft.com/en-us/windows/win32/direct3d10/d3d10-graphics-programming-guide-resources-block-compression",
)


def decode_png(data: bytes) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Read bounded RGB8, RGBA8 or indexed1/2/4/8 PNG; unknown formats stop."""
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 4 * 1024 * 1024:
        raise ValueError("PNG signature/size is unsupported")
    cursor, chunks, compressed, palette, alpha = 8, [], bytearray(), b"", b""
    header = None
    while cursor < len(data):
        if cursor + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, cursor)[0]
        kind = data[cursor + 4:cursor + 8]
        payload = data[cursor + 8:cursor + 8 + length]
        end = cursor + 12 + length
        if end > len(data) or zlib.crc32(kind + payload) & 0xFFFFFFFF != struct.unpack_from(">I", data, end - 4)[0]:
            raise ValueError("PNG chunk checksum/size mismatch")
        chunks.append(kind)
        if kind == b"IHDR":
            if header is not None or len(payload) != 13 or len(chunks) != 1:
                raise ValueError("PNG has invalid IHDR ordering")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            if palette or b"IDAT" in chunks or len(payload) % 3 or not 3 <= len(payload) <= 768:
                raise ValueError("Invalid indexed PNG palette")
            palette = payload
        elif kind == b"tRNS":
            if alpha or b"IDAT" in chunks:
                raise ValueError("Invalid PNG transparency ordering")
            alpha = payload
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            if payload or end != len(data):
                raise ValueError("PNG has trailing bytes")
            cursor = end
            break
        elif kind[:1].isupper():
            raise ValueError(f"Unsupported critical PNG chunk: {kind!r}")
        cursor = end
    if header is None or not chunks or chunks[-1] != b"IEND" or not compressed:
        raise ValueError("PNG is missing image data")
    width, height, depth, color, compression, filtering, interlace = header
    if color not in (2, 3, 6) or (depth not in (1, 2, 4, 8) if color == 3 else depth != 8) or compression or filtering or interlace or not (1 <= width <= 1024 and 1 <= height <= 1024):
        raise ValueError("Only bounded noninterlaced RGB8/RGBA8/indexed PNG is supported")
    bpp = {2: 3, 3: 1, 6: 4}[color]
    if (color == 3 and (not palette or len(palette) // 3 > 1 << depth or len(alpha) > len(palette) // 3)) or (color != 3 and alpha):
        raise ValueError("Unsupported PNG transparency/palette")
    row_bytes = (width * depth + 7) // 8 if color == 3 else width * bpp
    expected = (row_bytes + 1) * height
    stream = zlib.decompressobj()
    raw = stream.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or not stream.eof or stream.unused_data or stream.unconsumed_tail:
        raise ValueError("PNG inflated size does not match its dimensions")
    previous = bytearray(row_bytes)
    pixels = []
    for y in range(height):
        start = y * (row_bytes + 1)
        method = raw[start]
        row = bytearray(raw[start + 1:start + 1 + row_bytes])
        if method > 4:
            raise ValueError("Unknown PNG row filter")
        for x in range(len(row)):
            left = row[x - bpp] if x >= bpp else 0
            up = previous[x]
            upper_left = previous[x - bpp] if x >= bpp else 0
            if method == 4:
                estimate = left + up - upper_left
                distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
                predictor = (left, up, upper_left)[distances.index(min(distances))]
            else:
                predictor = (0, left, up, (left + up) // 2)[method]
            row[x] = (row[x] + predictor) & 255
        for x in range(width):
            values = row[x * bpp:(x + 1) * bpp]
            if color == 3:
                index = (row[x * depth // 8] >> (8 - depth - x * depth % 8)) & ((1 << depth) - 1)
                if index >= len(palette) // 3:
                    raise ValueError("PNG palette index out of bounds")
                rgb = tuple(palette[index * 3:index * 3 + 3])
                pixels.append((*rgb, alpha[index] if index < len(alpha) else 255))
            else:
                pixels.append(tuple(values) if color == 6 else (*values, 255))
        previous = row
    return width, height, pixels


def nearest_expand(width: int, height: int, pixels: list, scale: int = 4) -> tuple[int, int, list]:
    if scale not in (1, 2, 4) or len(pixels) != width * height:
        raise ValueError("Unsupported pixel expansion")
    return width * scale, height * scale, [pixels[(y // scale) * width + x // scale]
                                        for y in range(height * scale) for x in range(width * scale)]


def mip_chain(width: int, height: int, pixels: list) -> list[tuple[int, int, list]]:
    """Straight-alpha weighted box filtering in encoded RGB space, explicitly a candidate policy."""
    levels = [(width, height, pixels)]
    while width > 1 or height > 1:
        w, h = max(1, width // 2), max(1, height // 2)
        reduced = []
        for y in range(h):
            for x in range(w):
                taps = [pixels[min(height - 1, y * 2 + dy) * width + min(width - 1, x * 2 + dx)]
                        for dy in range(2) for dx in range(2)]
                total_alpha = sum(p[3] for p in taps)
                rgb = tuple((sum(p[c] * p[3] for p in taps) + total_alpha // 2) // total_alpha
                            if total_alpha else 0 for c in range(3))
                reduced.append((*rgb, (total_alpha + 2) // 4))
        width, height, pixels = w, h, reduced
        levels.append((w, h, pixels))
    return levels


def _rgb565(pixel: tuple) -> int:
    r, g, b = pixel[:3]
    return ((r * 31 + 127) // 255 << 11) | ((g * 63 + 127) // 255 << 5) | ((b * 31 + 127) // 255)


def _rgb888(value: int) -> tuple:
    r, g, b = value >> 11, (value >> 5) & 63, value & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def _color_block(pixels: list) -> bytes:
    values = sorted({_rgb565(p) for p in pixels if p[3]}) or [0]
    if len(values) == 1:
        c1, c0 = (values[0], values[0] + 1) if values[0] < 65535 else (65534, 65535)
    else:
        c1, c0 = max(((a, b) for i, a in enumerate(values) for b in values[i + 1:]),
                     key=lambda pair: sum((x - y) ** 2 for x, y in zip(_rgb888(pair[0]), _rgb888(pair[1]))))
    a, b = _rgb888(c0), _rgb888(c1)
    colors = [a, b, tuple((2 * x + y) // 3 for x, y in zip(a, b)),
              tuple((x + 2 * y) // 3 for x, y in zip(a, b))]
    indices = 0
    for position, pixel in enumerate(pixels):
        index = min(range(4), key=lambda i: sum((pixel[c] - colors[i][c]) ** 2 for c in range(3)))
        indices |= index << (position * 2)
    return struct.pack("<HHI", c0, c1, indices)


def _channel_block(values: list[int]) -> bytes:
    hi, lo = max(values), min(values)
    if hi == lo:
        return bytes((hi, lo)) + b"\0" * 6
    choices = [hi, lo] + [((7 - i) * hi + i * lo) // 7 for i in range(1, 7)]
    bits = 0
    for position, value in enumerate(values):
        index = min(range(8), key=lambda i: abs(value - choices[i]))
        bits |= index << (position * 3)
    return bytes((hi, lo)) + bits.to_bytes(6, "little")


def encode_dds(width: int, height: int, pixels: list, fourcc: str = "DXT1",
               template_header: bytes | None = None, last4: int | None = None) -> bytes:
    """Deterministic BC1/BC3/BC5U; full mip chain, reviewed 128-byte header shape.

    A template retains its opaque metadata and format. last4 is only an explicit
    caller override; it cannot stand in for archive PATHC registration.
    """
    if fourcc not in ("DXT1", "DXT5", "BC5U") or width < 4 or height < 4 or width > 1024 or height > 1024 or width & (width - 1) or height & (height - 1):
        raise ValueError("Unsupported DDS dimensions/format")
    if len(pixels) != width * height or any(len(p) != 4 or any(type(v) is not int or not 0 <= v <= 255 for v in p) for p in pixels):
        raise ValueError("Invalid RGBA pixels")
    if fourcc == "DXT1" and any(p[3] != 255 for p in pixels):
        raise ValueError("This BC1 encoder accepts opaque pixels only; use BC3 for alpha")
    if template_header is not None:
        if len(template_header) != 128 or template_header[:4] != b"DDS " or template_header[84:88] != fourcc.encode("ascii") or struct.unpack_from("<I", template_header, 4)[0] != 124 or struct.unpack_from("<I", template_header, 76)[0] != 32 or struct.unpack_from("<I", template_header, 80)[0] != 4:
            raise ValueError("DDS template has an unsupported header or different format")
        header = bytearray(template_header)
    else:
        header = bytearray(128)
        header[:4] = b"DDS "
        for offset, value in ((4, 124), (8, 0xA1007), (24, 1), (76, 32), (80, 4), (108, 0x401008)):
            struct.pack_into("<I", header, offset, value)
        header[84:88] = fourcc.encode("ascii")
    levels = mip_chain(width, height, pixels)
    blobs = []
    for w, h, level in levels:
        blob = bytearray()
        for by in range(0, h, 4):
            for bx in range(0, w, 4):
                block = [level[min(h - 1, by + y) * w + min(w - 1, bx + x)] for y in range(4) for x in range(4)]
                if fourcc == "DXT5":
                    blob.extend(_channel_block([p[3] for p in block]))
                if fourcc == "BC5U":
                    blob.extend(_channel_block([p[0] for p in block]))
                    blob.extend(_channel_block([p[1] for p in block]))
                else:
                    blob.extend(_color_block(block))
        blobs.append(bytes(blob))
    for offset, value in ((12, height), (16, width), (20, len(blobs[0])), (24, 1), (28, len(blobs))):
        struct.pack_into("<I", header, offset, value)
    # The real legacy templates carry their first four mip byte counts here.
    for i in range(4):
        struct.pack_into("<I", header, 32 + i * 4, len(blobs[i]) if i < len(blobs) else 0)
    if last4 is not None:
        if not 0 <= last4 <= 0xFFFFFFFF:
            raise ValueError("Invalid explicit Crimson DDS classification")
        struct.pack_into("<I", header, 124, last4)
    return bytes(header) + b"".join(blobs)


# Runs independently in the specified existing interpreter. It imports none of
# this project's codec, and does not write files or install Python packages.
_DECODER = r'''
import base64, hashlib, io, json, struct, sys
from pathlib import Path
import PIL, PIL.DdsImagePlugin, PIL._imaging
from PIL import Image
request=json.load(sys.stdin)
if PIL.__version__ != request['version']:
    raise ValueError('Independent decoder requires Pillow '+request['version'])
plugin=hashlib.sha256(Path(PIL.DdsImagePlugin.__file__).read_bytes()).hexdigest()
if plugin != request['pluginSha256']:
    raise ValueError('Pillow DDS plugin fingerprint mismatch')
result=[]
for item in request['images']:
    data=base64.b64decode(item,validate=True)
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        result.append({'width':im.width,'height':im.height,'rgba':base64.b64encode(im.convert('RGBA').tobytes()).decode('ascii')})
json.dump({'decoder':{'name':'Pillow','version':PIL.__version__,'ddsPluginSha256':plugin,
                     'binarySha256':hashlib.sha256(Path(PIL._imaging.__file__).read_bytes()).hexdigest(),
                     'source':'https://github.com/python-pillow/Pillow/tree/12.2.0',
                     'license':'MIT-CMU'},'images':result},sys.stdout)
'''


def independent_decode(images: list[bytes], decoder_python: Path) -> tuple[dict, list]:
    request = {"version": PILLOW_VERSION, "pluginSha256": PILLOW_DDS_PLUGIN_SHA256,
               "images": [base64.b64encode(data).decode("ascii") for data in images]}
    child = subprocess.run([str(decoder_python), "-B", "-c", _DECODER], input=json.dumps(request),
                           text=True, capture_output=True, timeout=60, check=False,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if child.returncode:
        raise ValueError("Independent Pillow decoder failed: " + child.stderr.strip()[-1000:])
    response = json.loads(child.stdout)
    if len(response["images"]) != len(images):
        raise ValueError("Independent decoder returned an incomplete batch")
    return response["decoder"], [(item["width"], item["height"],
                                 [tuple(data[i:i + 4]) for i in range(0, len(data), 4)])
                                for item in response["images"]
                                for data in [base64.b64decode(item["rgba"], validate=True)]]


def split_dds_mips(data: bytes) -> list[bytes]:
    from cdmw.core.dds_native import inspect_dds_native
    info = inspect_dds_native(data)
    if info.reason or not info.supported_compressed or len(info.mip_levels) != info.mip_count or info.data_offset != 128 or info.fourcc not in ("DXT1", "DXT5", "BC5U"):
        raise ValueError("DDS output failed fixed CDMW header/mip inspection")
    if info.mip_levels[-1].offset + info.mip_levels[-1].byte_count != len(data):
        raise ValueError("DDS output has unaccounted trailing payload")
    result = []
    for mip in info.mip_levels:
        header = bytearray(data[:128])
        for offset, value in ((12, mip.height), (16, mip.width), (20, mip.byte_count), (28, 1)):
            struct.pack_into("<I", header, offset, value)
        result.append(bytes(header) + data[mip.offset:mip.offset + mip.byte_count])
    return result


def verify_texture(data: bytes, width: int, height: int, pixels: list, fourcc: str,
                   decoder_python: Path) -> tuple[dict, dict]:
    """Check every BC mip using Pillow; measure colour loss instead of claiming lossless."""
    mip_bytes = split_dds_mips(data)
    decoder, decoded = independent_decode(mip_bytes, decoder_python)
    expected = mip_chain(width, height, pixels)
    if len(decoded) != len(expected):
        raise ValueError("Independent decoder lost a mip")
    checks = []
    for level, ((w, h, reference), (dw, dh, actual)) in enumerate(zip(expected, decoded)):
        if (w, h) != (dw, dh) or len(actual) != w * h:
            raise ValueError("Independent DDS decoded dimensions differ")
        channels = (0, 1) if fourcc == "BC5U" else (0, 1, 2)
        errors = [abs(p[c] - q[c]) for p, q in zip(reference, actual) if p[3] for c in channels]
        alpha_error = max((abs(p[3] - q[3]) for p, q in zip(reference, actual)), default=0) if fourcc != "BC5U" else 0
        if level == 0 and (max(errors, default=0) > 4 or alpha_error):
            raise ValueError("Base mip exceeds RGB565 quantization or changed authored alpha")
        if fourcc == "BC5U" and max(errors, default=0) != 0:
            raise ValueError("Flat normal map changed its authored XY channels")
        checks.append({"level": level, "width": w, "height": h,
                       "maxRgbError": max(errors, default=0),
                       "meanRgbError": round(sum(errors) / len(errors), 6) if errors else 0,
                       "maxAlphaError": alpha_error})
    return decoder, {"fourcc": fourcc, "width": width, "height": height,
                     "mipCount": len(checks), "independentDecode": checks,
                     "sourceAlphaCounts": dict(sorted(collections.Counter(p[3] for p in pixels).items()))}


def wrap_xml(text: str) -> ET.Element:
    return ET.fromstring("<CandidateDocument>" + text.lstrip("\ufeff") + "</CandidateDocument>")


def material_candidate(original: bytes, shader_template: bytes) -> tuple[bytes, dict]:
    from cdmw.core.pac_xml_standard_material import PlainMaterial, find_material_wrappers, rewrite_materials
    if native.sha256(original) != MATERIAL_SHA256 or native.sha256(shader_template) != SHADER_TEMPLATE_SHA256:
        raise ValueError("Material template fingerprint mismatch")
    text = original.decode("utf-8-sig")
    wrappers = find_material_wrappers(text)
    if len(wrappers) != 18 or collections.Counter(w.submesh_name for w in wrappers) != collections.Counter({name: 6 for name in DRAW_NAMES}) or any(w.shader != "SkinnedMeshSkin" for w in wrappers):
        raise ValueError("Body material has unknown wrappers/variants")
    donor = [w for w in find_material_wrappers(shader_template.decode("utf-8-sig")) if w.shader == "SkinnedMeshStandard"]
    required = {"_baseColorTexture": ("Texture", "3"), "_normalTexture": ("Texture", "2"),
                "_materialTexture": ("Texture", "1"), "_renderSettingFlag": ("BitFlag32", "0")}
    if not donor or any({p.name: (p.kind, p.item_id) for p in w.parameters if p.name in required} != required or w.value("_renderSettingFlag") != "4" for w in donor):
        raise ValueError("Reviewed native plain shader contract changed")
    plain = PlainMaterial(base=TEXTURE_PATHS["base"], normal=TEXTURE_PATHS["normal"],
                          material=TEXTURE_PATHS["material"], render_flag=4)
    result = rewrite_materials(text, {name: plain for name in DRAW_NAMES})
    if result.missing or len(result.rewritten) != 18:
        raise ValueError("Not every material variant was rewritten")
    rewritten = find_material_wrappers(result.text)
    if [w.submesh_name for w in rewritten] != [w.submesh_name for w in wrappers] or any(w.shader != "SkinnedMeshStandard" or w.textures != {"_baseColorTexture": TEXTURE_PATHS["base"], "_normalTexture": TEXTURE_PATHS["normal"], "_materialTexture": TEXTURE_PATHS["material"]} or len(w.parameters) != 4 for w in rewritten):
        raise ValueError("Candidate retains inherited skin/damage/dye parameters")
    # Apart from Material blocks, preserve every variant, wrapper identity and
    # engine property byte for byte. Morph/wrinkle dependencies remain untested.
    strip = lambda value, rows: "".join(value[end:start] for end, start in zip([0] + [w.end for w in rows], [w.start for w in rows] + [len(value)]))
    if strip(text, wrappers) != strip(result.text, rewritten):
        raise ValueError("Material rewrite changed opaque wrapper/property metadata")
    wrap_xml(result.text)
    return result.text.encode("utf-8"), {"wrappers": 18, "variants": 6,
        "drawNames": list(DRAW_NAMES), "shader": "SkinnedMeshStandard",
        "renderSettingFlag": 4, "alphaBehaviorVerified": False,
        "inheritedSkinMaterialParametersRemoved": True, "opaquePropertyMetadataPreserved": True}


def read_native_templates(game: Path) -> tuple[dict, str]:
    from cdmw.core.archive_format import parse_archive_pamt
    from cdmw.core.archive_extraction import read_archive_entry_raw_data, _decode_archive_entry_data
    from cdmw.core.dds_native import inspect_dds_native
    if native.file_hash(game / "bin64" / "CrimsonDesert.exe") != native.EXE_SHA256:
        raise ValueError("Unsupported Crimson Desert EXE; texture preparation stopped")
    index = game / "0009" / "0.pamt"
    index_hash = native.file_hash(index)
    paths = tuple(row[0] for row in TEXTURE_TEMPLATES.values()) + (SHADER_TEMPLATE,)
    selected = native.select_unique_entries(parse_archive_pamt(index), paths)
    files = {path: _decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0]
             for path, entry in selected.items()}
    if native.sha256(files[SHADER_TEMPLATE]) != SHADER_TEMPLATE_SHA256:
        raise ValueError("Native plain-shader source fingerprint mismatch")
    for path, expected, fourcc, dimension in TEXTURE_TEMPLATES.values():
        data = files[path]
        info = inspect_dds_native(data)
        if native.sha256(data) != expected or info.reason or info.fourcc != fourcc or (info.width, info.height) != (dimension, dimension) or info.mip_count != int(math.log2(dimension)) + 1:
            raise ValueError(f"Native DDS format/template changed: {path}")
        if struct.unpack_from("<I", data, 24)[0] != 1:
            raise ValueError("Unknown native DDS depth")
    if native.file_hash(index) != index_hash or any(_decode_archive_entry_data(entry, read_archive_entry_raw_data(entry))[0] != files[path] for path, entry in selected.items()):
        raise ValueError("Native texture snapshot changed while reading")
    return files, index_hash


def publish(output: Path, files: dict[str, bytes], report: dict) -> None:
    files = {**files, "steve-material-report.json": (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8")}
    output = native.output_directory(output)
    for name in files:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name or ":" in name or not relative.parts:
            raise ValueError("Asset output path escapes its build directory")
        native.check_links(output / name)
        native.check_links((output / name).with_suffix(Path(name).suffix + ".tmp"))
    for name, data in files.items():
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        native.check_links(target)
        temporary = target.with_suffix(target.suffix + ".tmp")
        native.check_links(temporary)
        temporary.write_bytes(data)
        temporary.replace(target)


def prepare(game: Path, output: Path, source: Path, deps: Path | None, asset: Path,
            native_assets: Path, decoder_python: Path) -> dict:
    output = native.output_directory(output)
    provenance = native.load_cdmw(source, deps)
    for directory in (asset, native_assets):
        native.check_links(directory)
    png = (asset / "steve.png").read_bytes()
    original_material = (native_assets / "template" / native.MATERIAL).read_bytes()
    candidate_pac = (native_assets / "steve-rig-candidate.pac").read_bytes()
    if native.sha256(png) != native.STEVE_HASHES["steve.png"] or native.sha256(candidate_pac) != CANDIDATE_PAC_SHA256:
        raise ValueError("Official Steve image/native geometry fingerprint mismatch")
    width, height, pixels = decode_png(png)
    if (width, height) != (64, 64):
        raise ValueError("Unknown official skin dimensions")
    decoder, [independent_png] = independent_decode([png], decoder_python)
    if independent_png != (width, height, pixels):
        raise ValueError("Stdlib PNG decoder differs from independent Pillow")
    templates, index_hash = read_native_templates(game)
    material, material_audit = material_candidate(original_material, templates[SHADER_TEMPLATE])
    w, h, expanded = nearest_expand(width, height, pixels, 4)
    maps = {"base": expanded, "normal": [(128, 128, 255, 255)] * (w * h),
            "material": [(0, 255, 0, 255)] * (w * h)}
    files = {f"template/{path}": data for path, data in templates.items()}
    resources, audits = [], {}
    for kind, reference in maps.items():
        path, _expected, fourcc, _dim = TEXTURE_TEMPLATES[kind]
        # Keep the actual template's last4 until the package builder explicitly
        # resolves PATHC for its new path. Source classification is not guessed.
        dds = encode_dds(w, h, reference, fourcc, templates[path][:128])
        _decoder, audit = verify_texture(dds, w, h, reference, fourcc, decoder_python)
        if _decoder != decoder:
            raise ValueError("Independent DDS decoder changed during preparation")
        audit["templatePath"] = path
        audit["templateLast4Preserved"] = struct.unpack_from("<I", dds, 124)[0]
        audits[kind] = audit
        name = "resources/" + TEXTURE_PATHS[kind]
        files[name] = dds
        resources.append({"virtualPath": TEXTURE_PATHS[kind], "localFile": name,
                          "sha256": native.sha256(dds), "kind": "texture", "templatePath": path,
                          "templateSha256": TEXTURE_TEMPLATES[kind][1]})
    for path, data, kind, template in ((PAC_PATH, candidate_pac, "skinnedMesh", native.BODY),
                                       (MATERIAL_PATH, material, "skinnedMaterial", native.MATERIAL)):
        name = "resources/" + path
        files[name] = data
        resources.append({"virtualPath": path, "localFile": name, "sha256": native.sha256(data),
                          "kind": kind, "templatePath": template,
                          "templateSha256": native.TEMPLATE_HASHES[native.BODY] if kind == "skinnedMesh" else MATERIAL_SHA256})
    report = {"schemaVersion": 1, "supportedExeSha256": native.EXE_SHA256,
        "cdmw": provenance, "archiveIndexSha256": index_hash,
        "inputHashes": {"steve.png": native.STEVE_HASHES["steve.png"], "body.pac_xml": MATERIAL_SHA256,
                        "steve-rig-candidate.pac": CANDIDATE_PAC_SHA256},
        "textureEncoding": {"encoder": "CrimsonMC stdlib BC1/BC3/BC5U", "formatReferences": list(FORMAT_SOURCES),
                            "nearestScale": 4, "mipPolicy": "straight-alpha weighted box in encoded RGB space",
                            "lossless": False},
        "independentDecoder": decoder, "textures": audits, "material": material_audit,
        "candidateResources": resources,
        "files": {name: native.sha256(data) for name, data in files.items()},
        "integration": {"nativeMaterialLoaded": False, "alphaBehaviorVerified": False,
                        "animationVerified": False, "equipmentBound": False,
                        "controlledAppearanceBound": False, "nativeRenderable": False,
                        "archiveRegistered": False, "installed": False},
        "limitations": [
            "The plain shader has a verified stock parameter shape; its alpha/cutout behavior on Steve's overlapping outer parts is unverified.",
            "Source DDS last4 fields are retained; new resource PATHC/package metadata must be resolved and validated before loading.",
            "Flat normal XY and G=255/B=0 matte/nonmetal maps are authored candidates; material red channel and lighting need game validation.",
            "PAC morph/wrinkle/property metadata is retained; fitting, animation, UV orientation/filtering and controlled-body lifecycle are unverified.",
            "New PAC and sidecar paths have no appearance/controller binding; adding an archive does not select this character.",
            "All Minecraft and native template payloads remain local ignored build assets and are not redistributable package approval.",
        ]}
    # Consumed local exports must remain the same snapshot through publication.
    if (asset / "steve.png").read_bytes() != png or (native_assets / "template" / native.MATERIAL).read_bytes() != original_material or (native_assets / "steve-rig-candidate.pac").read_bytes() != candidate_pac:
        raise ValueError("Local source assets changed during material preparation")
    publish(output, files, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-root", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "build" / "steve-material")
    parser.add_argument("--cdmw-source", type=Path, default=ROOT / "build" / "cdmw-fixed-source")
    parser.add_argument("--deps", type=Path, default=ROOT / "build" / "cdmw-deps")
    parser.add_argument("--steve-asset", type=Path, default=ROOT / "build" / "steve-1.21.1")
    parser.add_argument("--native-assets", type=Path, default=ROOT / "build" / "native-steve")
    parser.add_argument("--decoder-python", type=Path, default=Path(shutil.which("python") or "python"))
    args = parser.parse_args()
    try:
        game = args.game_root or Path(json.loads((ROOT / "runtime" / "installation.json").read_text(encoding="utf-8-sig"))["gameRoot"])
        report = prepare(game, args.output, args.cdmw_source, args.deps, args.steve_asset,
                         args.native_assets, args.decoder_python)
    except (OSError, ValueError, ImportError, KeyError, subprocess.SubprocessError) as error:
        raise SystemExit(f"Steve material preparation stopped: {error}") from error
    print(json.dumps({"output": str(native.output_directory(args.output)),
                      "material": report["material"], "resources": len(report["candidateResources"]),
                      "integration": report["integration"]}, indent=2))


if __name__ == "__main__":
    main()
