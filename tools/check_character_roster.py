"""Exercise read-only catalog/identity guards without opening a game process."""
import struct
import unittest
from unittest import mock

import probe_character_roster as probe

BASE, IMAGE_SIZE = 0x140000000, 0x20000000


class FakeReader:
    def __init__(self):
        self.segments, self.names, self.reads = {}, {}, []

    def block(self, address, size):
        self.segments[address] = bytearray(size)

    def put(self, address, value, fmt="<Q"):
        data = struct.pack(fmt, value)
        for origin, raw in self.segments.items():
            offset = address - origin
            if 0 <= offset <= len(raw) - len(data):
                raw[offset:offset + len(data)] = data
                return
        self.segments[address] = bytearray(data)

    def read(self, address, size):
        self.reads.append((address, size))
        for origin, raw in self.segments.items():
            offset = address - origin
            if 0 <= offset <= len(raw) - size:
                return bytes(raw[offset:offset + size])
        return None

    def value(self, address, fmt="<Q"):
        raw = self.read(address, struct.calcsize(fmt))
        return struct.unpack(fmt, raw)[0] if raw else None

    def rtti(self, address, base, length):
        return self.names.get(address)


def catalog_reader(count=1):
    reader = FakeReader()
    manager, directory, record, obj, name = 0x20000, 0x30000, 0x40000, 0x50000, 0x60000
    reader.put(BASE + probe.CATALOGS["character"][0], manager)
    reader.block(manager, 0xA0)
    reader.names[manager] = ".?AVCharacterInfoManager@pa@@"
    reader.put(manager + 8, count, "<I")
    reader.put(manager + 0x58, directory)
    reader.block(directory, 16)
    reader.put(directory, record)
    reader.block(record, 0xC0)
    reader.put(record, 1, "<I")
    reader.put(record + 8, obj)
    reader.put(record + 0xBE, 7, "<H")
    reader.put(obj, name)
    reader.block(name, 128)
    reader.segments[name][:6] = b"Kliff\0"
    return reader


def actor_reader(realm="Server", char_index=0):
    reader = FakeReader()
    actor, table, status, component = 0x70000, 0x80000, 0x90000, 0xA0000
    for address, size in ((actor, 0x100), (table, 0x200), (status, 0x100), (component, 0x40)):
        reader.block(address, size)
    reader.names[actor] = f".?AV{realm}ChildOnlyInGameActor@pa@@"
    reader.names[status] = f".?AV{realm}StatusActorComponent@pa@@"
    reader.names[component] = f".?AV{realm}MercenaryClanActorComponent@pa@@"
    reader.put(actor + 0x68, table)
    reader.put(table + 0x20, status)
    reader.put(status + 8, actor)
    reader.put(status + 0x30, char_index, "<H")
    reader.put(table + 0x110, component)
    reader.put(component + 8, actor)
    reader.put(component + 0x20, 1, "<I")
    reader.put(component + 0x18, 0xB0000)
    reader.put(0xB0000, 0xC0000)
    reader.block(0xC0000, 0x58)
    reader.put(0xC0020, char_index, "<H")
    reader.put(0xC0028, 98, "<q")
    reader.put(0xC0050, 456, "<I")
    return reader


CATALOG_FIXTURE = {"character": {"count": 1, "records": [
    {"directory_index": 0, "character_key_u32": 1, "name": "Kliff", "mercenary_directory_index_u16": 7}]},
    "mercenary": {"count": 8, "records": [{"directory_index": 7, "mercenary_key_u8": 9}]}}


