"""Local bridge: real Minecraft state -> native red-side collision proxies.

This first slice uses the game's one-metre grid cube as a diagnostic visual.
Minecraft owns blocks, inventory and drops; prototype crafting is disabled. Only our named scene
objects are reconciled; native maps/NPCs/terrain are never enumerated or edited.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from bridge.red_side import RedSide, GameAPIError

ROOT = Path(__file__).resolve().parents[1]
ORIGIN_FILE = ROOT / "runtime/bridge-origin.json"
PREFAB = "/object/00_common/system/cd_testfield_grid_box_1m.prefab"
PROJECT = "CrimsonMCPrototype"
ALLOWED_BLOCKS = {"minecraft:oak_log", "minecraft:oak_planks", "minecraft:cobblestone",
                  "minecraft:dirt", "minecraft:stone", "minecraft:crafting_table"}
INVENTORY_ACTIONS = {"/ui/grant", "/ui/add-item", "/ui/select", "/ui/consume"}
PLACEMENT_ACTIONS = {"/ui/place", "/ui/front", "/ui/place-selected", "/ui/front-selected"}
ACTIONS = INVENTORY_ACTIONS | PLACEMENT_ACTIONS | {
    "/ui/anchor", "/ui/reconnect", "/ui/break", "/ui/break-last"}


def strict_integer(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise GameAPIError(f"{name} must be an integer from {minimum} to {maximum}")
    return value


def tsv_text(value):
    if not isinstance(value, str):
        raise GameAPIError("Minecraft item text must be a string")
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ")


def mc(path="/api/state", body=None):
    data = None if body is None else json.dumps(body).encode()
    request = Request("http://127.0.0.1:8766" + path, data=data,
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=7) as response:
            return json.load(response)
    except HTTPError as error:
        with error:
            details = json.load(error)
        uncertain = (" Result may be unknown; refresh Minecraft state before retrying."
                     if body is not None and error.code >= 500 else "")
        raise GameAPIError(f"Minecraft request failed (HTTP {error.code}): {details}.{uncertain}") from error


def mutate_mc(path, body):
    try:
        return mc(path, body)
    except OSError as error:
        # A lost response does not prove the server rejected a queued operation.
        raise GameAPIError("Minecraft action response unavailable; result unknown. "
                           "Refresh Minecraft inventory/build state before retrying. " + str(error)) from error


class Bridge:
    def __init__(self):
        self.red = RedSide()
        self.lock = threading.Lock()
        self.message = "Start the Minecraft authority server, then set an anchor."
        self.origin = json.loads(ORIGIN_FILE.read_text()) if ORIGIN_FILE.exists() else None

    def ready(self):
        _, status = self.red.request("/api/status")
        if not status.get("ready") or not status.get("buildOk"):
            raise GameAPIError("Enter the Crimson Desert world; adapter is not ready")
        return status

    def anchor(self):
        self.ready()
        state = mc()
        if state["blocks"]:
            raise GameAPIError("Existing MC blocks keep their anchor; break them before moving the lab")
        _, player = self.red.request("/api/player")
        _, camera = self.red.request("/api/camera")
        if not camera.get("view"):
            raise GameAPIError("Camera view unavailable")
        x = player["x"] + camera["view"]["x"] * 4
        z = player["z"] + camera["view"]["z"] * 4
        ground = self.red.ground(x, player["y"] + 5, z)
        self.origin = {"x": x, "y": ground["y"] + 0.03, "z": z}
        ORIGIN_FILE.parent.mkdir(exist_ok=True)
        ORIGIN_FILE.write_text(json.dumps(self.origin, indent=2))
        self.message = "Anchor set four metres in front of the player. Cell (0,0,0) is ready."

    def all_objects(self):
        objects, offset = [], 0
        while True:
            _, page = self.red.request(f"/api/objects?offset={offset}&limit=500")
            objects.extend(page["items"])
            offset = page.get("nextOffset")
            if offset is None:
                return objects

    def cell(self, block):
        return (int(block["x"]), int(block["y"]) - 64, int(block["z"]))

    def world(self, cell):
        if self.origin is None:
            raise GameAPIError("Set the anchor first")
        return {"x": self.origin["x"] + cell[0], "y": self.origin["y"] + cell[1],
                "z": self.origin["z"] + cell[2]}

    def sync(self, state=None):
        self.ready()
        if self.origin is None:
            raise GameAPIError("Set the anchor before reconnecting blocks")
        state = mc() if state is None else state
        blocks = state["blocks"]
        if len(blocks) > 128:
            raise GameAPIError("Native proxy limit is 128 blocks in this slice")
        existing = [o for o in self.all_objects() if o.get("project") == PROJECT]
        used = set()
        for block in blocks:
            position = self.world(self.cell(block))
            match = next((o for o in existing if o["uid"] not in used and not o.get("hidden")
                          and o["prefab"] == PREFAB and abs(o.get("scale", 1) - 1) < 0.001
                          and all(abs(o[a] - position[a]) < 0.015 for a in "xyz")), None)
            if match:
                used.add(match["uid"])
                continue
            _, admitted = self.red.request("/api/objects", "POST", {"prefab": PREFAB, **position, "scale": 1})
            uid = admitted["uid"]
            self.red.request(f"/api/objects/{uid}/project", "POST", {"name": PROJECT})
            used.add(uid)
        for obj in existing:
            if obj["uid"] not in used:
                self.red.request(f"/api/objects/{obj['uid']}", "DELETE")
        return state

    def action(self, path, body):
        if path not in ACTIONS:
            raise GameAPIError("Unknown action")
        if not isinstance(body, dict):
            raise GameAPIError("JSON object required")
        with self.lock:
            if path in INVENTORY_ACTIONS:
                mutation = {"operationId": str(uuid.uuid4())}
                if path == "/ui/grant":
                    item = body.get("item")
                    if not isinstance(item, str) or not item or len(item) > 256:
                        raise GameAPIError("item must be a Minecraft item ID")
                    mutation["item"] = item
                    verb = "Granted one original Minecraft stack of " + item
                elif path == "/ui/add-item":
                    # Console-style direct add: item ID or name, an explicit count and a player.
                    item = body.get("item")
                    if not isinstance(item, str) or not item or len(item) > 256:
                        raise GameAPIError("item must be a Minecraft item ID or name")
                    count = strict_integer(body.get("count"), "count", 1, 6400)
                    player = body.get("player", "console")
                    if not isinstance(player, str) or not player or len(player) > 64:
                        raise GameAPIError("player must be a target player name")
                    if player != "console":
                        # This prototype has no real MC player entity; reject rather than guess.
                        raise GameAPIError("unknown player; this prototype owns one console inventory")
                    mutation.update({"item": item, "count": count, "player": player})
                    verb = f"Added {count} x {item} to {player}"
                elif path == "/ui/select":
                    mutation["slot"] = strict_integer(body.get("slot"), "slot", 0, 35)
                    verb = f"Selected Minecraft inventory slot {mutation['slot']} (native hand model not connected)"
                else:
                    verb = "Consumed one selected non-block item; special item effects are not connected"
                # Inventory actions work while Crimson Desert is closed and never move the anchor.
                result = mutate_mc("/api/" + path.rsplit("/", 1)[1], mutation)
                self.message = f"{verb}. Revision {result['revision']}"
                return result
            if path == "/ui/anchor":
                self.anchor()
                return
            if path == "/ui/reconnect":
                self.sync()
                self.message = "Native collision proxies reconciled with Minecraft."
                return
            self.ready()
            if self.origin is None:
                raise GameAPIError("Set an anchor first")
            state = mc()
            if len(state["blocks"]) >= 128 and path in PLACEMENT_ACTIONS:
                raise GameAPIError("Native proxy limit: 128 blocks")
            selected_placement = path in {"/ui/place-selected", "/ui/front-selected"}
            if selected_placement:
                selected = state.get("selectedItem")
                if not selected:
                    raise GameAPIError("The selected Minecraft slot is empty")
                if selected.get("id") not in ALLOWED_BLOCKS or selected.get("placeSupported") is not True:
                    raise GameAPIError("This selected item has no native block placement support yet")
            if path in {"/ui/front", "/ui/front-selected"}:
                _, player = self.red.request("/api/player")
                _, camera = self.red.request("/api/camera")
                if not camera.get("view"):
                    raise GameAPIError("Camera view unavailable")
                x = round(player["x"] + camera["view"]["x"] * 3 - self.origin["x"])
                z = round(player["z"] + camera["view"]["z"] * 3 - self.origin["z"])
                column = [self.cell(b)[1] for b in state["blocks"] if self.cell(b)[0] == x and self.cell(b)[2] == z]
                ground = self.red.ground(self.origin["x"]+x, player["y"]+5, self.origin["z"]+z)
                y = max(max(column, default=-1)+1, math.floor(ground["y"]-self.origin["y"]+0.10), 0)
            elif path == "/ui/break-last":
                if not state["blocks"]:
                    raise GameAPIError("No MC block to break")
                x, y, z = self.cell(state["blocks"][-1])
            elif path in {"/ui/place", "/ui/break", "/ui/place-selected"}:
                x, y, z = (strict_integer(body.get(a, 0), a, 0 if a == "y" else -16,
                                          31 if a == "y" else 16) for a in "xyz")
            else:
                raise GameAPIError("Unknown action")
            if abs(x) > 16 or abs(z) > 16 or not 0 <= y <= 31:
                raise GameAPIError("Stay within the 33 x 32 x 33 prototype grid")
            mutation = {"x": x, "y": y+64, "z": z, "operationId": str(uuid.uuid4())}
            if selected_placement:
                result = mutate_mc("/api/place-selected", mutation)
                verb = "Placed"
            elif path in {"/ui/place", "/ui/front"}:
                block = body.get("block")
                if block not in ALLOWED_BLOCKS:
                    raise GameAPIError("Unsupported block")
                mutation["block"] = block
                result = mutate_mc("/api/place", mutation)
                verb = "Placed"
            else:
                result = mutate_mc("/api/break", mutation)
                verb = "Broke"
            # MC remains authoritative if a native spawn fails; reconnect repairs presentation.
            try:
                self.sync(result)
            except Exception as error:
                self.message = (f"Minecraft committed revision {result['revision']} for cell ({x},{y},{z}); "
                                "native sync failed. Use Restore blocks; do not repeat the placement.")
                raise GameAPIError(self.message + " " + str(error)) from error
            self.message = f"{verb} cell ({x},{y},{z}); materials/drops handled by Minecraft."

    def catalog_text(self, search="", offset=0, limit=50):
        strict_integer(offset, "offset", 0, 2**31-1)
        strict_integer(limit, "limit", 1, 100)
        if not isinstance(search, str) or len(search) > 256:
            raise GameAPIError("search must be at most 256 characters")
        with self.lock:
            items = mc("/api/catalog")["items"]
            needle = search.casefold()
            filtered = [item for item in items if needle in item["id"].casefold()
                        or needle in item["name"].casefold()]
            if offset > len(filtered):
                raise GameAPIError("offset exceeds the filtered Minecraft item catalog")
            page = filtered[offset:offset+limit]
            next_offset = offset + len(page) if offset + len(page) < len(filtered) else -1
            lines = [f"catalog\t{len(filtered)}\t{offset}\t{next_offset}"]
            for item in page:
                maximum = strict_integer(item["maxCount"], "Minecraft maxCount", 1, 2**31-1)
                if type(item["placeSupported"]) is not bool or type(item["isBlock"]) is not bool:
                    raise GameAPIError("Invalid Minecraft item placement metadata")
                lines.append("\t".join(("item", tsv_text(item["id"]), tsv_text(item["name"]),
                                        str(maximum), str(int(item["placeSupported"])), str(int(item["isBlock"])))))
            return "\n".join(lines)

    def inventory_text(self):
        with self.lock:
            state = mc()
            selected = strict_integer(state["selectedSlot"], "Minecraft selectedSlot", 0, 35)
            slots = state["slots"]
            if len(slots) != 36 or {slot.get("slot") for slot in slots} != set(range(36)):
                raise GameAPIError("Minecraft must return all 36 inventory slots")
            lines = [f"inventory\t{state['revision']}\t{selected}"]
            for slot in sorted(slots, key=lambda row: row["slot"]):
                index = strict_integer(slot["slot"], "Minecraft slot", 0, 35)
                if slot.get("empty") is True:
                    lines.append(f"slot\t{index}\t-\t0\t0\t")
                elif slot.get("empty") is False:
                    maximum = strict_integer(slot["maxCount"], "Minecraft maxCount", 1, 2**31-1)
                    count = strict_integer(slot["count"], "Minecraft count", 1, maximum)
                    lines.append("\t".join(("slot", str(index), tsv_text(slot["id"]),
                                            str(count), str(maximum), tsv_text(slot["name"]))))
                else:
                    raise GameAPIError("Invalid Minecraft inventory slot metadata")
            return "\n".join(lines)

    def summary(self, state=None, check_red=True):
        with self.lock:
            lines = ["Minecraft Java 1.21.1 authority", "Visuals: native blue grid proxies (MC textures pending)"]
            try:
                state = mc() if state is None else state
                lines += [f"MC revision: {state['revision']} | blocks: {len(state['blocks'])}",
                          "Anchor: " + ("set" if self.origin else "not set"), "", "Inventory:"]
                lines += [f"  {slot['name']} ({slot['id']}): {slot['count']}"
                          for slot in state["slots"] if not slot["empty"]]
            except Exception as error:
                lines += ["Minecraft backend not ready: " + str(error)]
            if check_red:
                try:
                    status = self.ready()
                    lines += [f"Red side: ready ({status['gameVersion']})"]
                except Exception as error:
                    lines += ["Red-side building unavailable: " + str(error)]
            else:
                lines += ["Red side: not checked; inventory actions require Minecraft only."]
            lines += ["", self.message]
            return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    bridge = Bridge()

    def reply(self, code, text):
        encoded = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        try:
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query, keep_blank_values=True)
            if parsed.path == "/ui/state" and not query:
                self.reply(200, self.bridge.summary())
            elif parsed.path == "/ui/inventory" and not query:
                self.reply(200, self.bridge.inventory_text())
            elif parsed.path == "/ui/catalog":
                if set(query) - {"search", "offset", "limit"} or any(len(value) != 1 for value in query.values()):
                    raise GameAPIError("Invalid or repeated catalog query parameter")
                offset, limit = query.get("offset", ["0"])[0], query.get("limit", ["50"])[0]
                if not offset.isascii() or not offset.isdecimal() or not limit.isascii() or not limit.isdecimal():
                    raise GameAPIError("Catalog offset and limit must be unsigned decimal integers")
                self.reply(200, self.bridge.catalog_text(query.get("search", [""])[0], int(offset), int(limit)))
            else:
                self.reply(404, "Unknown endpoint")
        except Exception as error:
            self.reply(400, str(error))

    def do_POST(self):
        try:
            if self.path not in ACTIONS | {"/ui/shutdown"}:
                self.reply(404, "Unknown endpoint")
                return
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("application/json required")
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 65536:
                raise ValueError("invalid length")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise GameAPIError("JSON object required")
            if self.path == "/ui/shutdown":
                self.reply(200, "Bridge stopping; MC and native objects retained.")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            state = self.bridge.action(self.path, body)
            self.reply(200, self.bridge.summary(state=state, check_red=self.path not in INVENTORY_ACTIONS))
        except Exception as error:
            self.reply(400, str(error))

    def log_message(self, format, *args):
        print(format % args, flush=True)


if __name__ == "__main__":
    print("Crimson MC bridge listening on 127.0.0.1:8767", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8767), Handler).serve_forever()
