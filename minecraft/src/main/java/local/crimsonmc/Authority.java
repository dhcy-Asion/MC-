package local.crimsonmc;

import com.google.gson.*;
import com.mojang.serialization.JsonOps;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.block.Block;
import net.minecraft.block.Blocks;
import net.minecraft.inventory.SimpleInventory;
import net.minecraft.item.BlockItem;
import net.minecraft.item.Item;
import net.minecraft.item.ItemStack;
import net.minecraft.item.Items;
import net.minecraft.recipe.CraftingRecipe;
import net.minecraft.recipe.Ingredient;
import net.minecraft.recipe.ShapedRecipe;
import net.minecraft.recipe.input.CraftingRecipeInput;
import net.minecraft.registry.Registries;
import net.minecraft.registry.RegistryOps;
import net.minecraft.server.MinecraftServer;
import net.minecraft.util.Identifier;
import net.minecraft.util.WorldSavePath;
import net.minecraft.util.math.BlockPos;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Real MC runtime is authoritative; no recipes are reproduced in the bridge. */
public final class Authority implements ModInitializer {
    private static final Logger LOG = LoggerFactory.getLogger("crimsonmc");
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().serializeNulls().create();
    private static final Set<String> BLOCK_IDS = Set.of("minecraft:oak_log", "minecraft:oak_planks",
            "minecraft:cobblestone", "minecraft:dirt", "minecraft:stone", "minecraft:crafting_table");
    private static final Set<String> RECIPE_IDS = Set.of("minecraft:oak_planks", "minecraft:stick", "minecraft:crafting_table");
    private static final int SCHEMA_VERSION = 1;
    private final SimpleInventory inventory = new SimpleInventory(36);
    // Tombstones are retained so a restart repairs stale chunk saves after a crash.
    private final Map<BlockPos, String> touched = new LinkedHashMap<>();
    private record Receipt(String path, JsonObject request, JsonObject result) { }
    private final Map<String, Receipt> receipts = new LinkedHashMap<>();
    private MinecraftServer server;
    private HttpServer http;
    private ExecutorService httpWorkers;
    private Path stateFile;
    private long revision;
    private int selectedSlot;

    @Override public void onInitialize() {
        ServerLifecycleEvents.SERVER_STARTED.register(this::start);
        ServerLifecycleEvents.SERVER_STOPPING.register(s -> stop());
    }

