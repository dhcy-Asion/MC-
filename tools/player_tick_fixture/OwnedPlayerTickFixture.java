package local.crimsonmc.fixture;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.authlib.GameProfile;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Queue;
import java.util.UUID;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.block.Block;
import net.minecraft.block.Blocks;
import net.minecraft.entity.EntityPose;
import net.minecraft.entity.EquipmentSlot;
import net.minecraft.network.ClientConnection;
import net.minecraft.network.NetworkSide;
import net.minecraft.network.packet.c2s.common.SyncedClientOptions;
import net.minecraft.registry.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.filter.TextStream;
import net.minecraft.server.network.ConnectedClientData;
import net.minecraft.server.network.ServerPlayNetworkHandler;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.util.Arm;
import net.minecraft.util.Hand;
import net.minecraft.util.WorldSavePath;
import net.minecraft.util.math.BlockPos;

/** Full official world.tickEntity then playerTick once per actual server tick on an unregistered player.
 * This does not run the registered/connected player's complete lifecycle.
 */
public final class OwnedPlayerTickFixture implements ModInitializer {
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private static final String[] PROFILES = {"standing_main", "standing_off", "crouching_main", "crouching_off"};
    private static final UUID PROFILE_UUID = UUID.fromString("f7b21c8a-37e2-491d-90ed-4b85c842b5e0");
    private final JsonObject report = new JsonObject();
    private final JsonArray checks = new JsonArray(), warmup = new JsonArray(), frames = new JsonArray();
    private ServerPlayerEntity player;
    private ServerWorld world;
    private ClientConnection connection;
    private ServerPlayNetworkHandler handler;
    private Field queueField;
    private Path output;
    private boolean initialized, finished, settled;
    private int priorServerTick = -1, calls, worldCalls, frame, stableGroundTicks;

    @Override public void onInitialize() {
        ServerLifecycleEvents.SERVER_STARTED.register(this::start);
        ServerTickEvents.START_SERVER_TICK.register(this::step);
    }

    private static void require(boolean condition, String reason) {
        if (!condition) throw new IllegalStateException(reason);
    }

    private void checked(boolean condition, String name) {
        require(condition, name);
        JsonObject row = new JsonObject(); row.addProperty("name", name); row.addProperty("passed", true);
        checks.add(row);
    }

    private static JsonObject f(float value) {
        require(Float.isFinite(value), "Non-finite observed float");
        JsonObject result = new JsonObject(); result.addProperty("value", value);
        result.addProperty("rawBits", Float.floatToRawIntBits(value)); return result;
    }

    private static JsonObject vector(double x, double y, double z) {
        require(Double.isFinite(x) && Double.isFinite(y) && Double.isFinite(z), "Non-finite observed vector");
        JsonObject result = new JsonObject(); result.addProperty("x", x); result.addProperty("y", y); result.addProperty("z", z);
        result.addProperty("xRawBitsHex", Long.toHexString(Double.doubleToRawLongBits(x)));
        result.addProperty("yRawBitsHex", Long.toHexString(Double.doubleToRawLongBits(y)));
        result.addProperty("zRawBitsHex", Long.toHexString(Double.doubleToRawLongBits(z))); return result;
    }

    private int queuedTasks() throws IllegalAccessException {
        Object value = queueField.get(connection); // Read only: no reflective/private field writes.
        require(value instanceof Queue<?>, "Fixed queuedTasks field is not a Queue");
        return ((Queue<?>) value).size();
    }

    private void detached(MinecraftServer server) {
        require(server.isOnThread(), "Observation must run on the owned server thread");
        require(player.getClass() == ServerPlayerEntity.class && player.getWorld() == world, "Normal exact player/world identity changed");
        require(player.networkHandler == handler, "Normal handler assignment changed");
        require(!connection.isOpen() && connection.getPacketListener() == null, "Fixture acquired a channel/listener");
        require(server.getPlayerManager().getPlayerList().isEmpty(), "Fixture must not register a player");
        require(world.getEntityById(player.getId()) == null, "Fixture must not spawn/index the player");
        require(connection.getSide() == NetworkSide.SERVERBOUND, "Connection side changed");
    }

