"""Isolated fixed-catalog byte/fault checks; fixed EXE is read only from disk."""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

import probe_part_catalog as probe
from check_character_roster import FakeReader
from check_health_probe import DiskImage, install_type

BASE = 0x140000000
A = {name: 0x20000+i*0x80000 for i, name in enumerate(
    ("world", "manager", "user", "actor", "parent", "service", "catalog", "interface"))}
COLLISION = ("crimsonmc_catalog_collision_84985", "crimsonmc_catalog_collision_114283")
HASH_GOLDEN = ((0,0xdeba1dcd),(1,0x19cf2d6f),(2,0x9dd71533),(3,0xe3c8c2c0),
    (4,0x9993f5e9),(7,0x2bfba2a7),(8,0x910ada15),(11,0xde96103b),(12,0x56c102e9),
    (13,0x34b5a548),(16,0xcd95b701),(24,0x8ffacf34),(25,0x74c7f120),
    (32,0x898570b9),(64,0x44bafab6),(128,0x935db592))


def identity(disk, **changes):
    return {"pid": 43210, "creationTime100ns": "1234567890123456", "moduleBase": BASE,
            "moduleSize": disk.length, "imagePath": str(disk.path), **changes}


def held(reader, address, payload, unknown=False, cached=True):
    chars = address+0x103  # Byte strings have no QWORD alignment requirement.
    reader.segments[address] = bytearray(struct.pack("<QII", chars,
        0xffffffff if unknown else len(payload), probe.name_hash(payload) if cached else 0xffffffff))
    reader.segments[chars] = bytearray(payload+b"\0")
    return address, chars


def build_map(reader, number, records):
    address = A["catalog"]+tuple(probe.MAPS.values())[number]
    buckets, data, entries, nodes = 7, 0x1000000+number*0x100000, 0x1020000+number*0x100000, []
    reader.segments[address] = bytearray(struct.pack("<4I2Q", buckets, len(records), len(records)+1, 9, data, entries))
    reader.block(data, buckets*0x100)
    reader.block(entries, max(8,len(records)*8))
    for index, (name, folder) in enumerate(records):
        hash_ = probe.name_hash(name.encode())
        bucket = hash_%buckets
        count = reader.value(data+bucket*0x100, "<I")
        reader.put(data+bucket*0x100, count+1, "<I")
        reader.put(data+bucket*0x100+8+count*8, hash_, "<I")
        reader.put(data+bucket*0x100+12+count*8, index, "<I")
        node = data+0x40000+index*0x1000
        key, chars = held(reader, node+0x100, name.encode())
        folder_holder, folder_chars = held(reader, node+0x500, folder.encode())
        reader.segments[node] = bytearray(struct.pack("<I4xQQ", bucket*31+count,key,folder_holder))
        reader.put(entries+index*8,node)
        nodes.append({"node":node,"key":key,"chars":chars,"folderHolder":folder_holder,
                      "folderChars":folder_chars,"bucket":data+bucket*0x100,"slot":count})
    return {"address":address,"data":data,"entries":entries,"nodes":nodes}


