package local.crimsonmc.fixture;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.mojang.authlib.GameProfile;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.UUID;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.minecraft.entity.EntityPose;
import net.minecraft.network.packet.c2s.common.SyncedClientOptions;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.network.ServerPlayerEntity;
import net.minecraft.server.world.ServerWorld;
import net.minecraft.util.Arm;
import net.minecraft.util.Hand;
import net.minecraft.util.WorldSavePath;

/** Unregistered, unspawned player in the owned test world. No full player tick. */
public final class OwnedPlayerContextFixture implements ModInitializer {
    private static final UUID PROFILE_UUID = UUID.fromString("05ac0557-3792-4989-819b-d598963e3928");
    private static final String PROFILE_NAME = "CMCTestContext";
    private static final Gson JSON = new GsonBuilder().setPrettyPrinting().create();
    private boolean executed;

    /** Exposes only the existing protected hand-swing step, with no field writes. */
    private static final class FixturePlayer extends ServerPlayerEntity {
        FixturePlayer(MinecraftServer server, ServerWorld world) {
            super(server, world, new GameProfile(PROFILE_UUID, PROFILE_NAME), SyncedClientOptions.createDefault());
        }
        public void fixtureStepHandSwing() { super.tickHandSwing(); }
    }

    @Override public void onInitialize() {
        ServerLifecycleEvents.SERVER_STARTED.register(this::run);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new IllegalStateException(message);
    }

    private static void checked(JsonArray checks, boolean condition, String name) {
        require(condition, name);
        JsonObject row = new JsonObject(); row.addProperty("name", name); row.addProperty("passed", true);
        checks.add(row);
    }