    private JsonObject state() throws IllegalAccessException {
        JsonObject s = new JsonObject();
        s.addProperty("age", player.age); s.addProperty("mainArm", player.getMainArm().name());
        s.addProperty("preferredHand", String.valueOf(player.preferredHand));
        s.addProperty("activeHand", player.getActiveHand().name());
        s.addProperty("handSwinging", player.handSwinging); s.addProperty("handSwingTicks", player.handSwingTicks);
        s.add("lastHandSwingProgress", f(player.lastHandSwingProgress)); s.add("handSwingProgress", f(player.handSwingProgress));
        s.addProperty("pose", player.getPose().name()); s.addProperty("isSneaking", player.isSneaking());
        s.addProperty("isInSneakingPose", player.isInSneakingPose()); s.addProperty("onGround", player.isOnGround());
        s.addProperty("mainHandEmpty", player.getMainHandStack().isEmpty()); s.addProperty("offHandEmpty", player.getOffHandStack().isEmpty());
        s.addProperty("chestEmpty", player.getEquippedStack(EquipmentSlot.CHEST).isEmpty());
        s.addProperty("usingItem", player.isUsingItem()); s.addProperty("baby", player.isBaby()); s.addProperty("riding", player.hasVehicle());
        s.addProperty("fallFlyingTicks", player.getFallFlyingTicks()); s.addProperty("fallFlying", player.isFallFlying());
        s.addProperty("inSwimmingPose", player.isInSwimmingPose()); s.addProperty("swimming", player.isSwimming());
        s.addProperty("alive", player.isAlive()); s.addProperty("spectator", player.isSpectator());
        s.addProperty("statusEffectsEmpty", player.getStatusEffects().isEmpty()); s.addProperty("sleeping", player.isSleeping());
        s.addProperty("playerName", player.getName().getString()); s.addProperty("hasCustomName", player.hasCustomName());
        s.add("scale", f(player.getScale())); s.add("bodyYaw", f(player.bodyYaw)); s.add("prevBodyYaw", f(player.prevBodyYaw));
        s.add("headYaw", f(player.headYaw)); s.add("prevHeadYaw", f(player.prevHeadYaw));
        s.add("yaw", f(player.getYaw())); s.add("prevYaw", f(player.prevYaw));
        s.add("pitch", f(player.getPitch())); s.add("prevPitch", f(player.prevPitch));
        s.add("position", vector(player.getX(), player.getY(), player.getZ()));
        s.add("previousPosition", vector(player.prevX, player.prevY, player.prevZ));
        var velocity = player.getVelocity(); s.add("velocity", vector(velocity.x, velocity.y, velocity.z));
        s.addProperty("queuedConnectionTasks", queuedTasks()); s.add("health", f(player.getHealth()));
        JsonArray interpolation = new JsonArray();
        for (float delta : new float[]{0.0F, 0.5F, 1.0F}) {
            JsonObject point = new JsonObject(); point.add("tickDelta", f(delta));
            point.add("handSwingProgress", f(player.getHandSwingProgress(delta)));
            point.add("leaningPitch", f(player.getLeaningPitch(delta)));
            point.add("limbSpeed", f(player.limbAnimator.getSpeed(delta)));
            point.add("limbPosition", f(player.limbAnimator.getPos(delta))); interpolation.add(point);
        }
        s.add("interpolation", interpolation); return s;
    }