def fixture(disk, private=False, records=None):
    reader = FakeReader()
    for address in A.values():
        reader.block(address, 0x500)
    # Overlapping pins use identical original bytes, with widest spans first.
    for rva, size, _ in sorted(probe.WINDOWS, key=lambda row: -row[1]):
        reader.segments.setdefault(BASE+rva, bytearray(disk.read(rva,size)))
    for rva in probe.appearance.WORLD_ANCHORS:
        reader.segments[BASE+rva] = bytearray(disk.read(rva,len(probe.appearance.WORLD_PATTERN.split())))
    for index, kind in enumerate(("manager","user","actor")):
        install_type(reader,A[kind],kind,index=index)
    for key, target in ((BASE+probe.WORLD_GLOBAL,"world"),(A["world"]+0x30,"manager"),
        (A["manager"]+0x58,"user"),(A["manager"]+0x50,"actor"),(A["user"]+0xd0,"actor"),
        (A["user"]+0xd8,"actor"),(A["actor"]+0xa0,"user"),(A["world"]+0xe0,"parent"),
        (A["world"]+0xf0,"service"),(A["world"]+0xa8,"catalog"),(A["parent"]+0x2b8,"service"),
        (A["service"]+0x40068,"catalog"),(BASE+probe.CATALOG_GLOBAL,"catalog"),
        (A["service"]+0x40018,"interface"),(A["catalog"],"interface")):
        reader.put(key,A[target])
    for name, (vt,slots) in (("parent",probe.PARENT_VTABLE),("service",probe.SERVICE_VTABLE)):
        reader.put(A[name],BASE+vt)
        reader.segments[BASE+vt] = bytearray(struct.pack(f"<{len(slots)}Q",*(BASE+rva for rva in slots)))
    if records is None:
        records = list(zip(probe.NAMES[:2],probe.FOLDERS))
        if private:
            records += list(zip(probe.NAMES[2:],probe.FOLDERS))
    del reader.segments[A["catalog"]]
    reader.put(A["catalog"],A["interface"])
    reader.maps = [build_map(reader,i,records) for i in range(2)]
    reader.handle, reader.close = 12345, mock.Mock()
    reader.module = mock.Mock(return_value=(BASE,disk.length,disk.path))
    reader.reads.clear()
    return reader