    private void start(MinecraftServer s) {
        server = s;
        stateFile = s.getSavePath(WorldSavePath.ROOT).resolve("crimsonmc-state.json");
        try {
            if (Files.exists(stateFile)) {
                JsonObject saved = JsonParser.parseString(Files.readString(stateFile)).getAsJsonObject();
                load(saved);
                // Migrate only a validated legacy snapshot; never overwrite an unknown future format.
                if (!saved.has("schemaVersion")) save();
            }
            else {
                inventory.addStack(new ItemStack(Registries.ITEM.get(Identifier.of("minecraft:oak_log")), 16));
                inventory.addStack(new ItemStack(Registries.ITEM.get(Identifier.of("minecraft:cobblestone")), 64));
                inventory.addStack(new ItemStack(Registries.ITEM.get(Identifier.of("minecraft:dirt")), 32));
                save();
            }
            // Only our recorded experiment coordinates are reconciled.
            for (var e : touched.entrySet())
                s.getOverworld().setBlockState(e.getKey(), Registries.BLOCK.get(Identifier.of(e.getValue())).getDefaultState(), 3);
            http = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"),
                    Integer.getInteger("crimsonmc.port", 8766)), 16);
            httpWorkers = Executors.newFixedThreadPool(2, r -> { Thread t = new Thread(r, "crimsonmc-http"); t.setDaemon(true); return t; });
            http.setExecutor(httpWorkers);
            http.createContext("/api/", this::exchange);
            http.start();
            LOG.info("AUTHORITY_READY Minecraft 1.21.1, loopback HTTP port {}", http.getAddress().getPort());
        } catch (Exception e) { stop(); LOG.error("Authority disabled; initialization failed", e); }
    }

    private void stop() {
        if (http != null) { http.stop(0); http = null; }
        if (httpWorkers != null) { httpWorkers.shutdownNow(); httpWorkers = null; }
    }

    private void exchange(HttpExchange ex) throws IOException {
        int code = 200;
        JsonObject result;
        try {
            String method = ex.getRequestMethod(), path = ex.getRequestURI().getPath();
            if (!Set.of("GET", "POST").contains(method)) throw new BadRequest("method not supported");
            if (method.equals("POST") && !Objects.toString(ex.getRequestHeaders().getFirst("Content-Type"), "").startsWith("application/json"))
                throw new BadRequest("application/json required");
            byte[] bytes = ex.getRequestBody().readNBytes(65537);
            if (bytes.length > 65536) throw new BadRequest("body too large");
            JsonObject request = bytes.length == 0 ? new JsonObject() : JsonParser.parseString(new String(bytes, StandardCharsets.UTF_8)).getAsJsonObject();
            result = server.submit(() -> handle(method, path, request)).get(5, TimeUnit.SECONDS);
        } catch (Exception failure) {
            Throwable cause = failure instanceof ExecutionException ? failure.getCause() : failure;
            code = cause instanceof BadRequest || cause instanceof IllegalArgumentException ? 400 : 503;
            result = new JsonObject(); result.addProperty("error", Objects.toString(cause.getMessage(), cause.getClass().getSimpleName()));
        }
        byte[] response = JSON.toJson(result).getBytes(StandardCharsets.UTF_8);
        ex.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        ex.getResponseHeaders().set("Cache-Control", "no-store");
        ex.sendResponseHeaders(code, response.length);
        try (var out = ex.getResponseBody()) { out.write(response); }
    }

    private JsonObject handle(String method, String path, JsonObject req) {
        if (method.equals("GET") && path.equals("/api/state")) return state();
        if (method.equals("GET") && path.equals("/api/catalog")) return catalog();
        if (!method.equals("POST")) throw new BadRequest("unknown read endpoint");
        if (path.equals("/api/shutdown")) {
            // Stop from a separate thread after the HTTP response; normal MC shutdown saves chunks.
            Thread stopping = new Thread(() -> {
                try { Thread.sleep(500); } catch (InterruptedException ignored) { }
                server.stop(false);
            }, "crimsonmc-stop");
            stopping.setDaemon(true);
            stopping.start();
            JsonObject response = new JsonObject(); response.addProperty("stopping", true); return response;
        }
        if (!Set.of("/api/place", "/api/break", "/api/craft", "/api/grant", "/api/select",
                "/api/consume", "/api/place-selected").contains(path)) throw new BadRequest("unknown action");
        String operation = required(req, "operationId");
        if (operation.isBlank()) throw new BadRequest("operation ID is empty");
        if (operation.length() > 128) throw new BadRequest("operation ID too long");
        Receipt previous = receipts.get(operation);
        if (previous != null) {
            if (!previous.path().equals(path) || !previous.request().equals(req))
                throw new BadRequest("operation ID already belongs to a different request");
            return previous.result().deepCopy();
        }
        // Roll back both inventory and experiment block state on a failed mutation/save.
        JsonObject before = diskState();
        try {
            switch (path) {
                case "/api/place" -> place(req);
                case "/api/break" -> breakBlock(req);
                case "/api/craft" -> craft(req);
                case "/api/grant" -> grant(req);
                case "/api/select" -> selectedSlot = integer(req, "slot", 0, inventory.size() - 1);
                case "/api/consume" -> consume();
                case "/api/place-selected" -> placeSelected(req);
            }
            revision++;
            save();
        } catch (Exception error) {
            Set<BlockPos> changed = new HashSet<>(touched.keySet());
            load(before);
            changed.addAll(touched.keySet());
            for (BlockPos pos : changed) server.getOverworld().setBlockState(pos,
                    Registries.BLOCK.get(Identifier.of(touched.getOrDefault(pos, "minecraft:air"))).getDefaultState(), 3);
            throw error instanceof RuntimeException re ? re : new RuntimeException(error);
        }
        JsonObject result = state();
        result.addProperty("operationId", operation);
        receipts.put(operation, new Receipt(path, req.deepCopy(), result.deepCopy()));
        if (receipts.size() > 256) receipts.remove(receipts.keySet().iterator().next());
        return result;
    }

    private BlockPos position(JsonObject req) {
        int x = integer(req, "x", -16, 16), y = integer(req, "y", 64, 95), z = integer(req, "z", -16, 16);
        if (touched.size() >= 512 && !touched.containsKey(new BlockPos(x,y,z))) throw new BadRequest("prototype limit: 512 touched cells");
        return new BlockPos(x,y,z);
    }

    private void place(JsonObject req) {
        String id = required(req, "block");
        if (!BLOCK_IDS.contains(id)) throw new BadRequest("block not supported in this slice");
        int slot = findItem(id);
        if (slot < 0) throw new BadRequest("not enough material");
        placeFromSlot(req, slot, id);
    }

    private void placeSelected(JsonObject req) {
        ItemStack stack = inventory.getStack(selectedSlot);
        if (stack.isEmpty()) throw new BadRequest("selected slot is empty");
        String id = Registries.ITEM.getId(stack.getItem()).toString();
        if (!(stack.getItem() instanceof BlockItem) || !BLOCK_IDS.contains(id))
            throw new BadRequest("selected item placement is not supported in this slice");
        placeFromSlot(req, selectedSlot, id);
    }

    private void placeFromSlot(JsonObject req, int slot, String id) {
        BlockPos pos = position(req);
        var world = server.getOverworld();
        if (!world.getBlockState(pos).isAir()) throw new BadRequest("cell occupied");
        if (!world.setBlockState(pos, Registries.BLOCK.get(Identifier.of(id)).getDefaultState(), 3))
            throw new BadRequest("Minecraft refused placement");
        decrementSlot(slot);
        touched.put(pos, id);
    }

    private void grant(JsonObject req) {
        String id = required(req, "item");
        Identifier key = Identifier.tryParse(id);
        if (key == null || !Registries.ITEM.containsId(key)) throw new BadRequest("unknown Minecraft item");
        Item item = Registries.ITEM.get(key);
        if (item == Items.AIR) throw new BadRequest("air is not an inventory item");
        ItemStack stack = item.getDefaultStack();
        stack.setCount(stack.getMaxCount());
        if (!inventory.addStack(stack).isEmpty()) throw new BadRequest("a whole stack cannot fit inventory");
    }

    private void consume() {
        ItemStack stack = inventory.getStack(selectedSlot);
        if (stack.isEmpty()) throw new BadRequest("selected slot is empty");
        if (stack.getItem() instanceof BlockItem) throw new BadRequest("use placement to consume a block");
        // This is explicit inventory consumption, not a simulated bow, bucket or food use action.
        decrementSlot(selectedSlot);
    }

    private void decrementSlot(int slot) {
        ItemStack stack = inventory.getStack(slot);
        stack.decrement(1);
        if (stack.isEmpty()) inventory.setStack(slot, ItemStack.EMPTY);
        inventory.markDirty();
    }

    private JsonObject catalog() {
        JsonObject result = new JsonObject();
        result.addProperty("engine", "Minecraft Java 1.21.1");
        JsonArray items = new JsonArray();
        for (Item item : Registries.ITEM) if (item != Items.AIR) items.add(itemDescription(item.getDefaultStack()));
        result.add("items", items);
        return result;
    }

    private JsonObject itemDescription(ItemStack stack) {
        String id = Registries.ITEM.getId(stack.getItem()).toString();
        JsonObject item = new JsonObject();
        item.addProperty("id", id);
        item.addProperty("name", stack.getName().getString());
        item.addProperty("maxCount", stack.getMaxCount());
        item.addProperty("isBlock", stack.getItem() instanceof BlockItem);
        item.addProperty("placeSupported", stack.getItem() instanceof BlockItem && BLOCK_IDS.contains(id));
        return item;
    }

    private JsonObject slotDescription(int slot) {
        ItemStack stack = inventory.getStack(slot);
        JsonObject result = stack.isEmpty() ? new JsonObject() : itemDescription(stack);
        result.addProperty("slot", slot);
        result.addProperty("empty", stack.isEmpty());
        if (!stack.isEmpty()) result.addProperty("count", stack.getCount());
        return result;
    }

    private void breakBlock(JsonObject req) {
        BlockPos pos = position(req);
        if (!touched.containsKey(pos) || touched.get(pos).equals("minecraft:air")) throw new BadRequest("no prototype block here");
        var world = server.getOverworld();
        var state = world.getBlockState(pos);
        // Actual MC loot tables, with a diamond pickaxe for this first build slice.
        var drops = Block.getDroppedStacks(state, world, pos, world.getBlockEntity(pos), null,
                new ItemStack(Registries.ITEM.get(Identifier.of("minecraft:diamond_pickaxe"))));
        for (ItemStack drop : drops) if (!inventory.addStack(drop.copy()).isEmpty()) throw new BadRequest("inventory full");
        if (!world.setBlockState(pos, Blocks.AIR.getDefaultState(), 3)) throw new BadRequest("Minecraft refused removal");
        touched.put(pos, "minecraft:air");
    }

    private void craft(JsonObject req) {
        String id = required(req, "recipe");
        if (!RECIPE_IDS.contains(id)) throw new BadRequest("recipe not supported in this slice");
        var entry = server.getRecipeManager().get(Identifier.of(id)).orElseThrow(() -> new BadRequest("Minecraft recipe missing"));
        if (!(entry.value() instanceof CraftingRecipe recipe)) throw new BadRequest("not a crafting recipe");
        int width = recipe instanceof ShapedRecipe shaped ? shaped.getWidth() : 3;
        int height = recipe instanceof ShapedRecipe shaped ? shaped.getHeight() : 3;
        List<ItemStack> input = new ArrayList<>(Collections.nCopies(width * height, ItemStack.EMPTY));
        List<Ingredient> ingredients = recipe.getIngredients();
        if (ingredients.size() > input.size()) throw new BadRequest("invalid recipe dimensions");
        for (int n = 0; n < ingredients.size(); n++) {
            Ingredient ingredient = ingredients.get(n);
            if (ingredient.isEmpty()) continue;
            int slot = -1;
            for (int i = 0; i < inventory.size(); i++) {
                if (!inventory.getStack(i).isEmpty() && ingredient.test(inventory.getStack(i))) { slot = i; break; }
            }
            if (slot < 0) throw new BadRequest("not enough material for " + id);
            input.set(n, inventory.getStack(slot).copyWithCount(1));
            inventory.getStack(slot).decrement(1);
        }
        CraftingRecipeInput grid = CraftingRecipeInput.create(width, height, input);
        if (!recipe.matches(grid, server.getOverworld())) throw new BadRequest("Minecraft rejected the crafting grid");
        ItemStack output = recipe.craft(grid, server.getRegistryManager());
        if (output.isEmpty() || !inventory.addStack(output.copy()).isEmpty()) throw new BadRequest("output cannot fit inventory");
        for (ItemStack remainder : recipe.getRemainder(grid))
            if (!remainder.isEmpty() && !inventory.addStack(remainder.copy()).isEmpty()) throw new BadRequest("remainder cannot fit inventory");
    }

    private int findItem(String id) {
        for (int i = 0; i < inventory.size(); i++) {
            ItemStack stack = inventory.getStack(i);
            if (!stack.isEmpty() && Registries.ITEM.getId(stack.getItem()).toString().equals(id)) return i;
        }
        return -1;
    }

    private JsonObject state() {
        JsonObject result = new JsonObject();
        result.addProperty("engine", "Minecraft Java 1.21.1");
        result.addProperty("revision", revision);
        result.addProperty("schemaVersion", SCHEMA_VERSION);
        result.addProperty("selectedSlot", selectedSlot);
        JsonArray slots = new JsonArray();
        for (int i = 0; i < inventory.size(); i++) slots.add(slotDescription(i));
        result.add("slots", slots);
        result.add("selectedItem", inventory.getStack(selectedSlot).isEmpty() ? JsonNull.INSTANCE : slotDescription(selectedSlot));
        JsonObject counts = new JsonObject();
        for (int i = 0; i < inventory.size(); i++) {
            ItemStack stack = inventory.getStack(i); if (stack.isEmpty()) continue;
            String id = Registries.ITEM.getId(stack.getItem()).toString();
            counts.addProperty(id, stack.getCount() + (counts.has(id) ? counts.get(id).getAsInt() : 0));
        }
        result.add("inventory", counts);
        JsonArray blocks = new JsonArray();
        for (var entry : touched.entrySet()) {
            if (entry.getValue().equals("minecraft:air")) continue;
            JsonObject b = new JsonObject(); b.addProperty("x", entry.getKey().getX()); b.addProperty("y", entry.getKey().getY());
            b.addProperty("z", entry.getKey().getZ()); b.addProperty("block", entry.getValue()); blocks.add(b);
        }
        result.add("blocks", blocks);
        return result;
    }

    private JsonObject diskState() {
        JsonObject result = new JsonObject(); result.addProperty("revision", revision);
        result.addProperty("schemaVersion", SCHEMA_VERSION);
        result.addProperty("selectedSlot", selectedSlot);
        JsonArray slots = new JsonArray();
        var ops = RegistryOps.of(JsonOps.INSTANCE, server.getRegistryManager());
        for (int i = 0; i < inventory.size(); i++) slots.add(inventory.getStack(i).isEmpty() ? JsonNull.INSTANCE :
                ItemStack.CODEC.encodeStart(ops, inventory.getStack(i)).getOrThrow());
        result.add("slots", slots);
        JsonArray cells = new JsonArray();
        touched.forEach((pos,id) -> { JsonObject b = new JsonObject(); b.addProperty("x",pos.getX()); b.addProperty("y",pos.getY());
            b.addProperty("z",pos.getZ()); b.addProperty("block",id); cells.add(b); });
        result.add("touched", cells);
        return result;
    }

    private void load(JsonObject data) {
        int version = data.has("schemaVersion") ? integer(data, "schemaVersion", 0, Integer.MAX_VALUE) : 0;
        if (version > SCHEMA_VERSION) throw new BadRequest("unsupported future inventory schema " + version);
        int selection = version == 0 ? 0 : integer(data, "selectedSlot", 0, inventory.size() - 1);
        long savedRevision = data.get("revision").getAsBigDecimal().longValueExact();
        if (savedRevision < 0) throw new BadRequest("invalid saved revision");
        var ops = RegistryOps.of(JsonOps.INSTANCE, server.getRegistryManager());
        JsonArray slots = data.getAsJsonArray("slots");
        if (slots == null || slots.size() != inventory.size()) throw new BadRequest("saved inventory must contain exactly 36 slots");
        List<ItemStack> stacks = new ArrayList<>();
        for (JsonElement value : slots) {
            ItemStack stack = value.isJsonNull() ? ItemStack.EMPTY : ItemStack.CODEC.parse(ops, value).getOrThrow();
            if (!value.isJsonNull() && (stack.isEmpty() || stack.getCount() < 1 || stack.getCount() > stack.getMaxCount()))
                throw new BadRequest("saved inventory stack exceeds its Minecraft maximum");
            stacks.add(stack);
        }
        Map<BlockPos, String> cells = new LinkedHashMap<>();
        JsonArray savedCells = data.getAsJsonArray("touched");
        if (savedCells == null || savedCells.size() > 512) throw new BadRequest("invalid saved touched cells");
        for (JsonElement cell : savedCells) {
            JsonObject b = cell.getAsJsonObject();
            BlockPos pos = new BlockPos(integer(b, "x", -16, 16), integer(b, "y", 64, 95), integer(b, "z", -16, 16));
            String id = required(b, "block");
            if (!id.equals("minecraft:air") && !BLOCK_IDS.contains(id)) throw new BadRequest("unknown saved prototype block");
            if (cells.put(pos, id) != null) throw new BadRequest("duplicate saved cell");
        }
        // Parse and validate the complete snapshot before replacing any live state.
        inventory.clear(); touched.clear();
        for (int i = 0; i < stacks.size(); i++) inventory.setStack(i, stacks.get(i));
        touched.putAll(cells);
        revision = savedRevision;
        selectedSlot = selection;
    }

    private void save() throws IOException {
        Path temp=stateFile.resolveSibling(stateFile.getFileName()+".tmp");
        Files.writeString(temp, JSON.toJson(diskState()), StandardCharsets.UTF_8);
        try { Files.move(temp,stateFile,StandardCopyOption.REPLACE_EXISTING,StandardCopyOption.ATOMIC_MOVE); }
        catch (AtomicMoveNotSupportedException ignored) { Files.move(temp,stateFile,StandardCopyOption.REPLACE_EXISTING); }
    }

    private static String required(JsonObject req, String key) {
        if (!req.has(key) || !req.get(key).isJsonPrimitive() || !req.getAsJsonPrimitive(key).isString()) throw new BadRequest("missing string " + key);
        return req.get(key).getAsString();
    }
    private static int integer(JsonObject req, String key, int min, int max) {
        if (!req.has(key) || !req.get(key).isJsonPrimitive() || !req.getAsJsonPrimitive(key).isNumber())
            throw new BadRequest("missing integer " + key);
        try {
            int value = req.get(key).getAsBigDecimal().intValueExact();
            if (value < min || value > max) throw new BadRequest(key + " outside allowed range");
            return value;
        } catch (ArithmeticException error) { throw new BadRequest("invalid integer " + key); }
    }
    private static final class BadRequest extends RuntimeException { BadRequest(String message) { super(message); } }
}
