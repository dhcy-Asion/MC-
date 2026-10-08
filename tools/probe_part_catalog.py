"""Read four fixed PAPPT basename memberships for the controlled client, read-only.

No native function, HTTP endpoint, heap scan or memory write. Catalog membership
and folder declarations do not establish prefab loading, rendering or Steve.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import time

import probe_appearance_controller as appearance
import probe_health as health

core, roster, ROOT = appearance.core, appearance.roster, appearance.ROOT
ProbeError = appearance.ProbeError
WORLD_GLOBAL, CATALOG_GLOBAL = 0x6D69190, 0x6C8CF10
SOURCE = {"virtualPath": "character/bin__/partprefabtable.pappt",
          "sha256": "d6947dcb57d32e0503704da28edf4645baaa8faad8fbd47d09a8a8832686abed",
          "partCount": 15566, "descriptorCount": 2630,
          "provenance": "Fixed original PAPPT: both donor rows uniquely present in both sections; private rows absent."}
FOLDERS = ("1_pc/01_phm/nude", "1_pc/01_phm/head/head")
NAMES = ("cd_phm_00_nude_01_0002_macduff", "cd_phm_00_head_00_0001_macduff",
         "crimsonmc_steve_body_1_21_1", "crimsonmc_steve_head_1_21_1")
HASHES = (0x3B824C1E, 0x48A21D57, 0xB6A8E91D, 0xA675D277)
MAPS = {"partFolderMap": 0x70, "descriptorFolderMap": 0x90}
FLAGS = ("catalogMembershipObserved", "controlledActorRoundTripObserved", "stableTwoSamples")
LIMIT, READ_BUDGET = 65536, 262144


class NotReady(ProbeError):
    pass


# Fixed supported EXE constructors, loader/lookup/hash/path consumers. Digests
# are embedded here; no ignored research files or external decoder are loaded.
WINDOWS = (
    (0x391680, 43, "cdaf2912df1bc7255f72e63691fb30b48527cbd55b910ea949dfe4dc87237237"),
    (0x3916c3, 89, "572bcbdb421843f979c63ce4b368dbbf65830c3d7e9ca26cc2dc7bd1aa90d0e8"),
    (0x39176f, 138, "a0861683f41024c717792b685fee401b30bc3edf98f58bd5fa520c7b2787e994"),
    (0x391825, 23, "865ff62dc29325e48b9ba3be181f6efd22c143887bf3a20f6717bf6cd75696a2"),
    (0x391ac5, 99, "16afa68838db70fd54f9aac15fbfae2e63cab9c06823ad3fd0aad9df20263148"),
    (0x391b28, 83, "39b1e679fef708ba5a3927ce29c680352757481939402fa7b7ccae8aa0def1d0"),
    (0x391b7b, 106, "aae04a363f2ad4f906f765ce27e06839af549ce6a1eee9918404c2d063b22085"),
    (0x3a41c0, 27, "12410d1899f44682f1dfc688e66dc473fd1ee2dbf5d726df3206769a21bd0b2d"),
    (0x3a41db, 195, "e484047599b174d1f727118d574ab93dbade6ff78b152bffc44f51cb92bbbd7b"),
    (0x3d0c50, 37, "632fb5b5fcfe53f1dfd665353dec9311371fcb80735639d0886731d47db9c655"),
    (0x3d0c75, 59, "2d614dfa3ab1f27fc4ccda42c8bf0ccdec6770e6c09456fb69640e6b3e66a2c8"),
    (0x3d0c75, 137, "4a8e577f2bb1ef19472cc83e6aa6995d6652dcc35b27b72e07dbd726af529c9b"),
    (0x3d0cb0, 41, "36d8302eb08b3d8f774cd09a8fff6d77532f8a8dd94e8a0766d72b75095bf4aa"),
    (0x3d0cd9, 37, "42cf48bc6f1520f9ddf78ec222886834c1c7bcde17f64185973145b88ce82808"),
    (0x3d0cfe, 6, "610db06dabf97317e594448d58adc71479444c77e453244e572ce71b335bff2f"),
    (0x3d5ea0, 5, "f6a5378cef76c9c672f9fea81fc831e1ceac2227641535f78369e46d328471f0"),
    (0x3d5f10, 94, "93733a98e10b6f7fe09fba0a53872432fd15030ce8fad3887336f949b883bf25"),
    (0x46c9ee, 101, "b6c2b254b60ae99f9994c163d50d6d855d23dc0de3919472b995e06fb69a7eac"),
    (0x46cacc, 52, "baa7bb4cc99b367766a24319d20aa9989c529fa3924bb78045104e88daf8b79d"),
    (0x46cc3c, 50, "c43be538b88e46607720065a88a282205ea674e9ad59a5e496dd3380ecd8fbfe"),
    (0x723b90, 8, "ce7afdbf28a350cac960ecd098c4820e3ec1be57d9b487a5cfd6b79838cb2479"),
    (0xa4aacc, 42, "7636dab8a32d00f0566494371dc3bd1a66637c172aa9d4f55ae99c08a42061ba"),
    (0xacf7e8, 29, "a287f6085c18387e5dd3fbcdb2ca4e02347af3114d8bba51bf7ab0b8ca71dca7"),
    (0xacf86c, 35, "a1df075e10646623b763ef30c7f3600496cdd7c8616510f915ab40546665a103"),
    (0xacfa96, 15, "77a20d88cdc57eb47f80904a89b0cd9fbc27309573e174296e8e23262adaa896"),
    (0xacfaff, 37, "52f3a50f03ade59b6e119730bc1c0c7ed14837562e7a45b93456514a25d59ea0"),
    (0xacfbba, 19, "7a5fff4f7cd48c1eb6396f17dbbf8256aa3a77dfbfb9d6533fa7a51d49131d09"),
    (0x12c44a8, 43, "ef42c9fb1f1d4d65a35da1ce5d7e36807342ff4fff25583968411ad2c35990b5"),
    (0x1364780, 49, "24d5b37c381c99737c13ee110d3d8dabc46d48d319902be7c638121305c29c83"),
    (0x1364780, 239, "33b7d100710ba10374d2b4cf16f46b0a11da9e166895efe9debf6002b1d8ed8f"),
    (0x1364780, 1412, "16b5083cb5168e9502b18f084c8cd8f51e0499a50ad6ed720e9dd4e619bbefc2"),
    (0x13647e0, 126, "6694597a554d44f85117787a1dc6bbc7340bf638ca748d26cdb6ae09e13b9043"),
    (0x136485e, 19, "370c527a94ab9dd2599f8c05267df559f5454f6b9aea669dd62033ebbb3377e2"),
    (0x1364940, 163, "9b61aff19bd389bcf36c31c9bdc147d489d36d67f97aab0cc01aafce45aa0693"),
    (0x13649e3, 19, "6fceb11c44757cdac448eb39431fc31f3c8dcd7ae1e25991b3677e86cd33e269"),
    (0x1364aa0, 228, "a99164a4faf58a20f146a92503f6dfcfb5c1b4a32025ec38a531f0092e4aa695"),
    (0x1364b84, 19, "4a00b1d7e2ed4825a2b555be24ca096341adeaec6db6cfb2f7585efff72756af"),
    (0x1364c01, 103, "55f23e2f86aac6e5351102c499c10525c67a1cd013cd4c8ff1464708edc7c064"),
    (0x2c988e2, 23, "d1d885de62a71663fd0bc0ce4aa15df305df47ac336ddf0b3b71dac9a4ed74fa"),
    (0x2c98939, 135, "0ec9ca595c134a7bd416caf21c8fd0bb3ff4caf95b50a22faae2ec336d6b9c5a"),
    (0x2c98a75, 155, "cf0b013a57d97c963c1f03127097425ab6ca5048cdb01455d717b7c45de810fa"),
    (0x2c98b10, 392, "a0ae542125d4a137a2f2c9d7d3d3c43d3039ce4e19a5a6ee0a87d2c3b1317ef5"),
    (0x2c98d98, 30, "277c94dc43c3096a2d569e2b83c65673dafcdc377875e6dbde518aa9f11a7c35"),
    (0x2c98ea0, 97, "0d647af8531bb418f42470ebbc2c45ee9a317b19259ddfb3188364cad1b75ff3"),
    (0x2c990ed, 76, "8815ac5e824d0b057757e980a1482e9667178774744526f2c875754ac6bb42e4"),
    (0x2c99185, 81, "f89f59294e5ed38dc6f0f08a560e6014c591e025f941b344fa840f88e04fdf21"),
    (0x2c99264, 213, "507a52e61e7e2b831a4d8c845d2b68a607fef6b47a17e6a07b5158557e320355"),
    (0x2c99670, 5, "9b710b188f94d0f7e55c30f58cab181e1ac3a66b259dcc63c9fddd50e2ffb072"),
    (0x2c9ede0, 5, "aaa5200490460a266aa3e849f283273e748dc1c03f3ae17f1f72b3bea0541f08"),
    (0x2c9efb0, 5, "f2e1ab1e0b9c217ba9f6981433c96957a12f438960ac5fd8a7be58338d605482"),
    (0x2ca0830, 116, "0cb8002270b4338fe7da4ac17d3e6ff60c693d022f4b88d729e843d55e810439"),
    (0x2ca08a4, 92, "62625988b51a102e24254ef2cffb1131af6e8ec09ed2ef18063e4c9299049424"),
    (0x2ca08dc, 102, "bb45058133d4af6764e3c19ab0a8abf3ef27fbe8cc1b68c8000a18e57420fc96"),
    (0x2ca0900, 12, "d5d3e0ecfd5bf463019836bfdfa6e33f1ad9c5947d1446c5ef4f573493f59f6d"),
    (0x2ca091d, 37, "33a6c4f5f63f287d1298639f7b2612a60e8cfa85bae4363b17a8e357c6ecf2ef"),
    (0x2ca0992, 52, "3c7d35c198c4126f5dcabdcd64269fc0da9639ad4cfd28599ccc85fb4a9b5782"),
    (0x2ca09c6, 35, "57ad2d902c0070b8e50027686e18a98f61b5fbb12219f4df5e0ba97474a13d97"),
    (0x2ca0a3f, 11, "7072e5cfd54bda3b3a9cb5da24f9a6b8221aafd35a8ea3c1ab2cfb7607ec5653"),
    (0x2d14a68, 23, "b602c771addff03e4c3961e169246792799cacd73baa790b80a80b07433b150e"),
    (0x2d14aa2, 28, "52978fadab34f2a03ac63e119695ddf2c0ecd6068d1803ec325691e8f68951d2"),
    (0x2d16188, 42, "cca6440783cdfeb821860ef1cb88f401161d9a248b3f6a6a3cddc52ffbd5bc48"),
    (0x2d161da, 229, "df73e0dc7d597b64f9d43962d2b94149eaf6027f213d8d6df8833a7aa1b9733f"),
    (0x2d162bf, 7, "fc79aaaa8331806481de8825004e29a71d3e3926177af3640acb4694e73a0b0a"),
    (0x2d162cb, 28, "d154ebb794e1d7252d04612035bbd220e7bcd77da6eb4e0cd80e12f677b031fe"),
    (0x2d23055, 28, "5bd00b07b96587f3006fc38027a6a54f427b3ecb0eeaeb51144fdc722e3953be"),
    (0x2d23093, 54, "c14bb43548141167dfa41bfdff3aec648a7b316e72d4621756114b06d35ca0f8"),
    (0x3b3e20a, 10, "334510a1410af0b17ba7168b17f7935b3d4980335ccd6e1f47580df75e666058"),
    (0x3b3e231, 29, "29d5343f3690cc1df0324328cab1b927b85d1327ced5d7b021a92d7ffcbc1f5f"),
    (0x3b3e27d, 71, "470cc53bc9e008bf0a4e6a452257fcfa3a835ca779803fe73c6785e714237524"),
    (0x3dc6f73, 10, "a4e6641f185bdc378ba3b9952d024713f7d41796426ddb59e8abf0fed5ab1dde"),
    (0x3dc80c0, 12, "81be00fe14fbe849387194559d57c823e948c769337f2e3691e56d3a95a5645d"),
    (0x3dc90ac, 58, "11d11b4c7e0eb8a8733b1844ede18973ea92192272519f84c48cef0f16768f1d"),
    (0x8859bb0, 99, "caf007ccc1381271b7cef9280620b28850affb5b69bfe2feae15ed4123907402"),
    (0x1099bf8b, 63, "b58cb15f82b5a7f15be7eeafe45d4ef73caf9b3598c2ec51e5001ebe6474d78c"),
    (0x1099bfc2, 8, "a4f2567ec9e3471d82ebd5cabbeb9bdec3894fc07e9698f3e4c3bd363c43632e"),
    (0x109a8bb3, 26, "25c05f13d47d40498b44f5eafd8b65574f7c12d2a1f43b861b7d475ba5e91ee8"),
    (0x109a8bed, 69, "9659a7ceb176c7c8a6bb1845e29361b2d0deb7d9b113df255d9494dec5a8ad9b"),
    (0x109a8c32, 26, "8769b8b5e6f7711e660c07d4f31dd6658a463121eb7fdd16fd63fe43d834f58d"),
    (0x109a8cc5, 85, "06f638b6a3792e3fbc979331011d8a791313cc8f2102b8e41edee4a2d57306bf"),
    (0x109a8e36, 29, "0cd6be88571d7ee65621b23875eddaa5d782cb75a1e02da9eb4c69a4b9ee9525"),
    (0x109a8e6a, 69, "3ec9bde5b64f553b137bd8ea40d0857520b7bdc4e4c2a4a33f82879595bbdffb"),
    (0x109a8eaf, 6, "89e7500afbe1daa844eaa7554e7e780c721ff3444d75de6e039006ab1bb65df8"),
    (0x109a8f1a, 14, "52842d6f6dfb2c0f19635d591b4b8d8e3ef4cd282136fdd5d446d29ac386cf92"),
    (0x109a8f4b, 48, "bd82b46e31486f1db378086d9bb60b166652129ea16a232a00bef05a21480c8c"),
)
PARENT_VTABLE = (0x5d20718, (62125552, 59699392, 62176176, 62176160, 59693088, 59693120, 62131120, 62131184, 6780848, 8084624, 59693616, 62187840, 4893488, 62114384, 54024608, 62114368))
SERVICE_VTABLE = (0x5b41078, (47273472, 47275904, 47282224, 47282816, 47282192, 47295936, 47296224, 47296416, 7486368, 7486352, 47263232, 47320992, 47321168, 47321008, 47263200, 47263216))


def name_hash(data):
    """Exact byte-sensitive lookup3, seed C5EDE; no path/case normalization."""
    mask = 0xffffffff
    def rot(x, n):
        return ((x << n) | (x >> (32-n))) & mask
    a = b = c = (len(data)+0xDEBA1DCD) & mask
    offset, remaining = 0, len(data)
    while remaining > 12:
        x, y, z = struct.unpack_from("<3I", data, offset)
        a, b, c = (a+x)&mask, (b+y)&mask, (c+z)&mask
        a = ((a-c)&mask)^rot(c, 4); c = (c+b)&mask
        b = ((b-a)&mask)^rot(a, 6); a = (a+c)&mask
        c = ((c-b)&mask)^rot(b, 8); b = (b+a)&mask
        a = ((a-c)&mask)^rot(c, 16); c = (c+b)&mask
        b = ((b-a)&mask)^rot(a, 19); a = (a+c)&mask
        c = ((c-b)&mask)^rot(b, 4); b = (b+a)&mask
        offset += 12; remaining -= 12
    if remaining:
        x, y, z = struct.unpack("<3I", data[offset:]+bytes(12-remaining))
        a, b, c = (a+x)&mask, (b+y)&mask, (c+z)&mask
        c = ((c^b)-rot(b, 14))&mask; a = ((a^c)-rot(c, 11))&mask
        b = ((b^a)-rot(a, 25))&mask; c = ((c^b)-rot(b, 16))&mask
        a = ((a^c)-rot(c, 4))&mask; b = ((b^a)-rot(a, 14))&mask
        c = ((c^b)-rot(b, 24))&mask
    return c


def image_address(base, length, rva, size):
    if not 0 <= rva <= length-size:
        raise ProbeError("Catalog fixed contract escaped main image")
    return base+rva


def validate_code(reader, base, length):
    appearance.pointer(base, "module base")
    if type(length) is not int or not 0 < length <= core.MAX_IMAGE_SIZE or base+length >= 2**47:
        raise ProbeError("Catalog image extent exceeds bounds")
    for rva in (WORLD_GLOBAL, CATALOG_GLOBAL, PARENT_VTABLE[0], SERVICE_VTABLE[0]):
        image_address(base, length, rva, 128 if rva in (PARENT_VTABLE[0], SERVICE_VTABLE[0]) else 8)
    for rva, size, digest in WINDOWS:
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "catalog code window")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ProbeError("Catalog code differs from the fixed EXE")
    for rva in appearance.WORLD_ANCHORS:
        size = len(appearance.WORLD_PATTERN.split())
        raw = appearance.read(reader, image_address(base, length, rva, size), size, "world anchor")
        if (core.pattern(appearance.WORLD_PATTERN).fullmatch(raw) is None or
                rva+7+struct.unpack_from("<i", raw, 3)[0] != WORLD_GLOBAL):
            raise ProbeError("Controlled world anchors differ")
    if tuple(name_hash(name.encode("ascii")) for name in NAMES) != HASHES:
        raise ProbeError("Catalog hash implementation differs from fixed vectors")


class Watch(health.Watch):
    def __init__(self, reader, base, length):
        super().__init__(reader, base, length)
        self.bytes_read = 0

    def get(self, address, size, label):
        if (address, size) not in self.rows:
            self.bytes_read += size
        if self.bytes_read > READ_BUDGET:
            raise ProbeError("Catalog diagnostic read budget exceeded")
        return super().get(address, size, label)

    def ready_link(self, address, label):
        value = self.value(address, label)
        if value == 0:
            raise NotReady(label+" is not available")
        return appearance.pointer(value, label)

    def constructed(self, address, expected, label):
        if self.value(address, label+" vtable") != self.base+expected[0]:
            raise ProbeError(label+" exact constructed vtable differs")
        size = len(expected[1])*8
        raw = self.get(image_address(self.base, self.length, expected[0], size), size, label+" vtable slots")
        if raw != struct.pack(f"<{len(expected[1])}Q", *(self.base+rva for rva in expected[1])):
            raise ProbeError(label+" fixed vtable slots differ")

    def held_string(self, holder, maximum, label):
        appearance.pointer(holder, label+" holder")
        raw = self.get(holder, 16, label+" holder fields")
        chars, length, cached = struct.unpack("<QII", raw)
        if not 0x10000 <= chars < 2**47-maximum-1:
            raise ProbeError(label+" byte address is null or exceeds bounds")
        if length != 0xffffffff and length > maximum:
            raise ProbeError(label+" declared length exceeds bound")
        if length == 0xffffffff:
            value = bytearray()
            for index in range(maximum+1):
                byte = appearance.read(self.reader, chars+index, 1, label+" bounded byte")
                value.extend(byte)
                if byte == b"\0":
                    break
            else:
                raise ProbeError(label+" has no bounded NUL terminator")
            expected = bytes(value)
            value = self.get(chars, len(expected), label+" NUL-inclusive bytes")
            if value != expected:
                raise ProbeError(label+" changed while resolving bounded length")
        else:
            value = self.get(chars, length+1, label+" NUL-inclusive bytes")
        if value[-1:] != b"\0" or b"\0" in value[:-1]:
            raise ProbeError(label+" length/NUL contract differs")
        value = value[:-1]
        if cached != 0xffffffff and cached != name_hash(value):
            raise ProbeError(label+" cached hash differs from exact bytes")
        return value


def query(watch, address, map_name):
    header = watch.get(address, 32, map_name+" header")
    buckets, count, capacity, epoch, data, entries = struct.unpack("<4I2Q", header)
    if not 0 <= count <= capacity <= LIMIT or not 0 <= buckets <= LIMIT:
        raise ProbeError(map_name+" count/capacity exceeds bounds")
    if count and not buckets:
        raise ProbeError(map_name+" nonempty map has no buckets")
    if count:
        appearance.pointer(data, map_name+" buckets")
        appearance.pointer(entries, map_name+" entry pointers")
    result = {"bucketCount": buckets, "entryCount": count, "capacity": capacity,
              "clearEpoch": epoch, "clearEpochIsCompleteMutationCounter": False, "queries": {}}
    for name, hash_ in zip(NAMES, HASHES):
        matches = []
        row = {"membership": "absent", "hash32": f"{hash_:08x}", "folder": None,
               "folderMatchesDonor": False, "verifiedAtTopLevel": False}
        result["queries"][name] = row
        if count:
            bucket = hash_ % buckets
            raw = watch.get(data+bucket*0x100, 0x100, map_name+" bucket "+str(bucket))
            used = struct.unpack_from("<I", raw)[0]
            if used > 31:
                raise ProbeError(map_name+" bucket exceeds 31 items")
            pairs = [struct.unpack_from("<II", raw, 8+slot*8) for slot in range(used)]
            if len({index for _, index in pairs}) != used or any(index >= count for _, index in pairs):
                raise ProbeError(map_name+" bucket index is invalid or duplicated")
            for slot, (stored_hash, index) in enumerate(pairs):
                if stored_hash != hash_:
                    continue
                node = watch.link(entries+index*8, map_name+" selected node pointer")
                node_raw = watch.get(node, 24, map_name+" selected node")
                position, key, folder = struct.unpack_from("<I4xQQ", node_raw)
                if position != bucket*31+slot:
                    raise ProbeError(map_name+" selected node position backlink differs")
                actual = watch.held_string(key, 128, map_name+" selected key")
                if name_hash(actual) != stored_hash:
                    raise ProbeError(map_name+" selected key differs from bucket hash")
                if actual != name.encode("ascii"):
                    continue  # Genuine equal-hash strings remain distinct names.
                text = watch.held_string(folder, 384, map_name+" matched folder")
                if (not text or any(not 32 <= byte < 127 for byte in text) or b"\\" in text or
                        any(part in (b"", b".", b"..") for part in text.split(b"/"))):
                    raise ProbeError(map_name+" matched folder is not a bounded relative declaration")
                matches.append((text.decode("ascii"), index, slot))
        if len(matches) > 1:
            raise ProbeError(map_name+" exact name occurs more than once")
        if matches:
            folder, index, slot = matches[0]
            row.update(membership="present", folder=folder, index=index, bucketSlot=slot,
                       folderMatchesDonor=folder == FOLDERS[NAMES.index(name)%2])
    return result


def sample(reader, base, length, observed):
    watch = Watch(reader, base, length)
    world = watch.ready_link(base+WORLD_GLOBAL, "world")
    manager = watch.typed(watch.ready_link(world+0x30, "client manager"), "manager")
    user = watch.typed(watch.ready_link(manager+0x58, "client user"), "user")
    actor = watch.typed(watch.ready_link(manager+0x50, "controlled child"), "actor")
    if (watch.value(user+0xD0, "user first child") != actor or
            watch.value(user+0xD8, "user second child") != actor or
            watch.value(actor+0xA0, "actor user backlink") != user):
        raise ProbeError("Controlled manager/user/unique-child round trip differs")
    observed["controlledActor"] = {"world": hex(world), "manager": hex(manager), "user": hex(user), "actor": hex(actor)}
    parent = watch.ready_link(world+0xE0, "catalog parent manager")
    service = watch.ready_link(world+0xF0, "catalog service")
    catalog = watch.ready_link(world+0xA8, "world catalog")
    watch.constructed(parent, PARENT_VTABLE, "parent manager")
    watch.constructed(service, SERVICE_VTABLE, "anonymous service")
    if (watch.value(parent+0x2B8, "parent service backlink") != service or
            watch.value(service+0x40068, "service catalog backlink") != catalog or
            watch.value(base+CATALOG_GLOBAL, "catalog global") != catalog):
        raise ProbeError("World/constructed-owner/catalog-global round trip differs")
    interface = watch.ready_link(service+0x40018, "file interface")
    if watch.value(catalog, "catalog first file interface") != interface:
        raise ProbeError("Catalog file interface does not match constructor input")
    observed["catalog"] = {"pointer": hex(catalog), "parent": hex(parent), "service": hex(service),
                           "fileInterface": hex(interface), "catalogRttiInterpreted": False}
    observed["maps"] = {}
    for name, offset in MAPS.items():
        observed["maps"][name] = query(watch, catalog+offset, name)
    observed["dependencies"] = watch.finish()
    observed["donorBaselineValid"] = all(observed["maps"][m]["queries"][n]["membership"] == "present" and
        observed["maps"][m]["queries"][n]["folderMatchesDonor"] for m in MAPS for n in NAMES[:2])
    observed["stableDuringSample"] = True


def reject(report, reason, state="rejected"):
    report.update(state=state, reason=str(reason)[:2000], **{flag: False for flag in FLAGS})
    for sample_ in report.get("samples", []):
        for map_ in sample_.get("maps", {}).values():
            for row in map_.get("queries", {}).values():
                row["verifiedAtTopLevel"] = False
    return report


def collect(reader, base, length, *, identity=None, pause=time.sleep):
    identity = identity or (lambda: health.process_identity(reader))
    report = {"schemaVersion": 1, "mode": "four-fixed-part-catalog-read-only", "state": "rejected", "samples": [],
              **{flag: False for flag in FLAGS}, "sourceBaseline": SOURCE,
              "snapshotAtomic": False, "nativeFunctionsInvoked": False, "gameMemoryWritten": False,
              "heapScanned": False, "prefabLoadedVerified": False, "renderedDescriptorVerified": False,
              "steveModelLoaded": False, "appearanceApplicationVerified": False,
              "limitations": ["Stable membership/folder declarations do not establish loaded or rendered assets.",
                  "External double reads are not an atomic game-thread snapshot or a lifetime guarantee.",
                  "Private absences remain provisional unless both donor baselines and every dependency pass."]}
    try:
        before = identity()
        if (type(before.get("pid")) is not int or before["pid"] <= 0 or
                not str(before.get("creationTime100ns", "")).isdigit() or int(before["creationTime100ns"]) <= 0 or
                (before.get("moduleBase"), before.get("moduleSize")) != (base, length)):
            raise ProbeError("Reader process/module identity differs")
        report["process"] = before
        validate_code(reader, base, length)
        for index in range(2):
            observed = {"stableDuringSample": False}
            report["samples"].append(observed)
            sample(reader, base, length, observed)
            if index == 0:
                pause(0.05)
        validate_code(reader, base, length)
        if identity() != before or report["samples"][0] != report["samples"][1]:
            raise ProbeError("Process identity or complete catalog dependencies changed")
        if not all(row["donorBaselineValid"] for row in report["samples"]):
            raise NotReady("Original donor names/folders are not correct in both catalog maps")
        report.update(state="observed", **{flag: True for flag in FLAGS})
        for row in report["samples"]:
            for map_ in row["maps"].values():
                for query_ in map_["queries"].values():
                    query_["verifiedAtTopLevel"] = True
    except (ProbeError, RuntimeError, OSError, ValueError, struct.error) as error:
        state = "notReady" if isinstance(error, NotReady) else "unstable" if any(
            row.get("stableDuringSample") for row in report["samples"]) else "rejected"
        reject(report, error, state)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--output", type=Path, default=ROOT/"runtime/part-catalog.json")
    args = parser.parse_args()
    output = appearance.output_path(args.output)
    pid = args.pid
    if pid is None:
        text = subprocess.check_output(["tasklist", "/FI", "IMAGENAME eq CrimsonDesert.exe", "/FO", "CSV"], text=True, encoding="utf-8", errors="replace")
        pids = re.findall(r'"CrimsonDesert\.exe","(\d+)"', text, re.I)
        if len(pids) != 1:
            raise ProbeError("Require exactly one game process or explicit --pid")
        pid = int(pids[0])
    if pid <= 0:
        raise ProbeError("Invalid PID")
    profile, _ = core.load_profile()
    reader = core.Reader(pid)
    try:
        base, length, path = reader.module()
        version = subprocess.check_output(["powershell", "-NoProfile", "-Command", "(Get-Item -LiteralPath '"+str(path).replace("'", "''")+"').VersionInfo.FileVersion"], text=True).strip()
        digest = appearance.file_digest(path)
        roster.validate_layout_build(profile, version, digest)
        report = collect(reader, base, length)
        try:
            if (report.get("process", {}).get("pid") != pid or health.process_identity(reader) != report.get("process") or
                    reader.module() != (base, length, path) or appearance.file_digest(path) != digest):
                reject(report, "Final same-handle process/module/EXE identity changed", "unstable")
        except (ProbeError, RuntimeError, OSError, ValueError) as error:
            reject(report, error, "unstable")
        report.update(timeUtc=dt.datetime.now(dt.timezone.utc).isoformat(), gameVersion=version,
                      supportedExeSha256=digest, contract={"codeWindowCount": len(WINDOWS), "fixedNames": NAMES,
                      "hashSeed": "0xC5EDE", "mapOffsets": MAPS, "catalogClassNameKnown": False})
        appearance.write_report(output, report)
        print(json.dumps({"output": str(output), **{key: report.get(key) for key in ("state", "reason", *FLAGS, "steveModelLoaded")}}, indent=2))
        return 0 if report["state"] == "observed" else 1
    finally:
        reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