class CatalogChecks(unittest.TestCase):
    exe = None

    @classmethod
    def setUpClass(cls):
        cls.disk = DiskImage(cls.exe)

    def collect(self, reader, pause=lambda _:None, identities=None):
        callback = mock.Mock(side_effect=identities) if identities is not None else lambda:identity(self.disk)
        return probe.collect(reader,BASE,self.disk.length,identity=callback,pause=pause)

    def unavailable(self,report):
        self.assertNotEqual(report["state"],"observed",report.get("reason"))
        for flag in (*probe.FLAGS,"prefabLoadedVerified","renderedDescriptorVerified","steveModelLoaded",
                     "appearanceApplicationVerified","snapshotAtomic","gameMemoryWritten","nativeFunctionsInvoked","heapScanned"):
            self.assertIs(report[flag],False,flag)
        for sample in report["samples"]:
            for map_ in sample.get("maps",{}).values():
                self.assertFalse(any(row["verifiedAtTopLevel"] for row in map_["queries"].values()))

    def test_01_exact_disk_windows_owner_vtables_and_world_anchors(self):
        self.assertEqual(len(probe.WINDOWS),84)
        for rva,size,digest in probe.WINDOWS:
            self.assertEqual(hashlib.sha256(self.disk.read(rva,size)).hexdigest(),digest,hex(rva))
        for vt,slots in (probe.PARENT_VTABLE,probe.SERVICE_VTABLE):
            self.assertEqual(self.disk.read(vt,len(slots)*8),struct.pack(f"<{len(slots)}Q",*(BASE+rva for rva in slots)))
        probe.validate_code(fixture(self.disk),BASE,self.disk.length)

    def test_02_fixed_hash_vectors_tail_edges_case_bytes_and_real_collision(self):
        self.assertEqual(tuple(probe.name_hash(name.encode()) for name in probe.NAMES),probe.HASHES)
        # Golden results came from a bounded Python interpreter of the pinned
        # 1364780 x86 bytes; no native function was executed.
        for length,hash_ in HASH_GOLDEN:
            payload = bytes((i*37+11)%256 for i in range(length))
            self.assertEqual(probe.name_hash(payload),hash_)
        self.assertEqual([probe.name_hash(name.encode()) for name in COLLISION],[0x9e18c1bc]*2)
        self.assertNotEqual(probe.name_hash(probe.NAMES[0].upper().encode()),probe.HASHES[0])
        self.assertNotEqual(probe.name_hash(b"a\0"),probe.name_hash(b"a"))

    def test_03_donors_validate_private_absence_in_both_maps(self):
        reader = fixture(self.disk)
        report = self.collect(reader)
        self.assertEqual(report["state"],"observed",report.get("reason"))
        self.assertTrue(all(report[flag] for flag in probe.FLAGS))
        self.assertEqual(report["samples"][0],report["samples"][1])
        for sample in report["samples"]:
            self.assertTrue(sample["donorBaselineValid"])
            for map_ in sample["maps"].values():
                self.assertFalse(map_["clearEpochIsCompleteMutationCounter"])
                for name in probe.NAMES[2:]:
                    self.assertEqual(map_["queries"][name]["membership"],"absent")
                    self.assertTrue(map_["queries"][name]["verifiedAtTopLevel"])
        self.assertFalse(report["steveModelLoaded"])
        self.assertTrue(all(1<=size<=4096 for _,size in reader.reads))
        buckets = {(int(row["address"],16),row["size"]) for row in report["samples"][0]["dependencies"] if " bucket " in row["field"]}
        self.assertLessEqual(len(buckets),8)

    def test_04_registered_private_names_are_present_not_rendered(self):
        report = self.collect(fixture(self.disk,private=True))
        self.assertEqual(report["state"],"observed",report.get("reason"))
        for sample in report["samples"]:
            for map_ in sample["maps"].values():
                self.assertTrue(all(row["membership"]=="present" for row in map_["queries"].values()))
        self.assertFalse(report["prefabLoadedVerified"])

    def test_05_wrong_donor_folder_or_missing_donor_prevents_absence_promotion(self):
        for records in ([(probe.NAMES[0],"1_pc/wrong"),(probe.NAMES[1],probe.FOLDERS[1])],
                        [(probe.NAMES[1],probe.FOLDERS[1])],[]):
            report = self.collect(fixture(self.disk,records=records))
            self.unavailable(report)
            self.assertEqual(report["state"],"notReady")
            self.assertEqual(len(report["samples"]),2)
            self.assertFalse(report["samples"][0]["donorBaselineValid"])

    def test_06_constructed_vtable_or_any_owner_roundtrip_rejected(self):
        fields = (A["parent"],A["service"],A["parent"]+0x2b8,A["service"]+0x40068,
            BASE+probe.CATALOG_GLOBAL,A["catalog"],BASE+probe.PARENT_VTABLE[0]+8,BASE+probe.SERVICE_VTABLE[0]+8)
        for address in fields:
            with self.subTest(address=hex(address)):
                reader = fixture(self.disk)
                reader.put(address,reader.value(address)+8)
                report = self.collect(reader)
                self.unavailable(report)
                self.assertEqual(report["state"],"rejected")

    def test_07_zero_ready_links_are_not_ready_and_nonzero_bad_pointers_reject(self):
        fields = (BASE+probe.WORLD_GLOBAL,A["world"]+0x30,A["manager"]+0x58,A["manager"]+0x50,
                  A["world"]+0xe0,A["world"]+0xf0,A["world"]+0xa8,A["service"]+0x40018)
        for address in fields:
            for value,state in ((0,"notReady"),(123,"rejected")):
                reader = fixture(self.disk)
                reader.put(address,value)
                report = self.collect(reader)
                self.unavailable(report)
                self.assertEqual(report["state"],state)

    def test_08_rtti_primary_control_type_and_unique_child_gates(self):
        for kind,index in (("manager",0),("user",1),("actor",2)):
            for offset,value in ((0,0),(4,8),(20,1)):
                reader = fixture(self.disk)
                col = BASE+0x100000+index*0x1000+0x100
                reader.put(col+offset,value,"<I")
                self.unavailable(self.collect(reader))
            reader = fixture(self.disk)
            desc = BASE+0x100000+index*0x1000+0x200
            reader.put(desc+16,ord('x'),"<B")
            self.unavailable(self.collect(reader))
        for address in (A["user"]+0xd0,A["user"]+0xd8,A["actor"]+0xa0):
            reader = fixture(self.disk)
            reader.put(address,A["parent"])
            self.unavailable(self.collect(reader))

    def test_09_map_bounds_empty_nonempty_null_and_bucket_31_limit(self):
        for offset,value in ((0,0),(0,probe.LIMIT+1),(4,4),(8,0),(8,probe.LIMIT+1),(16,0),(24,0)):
            reader = fixture(self.disk)
            reader.put(reader.maps[0]["address"]+offset,value,"<Q" if offset>=16 else "<I")
            self.unavailable(self.collect(reader))
        reader = fixture(self.disk)
        reader.put(reader.maps[0]["nodes"][0]["bucket"],32,"<I")
        self.unavailable(self.collect(reader))

    def test_10_bucket_index_duplicate_and_node_back_position(self):
        reader = fixture(self.disk)
        node = reader.maps[0]["nodes"][0]
        reader.put(node["bucket"]+12+node["slot"]*8,2,"<I")
        self.unavailable(self.collect(reader))
        reader = fixture(self.disk)
        node = reader.maps[0]["nodes"][0]
        reader.put(node["node"],reader.value(node["node"],"<I")+1,"<I")
        self.unavailable(self.collect(reader))
        reader = fixture(self.disk)
        node = reader.maps[0]["nodes"][0]
        reader.put(node["bucket"],2,"<I")
        reader.put(node["bucket"]+16,probe.HASHES[0],"<I")
        reader.put(node["bucket"]+20,0,"<I")
        self.unavailable(self.collect(reader))

    def test_11_real_equal_hash_distinct_strings_get_exact_membership(self):
        names = COLLISION+probe.NAMES[2:]
        hashes = tuple(probe.name_hash(name.encode()) for name in names)
        records = [(COLLISION[1],probe.FOLDERS[1]),(COLLISION[0],probe.FOLDERS[0])]
        reader = fixture(self.disk,records=records)
        with mock.patch.object(probe,"NAMES",names),mock.patch.object(probe,"HASHES",hashes):
            watch = probe.Watch(reader,BASE,self.disk.length)
            result = probe.query(watch,reader.maps[0]["address"],"collision fixture")
        self.assertEqual(result["queries"][COLLISION[0]]["folder"],probe.FOLDERS[0])
        self.assertEqual(result["queries"][COLLISION[1]]["folder"],probe.FOLDERS[1])
        reader = fixture(self.disk,records=records[:1])
        with mock.patch.object(probe,"NAMES",names),mock.patch.object(probe,"HASHES",hashes):
            result = probe.query(probe.Watch(reader,BASE,self.disk.length),reader.maps[0]["address"],"collision fixture")
        self.assertEqual(result["queries"][COLLISION[0]]["membership"],"absent")

    def test_12_uncached_key_must_still_hash_to_bucket_and_no_casefold(self):
        reader = fixture(self.disk)
        node = reader.maps[0]["nodes"][0]
        reader.put(node["key"]+12,0xffffffff,"<I")
        reader.put(node["chars"],ord('X'),"<B")
        report = self.collect(reader)
        self.unavailable(report)
        self.assertIn("differs from bucket hash",report["reason"])
        records = [(probe.NAMES[0].upper(),probe.FOLDERS[0]),(probe.NAMES[1],probe.FOLDERS[1])]
        report = self.collect(fixture(self.disk,records=records))
        self.unavailable(report)
        self.assertEqual(report["state"],"notReady")

    def test_13_duplicate_exact_name_is_not_unique_membership(self):
        records = list(zip(probe.NAMES[:2],probe.FOLDERS))+[(probe.NAMES[0],probe.FOLDERS[0])]
        report = self.collect(fixture(self.disk,records=records))
        self.unavailable(report)
        self.assertIn("occurs more than once",report["reason"])

    def test_14_bounded_unaligned_strings_and_uncached_length_hash(self):
        reader = fixture(self.disk,private=True)
        for map_ in reader.maps:
            for node in map_["nodes"]:
                for holder in (node["key"],node["folderHolder"]):
                    reader.put(holder+8,0xffffffff,"<I")
                    reader.put(holder+12,0xffffffff,"<I")
        report = self.collect(reader)
        self.assertEqual(report["state"],"observed",report.get("reason"))
        self.assertTrue(any(int(row["address"],16)%8 for row in report["samples"][0]["dependencies"] if "NUL-inclusive" in row["field"]))
        self.assertLessEqual(sum(row["size"] for row in report["samples"][0]["dependencies"]),probe.READ_BUDGET)

    def test_15_null_holder_bad_string_nul_length_cached_hash_and_folders(self):
        for holder_name,chars_name,max_ in (("key","chars",128),("folderHolder","folderChars",384)):
            for mode in ("nullholder","nullchars","toolong","nonNul","embeddedNul","hash","unknownNonNul"):
                reader = fixture(self.disk)
                node = reader.maps[0]["nodes"][0]
                holder,chars = node[holder_name],node[chars_name]
                if mode=="nullholder":
                    reader.put(node["node"]+(8 if holder_name=="key" else 16),0)
                elif mode=="nullchars":reader.put(holder,0)
                elif mode=="toolong":reader.put(holder+8,max_+1,"<I")
                elif mode=="nonNul":reader.segments[chars][-1]=ord('x')
                elif mode=="embeddedNul":reader.segments[chars][0]=0
                elif mode=="hash":reader.put(holder+12,1,"<I")
                else:
                    reader.put(holder+8,0xffffffff,"<I")
                    reader.segments[chars]=bytearray(b"x"*(max_+1))
                with self.subTest(holder=holder_name,mode=mode):self.unavailable(self.collect(reader))
        for folder in ("", "/absolute", "a//b", "a/../b", "a\\b", "a/\x01b"):
            self.unavailable(self.collect(fixture(self.disk,records=[(probe.NAMES[0],folder),(probe.NAMES[1],probe.FOLDERS[1])])))

    def test_16_full_dependency_every_span_is_rechecked(self):
        baseline = self.collect(fixture(self.disk,private=True))
        dependencies = baseline["samples"][0]["dependencies"]
        self.assertGreater(len(dependencies),60)
        for row in dependencies:
            with self.subTest(field=row["field"]):
                reader = fixture(self.disk,private=True)
                original,seen = reader.read,0
                address,size = int(row["address"],16),row["size"]
                def drift(at,n):
                    nonlocal seen
                    raw = original(at,n)
                    if (at,n)==(address,size):
                        seen+=1
                        if seen>=2 and raw is not None:
                            raw=bytes([raw[0]^1])+raw[1:]
                    return raw
                reader.read=drift
                self.unavailable(self.collect(reader))

    def test_17_insert_or_byte_change_without_epoch_change_is_unstable(self):
        for action in ("folder","bucketpadding","replacepointer"):
            reader = fixture(self.disk)
            node = reader.maps[0]["nodes"][0]
            def mutate(_):
                if action=="folder":reader.put(node["folderChars"],ord('2'),"<B")
                elif action=="bucketpadding":reader.put(node["bucket"]+4,7,"<I")
                else:reader.put(A["service"]+0x40018,A["interface"]+8)
            report = self.collect(reader,pause=mutate)
            self.unavailable(report)
            self.assertEqual(report["state"],"unstable")
            self.assertTrue(report["samples"][0]["stableDuringSample"])

    def test_18_process_identity_change_or_end_refuses_two_samples(self):
        before = identity(self.disk)
        for after in (identity(self.disk,pid=43211),identity(self.disk,creationTime100ns="999"),
                      identity(self.disk,moduleBase=BASE+8),identity(self.disk,moduleSize=self.disk.length-8),
                      identity(self.disk,imagePath="different.exe"),RuntimeError("process ended")):
            report = self.collect(fixture(self.disk),identities=[before,after])
            self.unavailable(report)
            self.assertEqual(report["state"],"unstable")
        for bad in (identity(self.disk,pid=0),identity(self.disk,creationTime100ns="0"),identity(self.disk,moduleBase=BASE+8)):
            report = self.collect(fixture(self.disk),identities=[bad])
            self.unavailable(report)
            self.assertEqual(report["samples"],[])

    def test_19_bad_code_image_extent_or_read_budget_refuses(self):
        reader = fixture(self.disk)
        reader.put(BASE+probe.WINDOWS[0][0],0,"<B")
        self.unavailable(self.collect(reader))
        for size in (0,probe.CATALOG_GLOBAL+7,probe.PARENT_VTABLE[0]+127,probe.core.MAX_IMAGE_SIZE+1):
            with self.assertRaises(probe.ProbeError):probe.validate_code(fixture(self.disk),BASE,size)
        with mock.patch.object(probe,"READ_BUDGET",16):self.unavailable(self.collect(fixture(self.disk)))

    def run_main(self,reader,identities,digests=None):
        reports=[]
        with mock.patch("sys.argv",["probe_part_catalog.py","--pid","43210","--output","unused.json"]), \
             mock.patch.object(probe.appearance,"output_path",return_value=Path("unused.json")), \
             mock.patch.object(probe.core,"load_profile",return_value=({},None)), \
             mock.patch.object(probe.core,"Reader",return_value=reader), \
             mock.patch.object(probe.subprocess,"check_output",return_value=probe.roster.VERSION), \
             mock.patch.object(probe.roster,"validate_layout_build"), \
             mock.patch.object(probe.health,"process_identity",side_effect=identities), \
             mock.patch.object(probe.appearance,"file_digest",side_effect=digests or [probe.roster.SHA256]*2), \
             mock.patch.object(probe.appearance,"write_report",side_effect=lambda _,report:reports.append(report)), \
             mock.patch.object(probe.time,"sleep"),contextlib.redirect_stdout(io.StringIO()):
            code=probe.main()
        reader.close.assert_called_once()
        return code,reports[0]

    def test_20_cli_final_pid_creation_module_digest_or_liveness_clears_nested_success(self):
        before=identity(self.disk)
        for mode in ("pid","creation","module","digest","ended"):
            reader=fixture(self.disk)
            after={"pid":identity(self.disk,pid=43211),"creation":identity(self.disk,creationTime100ns="999"),
                   "ended":RuntimeError("same handle process ended")}.get(mode,before)
            if mode=="module":reader.module.side_effect=[(BASE,self.disk.length,self.disk.path),(BASE,self.disk.length-8,self.disk.path)]
            code,report=self.run_main(reader,[before,before,after],
                [probe.roster.SHA256,"0"*64] if mode=="digest" else None)
            self.assertEqual(code,1)
            self.unavailable(report)
            self.assertEqual(report["state"],"unstable")
            self.assertEqual(len(report["samples"]),2)
        code,report=self.run_main(fixture(self.disk),[before]*3)
        self.assertEqual(code,0)
        self.assertEqual(report["state"],"observed")

    def test_21_output_root_existing_file_and_symlink_guard(self):
        runtime=probe.ROOT/"runtime"
        with tempfile.TemporaryDirectory(prefix="part-catalog-check-",dir=runtime) as root:
            path=Path(root)/"report.json"
            probe.appearance.write_report(probe.appearance.output_path(path),{"ok":True})
            self.assertEqual(json.loads(path.read_text()),{"ok":True})
            with self.assertRaises(probe.ProbeError):probe.appearance.output_path(path)
            with self.assertRaises(RuntimeError):probe.appearance.output_path(probe.ROOT/"tools/rejected-part-catalog.json")
            target=Path(root)/"external.json"
            target.write_text("sentinel")
            link=Path(root)/"link.json"
            try:link.symlink_to(target)
            except OSError:pass
            else:
                with self.assertRaises(RuntimeError):probe.appearance.write_report(link,{"overwritten":True})
                self.assertEqual(target.read_text(),"sentinel")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe",type=Path,help="fixed original EXE on disk; defaults to runtime installation")
    args=parser.parse_args()
    if args.exe is None:
        installation=json.loads((probe.ROOT/"runtime/installation.json").read_text(encoding="utf-8-sig"))
        args.exe=Path(installation["gameRoot"])/"bin64/CrimsonDesert.exe"
    CatalogChecks.exe=args.exe
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CatalogChecks))
    raise SystemExit(not result.wasSuccessful())


if __name__=="__main__":
    main()
