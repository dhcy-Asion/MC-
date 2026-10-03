"""Local bridge: real Minecraft state -> native red-side collision proxies.

This first slice uses the game's one-metre grid cube as a diagnostic visual.
Minecraft owns blocks, inventory, recipes and drops. Only our named scene
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

from bridge.red_side import RedSide, GameAPIError

ROOT = Path(__file__).resolve().parents[1]
ORIGIN_FILE = ROOT / "runtime/bridge-origin.json"
PREFAB = "/object/00_common/system/cd_testfield_grid_box_1m.prefab"
PROJECT = "CrimsonMCPrototype"
ALLOWED_BLOCKS = {"minecraft:oak_log", "minecraft:oak_planks", "minecraft:cobblestone",
                  "minecraft:dirt", "minecraft:stone", "minecraft:crafting_table"}
ALLOWED_RECIPES = {"minecraft:oak_planks", "minecraft:stick", "minecraft:crafting_table"}


def mc(path="/api/state", body=None):
    data = None if body is None else json.dumps(body).encode()
    request = Request("http://127.0.0.1:8766" + path, data=data,
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=7) as response:
            return json.load(response)
    except HTTPError as error:
        raise GameAPIError(f"Minecraft rejected action: {json.load(error)}") from error


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
        with self.lock:
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
            if path == "/ui/craft":
                recipe = body.get("recipe")
                if recipe not in ALLOWED_RECIPES:
                    raise GameAPIError("Unsupported recipe")
                result = mc("/api/craft", {"recipe": recipe, "operationId": str(uuid.uuid4())})
                self.message = f"Crafted via Minecraft's own recipe: {recipe}. Revision {result['revision']}"
                return
            state = mc()
            if len(state["blocks"]) >= 128 and path in {"/ui/place", "/ui/front"}:
                raise GameAPIError("Native proxy limit: 128 blocks")
            if path == "/ui/front":
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
            elif path in {"/ui/place", "/ui/break"}:
                x, y, z = (int(body.get(a, 0)) for a in "xyz")
            else:
                raise GameAPIError("Unknown action")
            if abs(x) > 16 or abs(z) > 16 or not 0 <= y <= 31:
                raise GameAPIError("Stay within the 33 x 32 x 33 prototype grid")
            mutation = {"x": x, "y": y+64, "z": z, "operationId": str(uuid.uuid4())}
            if path in {"/ui/place", "/ui/front"}:
                block = body.get("block")
                if block not in ALLOWED_BLOCKS:
                    raise GameAPIError("Unsupported block")
                mutation["block"] = block
                result = mc("/api/place", mutation)
                verb = "Placed"
            else:
                result = mc("/api/break", mutation)
                verb = "Broke"
            # MC remains authoritative if a native spawn fails; reconnect repairs presentation.
            self.sync(result)
            self.message = f"{verb} cell ({x},{y},{z}); materials/drops handled by Minecraft."

    def summary(self):
        with self.lock:
            lines = ["Minecraft Java 1.21.1 authority", "Visuals: native blue grid proxies (MC textures pending)"]
            try:
                status = self.ready()
                state = mc()
                lines += [f"Red side: ready ({status['gameVersion']})", f"MC revision: {state['revision']} | blocks: {len(state['blocks'])}",
                          "Anchor: " + ("set" if self.origin else "not set"), "", "Inventory:"]
                lines += [f"  {k.removeprefix('minecraft:')}: {v}" for k,v in state["inventory"].items()]
            except Exception as error:
                lines += ["Backend not ready: " + str(error)]
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
        if self.path != "/ui/state":
            self.reply(404, "Unknown endpoint")
            return
        self.reply(200, self.bridge.summary())

    def do_POST(self):
        try:
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                raise ValueError("application/json required")
            length = int(self.headers.get("Content-Length", 0))
            if not 0 <= length <= 65536:
                raise ValueError("invalid length")
            body = json.loads(self.rfile.read(length))
            if self.path == "/ui/shutdown":
                self.reply(200, "Bridge stopping; MC and native objects retained.")
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            self.bridge.action(self.path, body)
            self.reply(200, self.bridge.summary())
        except Exception as error:
            self.reply(400, str(error))

    def log_message(self, format, *args):
        print(format % args, flush=True)


if __name__ == "__main__":
    print("Crimson MC bridge listening on 127.0.0.1:8767", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8767), Handler).serve_forever()