    private void start(MinecraftServer server) {
        require(!initialized, "Fixture initialization may execute once"); initialized = true;
        report.addProperty("schemaVersion", 1); report.addProperty("runTicket", System.getProperty("crimsonmc.playerTickFixtureTicket"));
        report.add("checks", checks); report.add("warmup", warmup); report.add("frames", frames);
        JsonObject scope = new JsonObject();
        scope.addProperty("fixtureConnectionNormallyConstructed", false); scope.addProperty("fixtureNetworkHandlerNormallyConstructed", false);
        for (String name : new String[]{"fixtureClientConnected", "registeredWithPlayerManager", "spawnedInWorld",
                "fullServerPlayerTickCalled", "worldTickEntityCalled", "worldAgeLifecycleVerified", "fullConnectedLifecycleVerified", "twentyHzLifecycleVerified", "privateFieldsWritten",
                "attackOrDamageCalled", "nativeApplied", "clientModelOrGameRendererVerified", "animationSystemComplete"}) scope.addProperty(name, false);
        scope.addProperty("privateQueueFieldReadOnly", true); scope.addProperty("ownedWorldFloorBlocksWritten", false);
        report.add("scope", scope);
        report.addProperty("tickEntryPoint", "ServerWorld.tickEntity(player) then ServerPlayerEntity.playerTick()");
        report.addProperty("scheduler", "Fabric START_SERVER_TICK; exactly one call to each full official entry in fixed world-before-player order per observed distinct server tick");
        report.addProperty("normalLifecycleMissing", "Player is absent from world/entity and connection lists; ServerPlayNetworkHandler.tick and connected/registered scheduling are not requested");
        try {
            Path owned = Path.of(System.getProperty("crimsonmc.playerTickFixtureRuntime")).toRealPath();
            output = Path.of(System.getProperty("crimsonmc.playerTickFixtureReport")).toAbsolutePath().normalize();
            require(output.getParent().equals(owned) && !Files.exists(output), "Fresh report must stay in the owned runtime");
            checked(server.isOnThread(), "normal-owned-server-thread");
            checked(server.getSavePath(WorldSavePath.ROOT).toAbsolutePath().normalize().startsWith(owned), "all-world-side-effects-stay-owned");
            world = server.getOverworld(); require(world != null, "Real overworld required");
            checked(server.getPlayerManager().getPlayerList().isEmpty(), "no-existing-or-connected-player");
            GameProfile profile = new GameProfile(PROFILE_UUID, "CMCTickContext");
            SyncedClientOptions options = SyncedClientOptions.createDefault();
            player = new ServerPlayerEntity(server, world, profile, options);
            require(player.networkHandler == null, "Normal player initially has no handler");
            require(player.getTextStream() == TextStream.UNFILTERED, "Fixture permits only official unfiltered/no external text service");
            connection = new ClientConnection(NetworkSide.SERVERBOUND);
            scope.addProperty("fixtureConnectionNormallyConstructed", true);
            handler = new ServerPlayNetworkHandler(server, connection, player, new ConnectedClientData(profile, 0, options, false));
            scope.addProperty("fixtureNetworkHandlerNormallyConstructed", true);
            queueField = ClientConnection.class.getDeclaredField("queuedTasks"); queueField.setAccessible(true);
            detached(server); checked(player.networkHandler == handler, "official-handler-constructor-assignment");
            checked(queuedTasks() == 0, "constructor-does-not-queue-or-send-packets");
            checked(player.getMainArm() == Arm.RIGHT, "actual-default-right-main-arm");
            report.addProperty("worldPath", server.getSavePath(WorldSavePath.ROOT).toString()); report.addProperty("playerEntityId", player.getId());
            report.add("constructedState", state());
            var origin = ServerPlayerEntity.class.getProtectionDomain().getCodeSource();
            report.addProperty("serverPlayerClassCodeSource", origin == null ? "unavailable" : origin.getLocation().toExternalForm());
            JsonArray floor = new JsonArray();
            for (int x = 0; x < 3; x++) for (int z = 0; z < 3; z++) {
                BlockPos pos = new BlockPos(x, 0, z); JsonObject block = new JsonObject();
                block.addProperty("x", x); block.addProperty("y", 0); block.addProperty("z", z);
                block.addProperty("beforeBlock", Registries.BLOCK.getId(world.getBlockState(pos).getBlock()).toString());
                block.addProperty("setBlockStateReturned", world.setBlockState(pos, Blocks.STONE.getDefaultState(), Block.NOTIFY_ALL));
                require(world.getBlockState(pos).isOf(Blocks.STONE), "Owned stone floor placement failed");
                block.addProperty("afterBlock", "minecraft:stone"); floor.add(block);
            }
            report.add("ownedFloor", floor);
            scope.addProperty("ownedWorldFloorBlocksWritten", true);
            player.refreshPositionAndAngles(1.5, 3.0, 1.5, 0.0F, 0.0F);
            report.add("placedState", state());
        } catch (Throwable failure) { publishFailure(failure); }
    }