    private void run(MinecraftServer server) {
        require(!executed, "Fixture callback may execute only once"); executed = true;
        JsonObject report = new JsonObject(); JsonArray checks = new JsonArray(); report.add("checks", checks);
        report.addProperty("schemaVersion", 1); report.addProperty("runTicket", System.getProperty("crimsonmc.playerFixtureTicket"));
        report.addProperty("profileUuid", PROFILE_UUID.toString()); report.addProperty("profileName", PROFILE_NAME);
        JsonObject scope = new JsonObject();
        scope.addProperty("fixtureClientCreated", false); scope.addProperty("fixtureNetworkHandlerCreated", false);
        scope.addProperty("registeredWithPlayerManager", false); scope.addProperty("spawnedInWorld", false);
        scope.addProperty("fullEntityOrPlayerTickCalled", false); scope.addProperty("twentyHzLifecycleVerified", false);
        scope.addProperty("privateFieldsWritten", false); scope.addProperty("nativeApplied", false);
        scope.addProperty("attackOrDamageCalled", false); scope.addProperty("clientModelOrGameRendererVerified", false);
        scope.addProperty("normalIsolatedServerListenersExist", true); scope.addProperty("fixtureNetworkClientConnected", false);
        report.add("scope", scope);
        Path output = null;
        try {
            Path owned = Path.of(System.getProperty("crimsonmc.playerFixtureRuntime")).toRealPath();
            output = Path.of(System.getProperty("crimsonmc.playerFixtureReport")).toAbsolutePath().normalize();
            require(output.getParent().equals(owned) && !Files.exists(output), "Report must be a fresh owned-runtime file");
            Path worldPath = server.getSavePath(WorldSavePath.ROOT).toAbsolutePath().normalize();
            checked(checks, worldPath.startsWith(owned), "stat-and-advancement-construction-is-confined-to-owned-world");
            checked(checks, server.isOnThread(), "server-started-callback-is-on-server-thread");
            ServerWorld world = server.getOverworld();
            checked(checks, world != null, "real-overworld-is-available");
            int playersBefore = server.getPlayerManager().getPlayerList().size();
            checked(checks, playersBefore == 0, "no-connected-test-or-existing-player");
            FixturePlayer player = new FixturePlayer(server, world);
            var playerCodeSource = ServerPlayerEntity.class.getProtectionDomain().getCodeSource();
            report.addProperty("serverPlayerClassCodeSource", playerCodeSource == null ? "unavailable" : playerCodeSource.getLocation().toExternalForm());
            checked(checks, player.getWorld() == world, "player-retains-real-overworld");
            checked(checks, player.networkHandler == null, "unconnected-player-has-no-network-handler");
            checked(checks, !server.getPlayerManager().getPlayerList().contains(player), "player-manager-registration-not-performed");
            checked(checks, world.getEntityById(player.getId()) == null, "player-not-spawned-or-indexed-in-world");
            report.addProperty("worldPath", worldPath.toString()); report.addProperty("playerEntityId", player.getId());
            Arm initialArm = player.getMainArm(); EntityPose initialPose = player.getPose(); boolean initialSneaking = player.isSneaking();
            boolean initialSneakingPose = player.isInSneakingPose();
            JsonObject original = new JsonObject(); original.addProperty("mainArm", initialArm.name());
            original.addProperty("pose", initialPose.name()); original.addProperty("sneaking", initialSneaking);
            original.addProperty("inSneakingPose", initialSneakingPose); report.add("initialState", original);
            try {
                player.setMainArm(Arm.LEFT); checked(checks, player.getMainArm() == Arm.LEFT, "official-left-main-arm-roundtrip");
                player.setMainArm(Arm.RIGHT); checked(checks, player.getMainArm() == Arm.RIGHT, "official-right-main-arm-roundtrip");
                player.setSneaking(true); checked(checks, player.isSneaking(), "official-sneaking-roundtrip");
                player.setPose(EntityPose.CROUCHING); checked(checks, player.getPose() == EntityPose.CROUCHING, "official-crouching-pose-roundtrip");
                checked(checks, player.isInSneakingPose(), "official-crouching-sneaking-pose-getter");
            } finally {
                player.setMainArm(initialArm); player.setSneaking(initialSneaking); player.setPose(initialPose);
            }
            checked(checks, player.getMainArm() == initialArm && player.isSneaking() == initialSneaking && player.getPose() == initialPose
                    && player.isInSneakingPose() == initialSneakingPose,
                    "original-arm-sneaking-pose-restored-by-official-setters");
            checked(checks, player.getStatusEffects().isEmpty(), "swing-fixture-has-no-status-effects");
            JsonObject swing = new JsonObject(); swing.addProperty("overload", "LivingEntity.swingHand(Hand.MAIN_HAND, false)");
            swing.addProperty("serverPlayerSingleArgumentOverrideUsed", false);
            swing.addProperty("protectedMethod", "LivingEntity.tickHandSwing"); swing.addProperty("completeTickCalled", false);
            swing.addProperty("broadcastBytecodeNullTrackerReturns", true);
            JsonArray progress = new JsonArray(); progress.add(player.getHandSwingProgress(1.0F));
            player.swingHand(Hand.MAIN_HAND, false);
            boolean positive = false;
            for (int step = 0; step < 8; step++) {
                player.fixtureStepHandSwing(); float value = player.getHandSwingProgress(1.0F);
                checked(checks, Float.isFinite(value) && value >= 0.0F && value < 1.0F, "native-protected-swing-step-range-" + step);
                positive |= value > 0.0F; progress.add(value);
            }
            checked(checks, positive && player.getHandSwingProgress(1.0F) == 0.0F, "official-single-swing-progress-advances-and-returns-to-zero");
            swing.addProperty("protectedStepCalls", 8); swing.add("progressAtPartialTickOne", progress); report.add("swing", swing);
            checked(checks, player.networkHandler == null && world.getEntityById(player.getId()) == null
                    && server.getPlayerManager().getPlayerList().size() == playersBefore,
                    "fixture-remains-unconnected-unregistered-unspawned");
            report.addProperty("result", "pass");
        } catch (Throwable failure) {
            report.addProperty("result", "failure"); report.addProperty("failureClass", failure.getClass().getName());
            report.addProperty("failureMessage", String.valueOf(failure.getMessage()));
        }
        try {
            require(output != null, "No safe owned report path was established");
            Files.writeString(output, JSON.toJson(report) + "\n", StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            System.out.println("MC_PLAYER_CONTEXT_FIXTURE_RESULT " + report.get("result").getAsString());
        } catch (Exception failure) {
            throw new IllegalStateException("Fixture report publication failed", failure);
        }
    }
}