class Guards(unittest.TestCase):
    def test_catalog_row_number_is_not_character_key(self):
        result = probe.catalog(catalog_reader(), BASE, IMAGE_SIZE, "character")
        row = result["records"][0]
        self.assertEqual((row["directory_index"], row["character_key_u32"],
                          row["mercenary_directory_index_u16"], row["name"]), (0, 1, 7, "Kliff"))
        self.assertTrue(result["stable_during_read"])
        self.assertFalse(result["f1_roster_verified"])

    def test_invalid_count_never_reads_bulk_directory(self):
        for count in (0, 65536, 0xFFFFFFFF):
            reader = catalog_reader(count)
            with self.assertRaisesRegex(RuntimeError, "count/directory"):
                probe.catalog(reader, BASE, IMAGE_SIZE, "character")
            self.assertFalse(any(address == 0x30000 for address, _ in reader.reads))

    def test_global_must_fit_module_before_read(self):
        reader = catalog_reader()
        with self.assertRaisesRegex(RuntimeError, "escaped"):
            probe.catalog(reader, BASE, 0x10000, "character")
        self.assertEqual(reader.reads, [])

    def test_wrong_manager_rtti_never_uses_catalog_layout(self):
        reader = catalog_reader()
        reader.names[0x20000] = ".?AVServerActorManager@pa@@"
        with self.assertRaisesRegex(RuntimeError, "RTTI mismatch"):
            probe.catalog(reader, BASE, IMAGE_SIZE, "character")
        self.assertFalse(any(address == 0x20008 for address, _ in reader.reads))

    def test_absent_record_is_not_materialized(self):
        reader = catalog_reader()
        reader.put(0x30000, 0)
        result = probe.catalog(reader, BASE, IMAGE_SIZE, "character")
        self.assertEqual(result["loaded_count"], 0)
        self.assertTrue(result["absent_records_not_loaded"])
        self.assertFalse(any(address == 0x40000 for address, _ in reader.reads))

    def test_unreadable_or_duplicate_record_rejects_partial_catalog(self):
        reader = catalog_reader()
        del reader.segments[0x40000]
        with self.assertRaisesRegex(RuntimeError, "partial catalog"):
            probe.catalog(reader, BASE, IMAGE_SIZE, "character")
        reader = catalog_reader(2)
        reader.put(0x30008, 0x40000)
        with self.assertRaisesRegex(RuntimeError, "aliases"):
            probe.catalog(reader, BASE, IMAGE_SIZE, "character")

    def test_changed_payload_disallows_identity_conclusion(self):
        reader, calls = catalog_reader(), []
        original = reader.read

        def changing(address, size):
            raw = original(address, size)
            if (address, size) == (0x40000, 0xC0):
                calls.append(address)
                if len(calls) > 1:
                    return bytes([2]) + raw[1:]
            return raw

        reader.read = changing
        with self.assertRaisesRegex(RuntimeError, "record changed"):
            probe.catalog(reader, BASE, IMAGE_SIZE, "character")

    def test_changed_manager_disallows_stale_catalog(self):
        reader, calls = catalog_reader(), []
        original = reader.value

        def changing(address, fmt="<Q"):
            if address == BASE + probe.CATALOGS["character"][0]:
                calls.append(address)
                if len(calls) > 1:
                    return 0x20100
            return original(address, fmt)

        reader.value = changing
        with self.assertRaisesRegex(RuntimeError, "catalog changed"):
            probe.catalog(reader, BASE, IMAGE_SIZE, "character")

    def test_status_mapping_keeps_three_namespaces_separate(self):
        row = probe.actor_identity(actor_reader(), 0x70000, "Server", BASE, IMAGE_SIZE, CATALOG_FIXTURE)
        self.assertEqual(row["character_directory_index"], 0)
        self.assertEqual(row["character_key_u32"], 1)
        self.assertEqual(row["mercenary_directory_index_u16"], 7)
        self.assertEqual(row["loaded_mercenary_record"]["mercenary_key_u8"], 9)
        self.assertFalse(row["native_control_identity_verified"])

    def test_status_index_is_bounded_by_actual_catalog(self):
        with self.assertRaisesRegex(RuntimeError, "index outside catalog"):
            probe.actor_identity(actor_reader(char_index=3), 0x70000, "Server", BASE, IMAGE_SIZE, CATALOG_FIXTURE)

    def test_status_owner_mismatch_stops_before_index_read(self):
        reader = actor_reader()
        reader.put(0x90008, 0x70001)
        with self.assertRaisesRegex(RuntimeError, "backlink mismatch"):
            probe.actor_identity(reader, 0x70000, "Server", BASE, IMAGE_SIZE, {})
        self.assertFalse(any(address == 0x90030 for address, _ in reader.reads))

    def test_unloaded_status_record_preserves_unknown(self):
        row = probe.actor_identity(actor_reader(), 0x70000, "Server", BASE, IMAGE_SIZE,
                                   {"character": {"count": 1, "records": []}, "mercenary": {"records": []}})
        self.assertIsNone(row["character_key_u32"])
        self.assertFalse(row["loaded_catalog_mapping_available"])
        self.assertFalse(row["f1_selectability_verified"])

    def test_client_actor_never_uses_server_owned_layout(self):
        reader = actor_reader("Client")
        with self.assertRaisesRegex(RuntimeError, "server actor"):
            probe.owned_server_records(reader, 0x70000, BASE, IMAGE_SIZE, {})
        self.assertEqual(reader.reads, [])

    def test_client_component_never_uses_server_owned_layout(self):
        reader = actor_reader()
        reader.names[0xA0000] = ".?AVClientMercenaryClanActorComponent@pa@@"
        result = probe.owned_server_records(reader, 0x70000, BASE, IMAGE_SIZE, {})
        self.assertFalse(result["available"])
        self.assertFalse(any(address in (0xA0018, 0xA0020) for address, _ in reader.reads))

    def test_owned_owner_and_count_stop_before_bulk_read(self):
        for bad_owner, count in ((0x70001, 1), (0x70000, 4097)):
            reader = actor_reader()
            reader.put(0xA0008, bad_owner)
            reader.put(0xA0020, count, "<I")
            result = probe.owned_server_records(reader, 0x70000, BASE, IMAGE_SIZE, {})
            self.assertFalse(result["available"])
            self.assertFalse(any(address == 0xB0000 for address, _ in reader.reads))

    def test_owned_record_is_not_character_key_or_roster(self):
        result = probe.owned_server_records(actor_reader(), 0x70000, BASE, IMAGE_SIZE, CATALOG_FIXTURE)
        self.assertTrue(result["available"])
        row = result["records"][0]
        self.assertEqual((row["character_directory_index"], row["character_key_u32"],
                          row["owned_mercenary_no_i64"], row["actor_handle_u32"]), (0, 1, 98, 456))
        self.assertFalse(result["f1_roster_verified"])

    def test_owned_payload_change_drops_entire_interpretation(self):
        reader, calls = actor_reader(), []
        original = reader.read

        def changing(address, size):
            raw = original(address, size)
            if (address, size) == (0xC0000, 0x58):
                calls.append(address)
                if len(calls) > 1:
                    return raw[:-1] + bytes([1])
            return raw

        reader.read = changing
        result = probe.owned_server_records(reader, 0x70000, BASE, IMAGE_SIZE, CATALOG_FIXTURE)
        self.assertFalse(result["available"])
        self.assertEqual(result["records"], [])

    def test_owned_unknown_catalog_index_drops_entire_interpretation(self):
        reader = actor_reader(char_index=1)
        result = probe.owned_server_records(reader, 0x70000, BASE, IMAGE_SIZE, CATALOG_FIXTURE)
        self.assertFalse(result["available"])
        self.assertIn("index outside catalog", result["reason"])
        self.assertNotIn("records", result)

    def test_owned_invalid_index_sentinel_stays_unknown(self):
        result = probe.owned_server_records(actor_reader(char_index=0xFFFF), 0x70000,
                                            BASE, IMAGE_SIZE, CATALOG_FIXTURE)
        self.assertTrue(result["available"])
        row = result["records"][0]
        self.assertTrue(row["invalid_character_index_sentinel"])
        self.assertIsNone(row["character_key_u32"])
        self.assertIsNone(row["character_name"])

    def test_build_pin_cannot_be_bypassed_by_updating_shared_profile(self):
        profile, _ = probe.core.load_profile()
        probe.validate_layout_build(profile, probe.VERSION, probe.SHA256)
        with self.assertRaises(RuntimeError):
            probe.validate_layout_build(profile, "1.0.0.2977", probe.SHA256)
        changed = {**profile, "game_version": "1.0.0.2977", "game_sha256": "0" * 64}
        with self.assertRaisesRegex(RuntimeError, "not been reviewed"):
            probe.validate_layout_build(changed, changed["game_version"], changed["game_sha256"])

    def test_public_or_non_json_output_rejected(self):
        for path in (probe.ROOT / "docs/roster.json", probe.ROOT / "runtime/roster.txt",
                     probe.ROOT / "runtime/../docs/roster.json"):
            with self.assertRaisesRegex(RuntimeError, "ignored runtime"):
                probe.output_path(path)
        self.assertEqual(probe.output_path(probe.ROOT / "runtime/roster.json"),
                         probe.ROOT / "runtime/roster.json")

    def test_output_rejects_linked_runtime_and_intermediate_directory(self):
        for linked in (probe.ROOT / "runtime", probe.ROOT / "runtime/linked",
                       probe.ROOT / "runtime/linked/roster.json"):
            with mock.patch.object(probe.Path, "is_symlink", autospec=True,
                                   side_effect=lambda path: path == linked):
                with self.assertRaisesRegex(RuntimeError, "symlinks or junctions"):
                    probe.output_path(probe.ROOT / "runtime/linked/roster.json")
        if hasattr(probe.Path, "is_junction"):
            with mock.patch.object(probe.Path, "is_junction", autospec=True,
                                   side_effect=lambda path: path == probe.ROOT / "runtime"):
                with self.assertRaisesRegex(RuntimeError, "symlinks or junctions"):
                    probe.output_path(probe.ROOT / "runtime/roster.json")


if __name__ == "__main__":
    unittest.main(verbosity=2)