    private void step(MinecraftServer server) {
        if (!initialized || finished) return;
        try {
            detached(server);
            int serverTick = server.getTicks();
            require(priorServerTick < 0 || serverTick == priorServerTick + 1, "Server tick repeated or skipped");
            priorServerTick = serverTick;
            String profileName = settled ? PROFILES[frame / 8] : "natural_floor_warmup";
            if (settled && frame % 8 == 0) {
                require(!player.handSwinging && Float.floatToRawIntBits(player.handSwingProgress) == 0, "Prior official swing did not return to zero");
                player.setSneaking(frame / 8 >= 2);
                player.swingHand(frame / 8 % 2 == 0 ? Hand.MAIN_HAND : Hand.OFF_HAND);
            }
            int beforeAge = player.age;
            float beforeProgress = player.handSwingProgress;
            double beforeX = player.getX(), beforeY = player.getY(), beforeZ = player.getZ();
            JsonObject observation = new JsonObject(); observation.addProperty("serverTick", serverTick);
            observation.addProperty("monotonicNanos", Long.toString(System.nanoTime()));
            observation.addProperty("profile", profileName); observation.addProperty("profileFrame", settled ? frame % 8 : warmup.size());
            observation.addProperty("entryPointOrder", "ServerWorld.tickEntity(player) -> ServerPlayerEntity.playerTick()");
            observation.add("before", state());
            world.tickEntity(player); // Full official entry performs resetPosition, age increment, and ServerPlayer.tick.
            worldCalls++;
            detached(server); observation.add("afterWorldTickEntity", state());
            require(player.age == beforeAge + 1, "Official world tick did not advance age once");
            require(Double.doubleToRawLongBits(player.prevX) == Double.doubleToRawLongBits(beforeX)
                    && Double.doubleToRawLongBits(player.prevY) == Double.doubleToRawLongBits(beforeY)
                    && Double.doubleToRawLongBits(player.prevZ) == Double.doubleToRawLongBits(beforeZ), "Official resetPosition previous position differs");
            report.getAsJsonObject("scope").addProperty("worldTickEntityCalled", true);
            report.getAsJsonObject("scope").addProperty("fullServerPlayerTickCalled", true);
            player.playerTick(); // Full official entity/player update, never hand-written tick fragments.
            calls++;
            detached(server); observation.add("after", state());
            require(player.age == beforeAge + 1, "Official playerTick unexpectedly changed the world-managed age");
            require(Float.floatToRawIntBits(player.lastHandSwingProgress) == Float.floatToRawIntBits(beforeProgress), "Official previous swing copy differs");
            if (!settled) {
                warmup.add(observation);
                var velocity = player.getVelocity();
                boolean stableGroundPosition = player.isOnGround() && Math.abs(player.getY() - 1.0) < 1.0e-8
                        && Math.abs(player.getX() - beforeX) < 1.0e-12 && Math.abs(player.getY() - beforeY) < 1.0e-12
                        && Math.abs(player.getZ() - beforeZ) < 1.0e-12 && velocity.x == 0.0 && velocity.z == 0.0;
                stableGroundTicks = stableGroundPosition ? stableGroundTicks + 1 : 0;
                // Official travel may retain its downward gravity velocity while grounded.
                // Settle means three observed stationary/on-ground ticks, never forcing velocity to zero.
                settled = stableGroundTicks >= 3;
                require(settled || warmup.size() < 40, "Natural floor settling did not complete within 40 real ticks");
                if (settled) { report.add("settledState", state()); checked(true, "official-physics-landed-and-settled-on-owned-floor"); }
                return;
            }
            boolean requestedCrouch = frame / 8 >= 2;
            Hand requestedHand = frame / 8 % 2 == 0 ? Hand.MAIN_HAND : Hand.OFF_HAND;
            require(player.getMainArm() == Arm.RIGHT && player.preferredHand == requestedHand, "Actual hand contract changed");
            require(player.isSneaking() == requestedCrouch && player.isInSneakingPose() == requestedCrouch
                    && player.getPose() == (requestedCrouch ? EntityPose.CROUCHING : EntityPose.STANDING), "Official pose update did not match requested sneaking");
            require(player.isOnGround() && Math.abs(player.getY() - 1.0) < 1.0e-8, "Sampling player left the observed floor");
            frames.add(observation); frame++;
            if (frame % 8 == 0) require(!player.handSwinging && Float.floatToRawIntBits(player.handSwingProgress) == 0, "Eight complete ticks did not finish the official swing");
            if (frame == 32) {
                checked(frames.size() == 32 && calls == warmup.size() + 32 && worldCalls == calls, "all-thirty-two-frames-have-one-call-to-each-complete-entry");
                checked(queuedTasks() > 0, "official-sync-packets-queue-on-unconnected-transport");
                report.addProperty("playerTickCalls", calls); report.addProperty("warmupPlayerTickCalls", warmup.size());
                report.addProperty("samplePlayerTickCalls", frame); report.addProperty("oncePerDistinctServerTickObserved", true);
                report.addProperty("worldTickEntityCalls", worldCalls);
                report.getAsJsonObject("scope").addProperty("worldAgeLifecycleVerified", true);
                report.addProperty("completePlayerTickMethodExecuted", true); report.add("terminalState", state());
                report.addProperty("result", "pass"); publish();
            }
        } catch (Throwable failure) { publishFailure(failure); }
    }

    private void publishFailure(Throwable failure) {
        report.addProperty("result", "failure"); report.addProperty("failureClass", failure.getClass().getName());
        report.addProperty("failureMessage", String.valueOf(failure.getMessage()));
        report.addProperty("playerTickCallsBeforeFailure", calls); report.addProperty("completePlayerTickMethodExecuted", false);
        report.addProperty("worldTickEntityCallsBeforeFailure", worldCalls);
        JsonArray trace = new JsonArray();
        for (StackTraceElement element : failure.getStackTrace()) {
            trace.add(element.toString()); if (trace.size() == 20) break;
        }
        report.add("failureStack", trace); publish();
    }

    private void publish() {
        finished = true;
        try {
            require(output != null, "Safe report path unavailable");
            Files.writeString(output, JSON.toJson(report) + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println("MC_PLAYER_TICK_FIXTURE_RESULT " + report.get("result").getAsString());
        } catch (Exception failure) { throw new IllegalStateException("Fixture report publication failed", failure); }
    }
}
