package local.crimsonmc.assets;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Replays captured real ServerPlayer state through the fixed official model.
 * Model fixture remains a normal null-World ArmorStand in STANDING Pose. Only
 * six base joints are exported. The actual Player renderer is not executed.
 * No server, entity tick, private entity-state write or native call is made.
 */
public final class StevePlayerPoseDump {
    private static final String[] PARTS = {"head", "body", "right_arm", "left_arm", "right_leg", "left_leg"};
    private static final String[] FIELDS = {"b", "c", "d", "e", "f", "g", "h", "i", "j"};
    private static final String[] NAMES = {"pivotX", "pivotY", "pivotZ", "pitch", "yaw", "roll", "scaleX", "scaleY", "scaleZ"};

    private static Object read(Object object, String owner, String name) throws Exception {
        Field field = Class.forName(owner).getDeclaredField(name);
        field.setAccessible(true);
        return field.get(object);
    }

    private static void set(Object object, String owner, String name, Object value) throws Exception {
        Field field = Class.forName(owner).getDeclaredField(name);
        field.setAccessible(true);
        field.set(object, value);
    }

    private static Object call(Object object, String name) throws Exception {
        return object.getClass().getMethod(name).invoke(object);
    }

    private static String enumName(Object object) {
        if (!(object instanceof Enum<?> value)) throw new IllegalStateException("Official enum absent");
        return value.name();
    }

    private static String quote(String text) {
        return '"' + text.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "\\r") + '"';
    }

    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String text) return quote(text);
        if (value instanceof Float number && !Float.isFinite(number)) throw new IllegalStateException("Nonfinite input");
        if (value instanceof Double number && !Double.isFinite(number)) throw new IllegalStateException("Nonfinite input");
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?, ?> map) {
            List<String> entries = new ArrayList<>();
            for (Map.Entry<?, ?> entry : map.entrySet()) entries.add(quote((String)entry.getKey()) + ':' + json(entry.getValue()));
            return '{' + String.join(",", entries) + '}';
        }
        if (value instanceof Collection<?> list) {
            List<String> entries = new ArrayList<>();
            for (Object item : list) entries.add(json(item));
            return '[' + String.join(",", entries) + ']';
        }
        throw new IllegalStateException("Unadmitted JSON value");
    }

    private static Object newEntity() throws Exception {
        Object entity = Class.forName("ciw").getConstructor(Class.forName("bsx"), Class.forName("dcw"))
                .newInstance(Class.forName("bsx").getField("d").get(null), null);
        if (!entity.getClass().getName().equals("ciw") || read(entity, "bsr", "r") != null)
            throw new IllegalStateException("Expected a normal exact ArmorStandEntity with null World");
        return entity;
    }

    private static Map<String, Object> entityState(Object entity) throws Exception {
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("worldNull", read(entity, "bsr", "r") == null);
        state.put("pose", enumName(call(entity, "at")));
        state.put("isSneaking", call(entity, "bW"));
        state.put("isInSneakingPose", call(entity, "cb"));
        state.put("fallFlyingTicks", call(entity, "fB"));
        state.put("swimmingPose", call(entity, "ce"));
        state.put("usingItem", call(entity, "fr"));
        state.put("mainArm", enumName(call(entity, "fq")));
        state.put("activeHand", enumName(call(entity, "fs")));
        state.put("preferredHand", enumName(read(entity, "btn", "aK")));
        state.put("velocityZero", call(entity, "dr").equals(Class.forName("exc").getField("b").get(null)));
        state.put("mainHandEmpty", call(call(entity, "eT"), "e"));
        state.put("offHandEmpty", call(call(entity, "eU"), "e"));
        Object chest = entity.getClass().getMethod("a", Class.forName("bsy"))
                .invoke(entity, Class.forName("bsy").getField("e").get(null));
        state.put("chestEmpty", call(chest, "e"));
        state.put("riding", call(entity, "bS"));
        state.put("child", call(entity, "o_"));
        state.put("activeEffectCount", ((Collection<?>)call(entity, "et")).size());
        state.put("entitySwinging", read(entity, "btn", "aJ"));
        state.put("entitySwingTicks", read(entity, "btn", "aL"));
        state.put("entityHandSwingProgress", read(entity, "btn", "aS"));
        state.put("entityLastHandSwingProgress", read(entity, "btn", "aR"));
        state.put("entityInterpolatedProgressAtZero", entity.getClass().getMethod("B", float.class).invoke(entity, 0.0f));
        state.put("leaningPitchAtZero", entity.getClass().getMethod("a", float.class).invoke(entity, 0.0f));
        Method duration = Class.forName("btn").getDeclaredMethod("C");
        duration.setAccessible(true);
        state.put("officialSwingDurationNeutralGetter", duration.invoke(entity));
        Map<String, Object> expected = new LinkedHashMap<>();
        expected.put("worldNull", true); expected.put("pose", "STANDING");
        expected.put("isSneaking", false); expected.put("isInSneakingPose", false);
        expected.put("fallFlyingTicks", 0); expected.put("swimmingPose", false); expected.put("usingItem", false);
        expected.put("mainArm", "RIGHT"); expected.put("activeHand", "MAIN_HAND");
        expected.put("preferredHand", state.get("preferredHand"));
        expected.put("velocityZero", true); expected.put("mainHandEmpty", true); expected.put("offHandEmpty", true);
        expected.put("chestEmpty", true); expected.put("riding", false); expected.put("child", false);
        expected.put("activeEffectCount", 0); expected.put("entitySwinging", true); expected.put("entitySwingTicks", -1);
        expected.put("entityHandSwingProgress", 0.0f); expected.put("entityLastHandSwingProgress", 0.0f);
        expected.put("entityInterpolatedProgressAtZero", 0.0f); expected.put("leaningPitchAtZero", 0.0f);
        expected.put("officialSwingDurationNeutralGetter", 6);
        if (!state.equals(expected) || !List.of("MAIN_HAND", "OFF_HAND").contains(state.get("preferredHand")))
            throw new IllegalStateException("Entity state outside admitted normal fixture contract: " + state);
        return state;
    }

    private static Object[] newModel(float progress, boolean crouch) throws Exception {
        Object none = Class.forName("fyo").getField("a").get(null);
        Object data = Class.forName("fwp").getDeclaredMethod("a", Class.forName("fyo"), boolean.class).invoke(null, none, false);
        Object rootData = call(data, "a");
        Object root = rootData.getClass().getMethod("a", int.class, int.class).invoke(rootData, 64, 64);
        Object model = Class.forName("fwp").getConstructor(Class.forName("fyk"), boolean.class).newInstance(root, false);
        set(model, "fvk", "c", progress); set(model, "fvk", "d", false); set(model, "fvk", "e", false);
        set(model, "fvx", "t", crouch); set(model, "fvx", "u", 0.0f);
        Object empty = Class.forName("fvx$a").getField("a").get(null);
        set(model, "fvx", "r", empty); set(model, "fvx", "s", empty);
        return new Object[]{model, root};
    }

    private static Map<String, Object> modelState(Object model) throws Exception {
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("handSwingProgress", read(model, "fvk", "c")); state.put("sneaking", read(model, "fvx", "t"));
        state.put("riding", read(model, "fvk", "d")); state.put("child", read(model, "fvk", "e"));
        state.put("leaningPitch", read(model, "fvx", "u"));
        state.put("leftArmPose", enumName(read(model, "fvx", "r"))); state.put("rightArmPose", enumName(read(model, "fvx", "s")));
        return state;
    }

    private static void vector(StringBuilder out, float... values) {
        out.append('[');
        for (int i = 0; i < values.length; i++) {
            if (!Float.isFinite(values[i])) throw new IllegalStateException("Nonfinite ModelPart output");
            if (i != 0) out.append(','); out.append(Float.toString(values[i]));
        }
        out.append(']');
    }

    private static void partJson(StringBuilder out, Object part) throws Exception {
        float[] raw = new float[9];
        out.append("{\"rawModelPart\":{");
        for (int i = 0; i < raw.length; i++) {
            raw[i] = ((Number)read(part, "fyk", FIELDS[i])).floatValue();
            if (i != 0) out.append(','); out.append(quote(NAMES[i])).append(':').append(Float.toString(raw[i]));
        }
        out.append("},\"rawFloatBits\":[");
        for (int i = 0; i < raw.length; i++) {
            if (i != 0) out.append(','); out.append(Float.floatToRawIntBits(raw[i]));
        }
        out.append("],\"translationMetres\":"); vector(out, raw[0]/16.0f, 1.5f-raw[1]/16.0f, -raw[2]/16.0f);
        Object quaternion = Class.forName("org.joml.Quaternionf").getConstructor().newInstance();
        quaternion.getClass().getMethod("rotationZYX", float.class, float.class, float.class).invoke(quaternion, raw[5], raw[4], raw[3]);
        out.append(",\"rotationQuaternionXYZW\":");
        vector(out, quaternion.getClass().getField("x").getFloat(quaternion), -quaternion.getClass().getField("y").getFloat(quaternion),
                -quaternion.getClass().getField("z").getFloat(quaternion), quaternion.getClass().getField("w").getFloat(quaternion));
        out.append(",\"scale\":"); vector(out, raw[6], raw[7], raw[8]); out.append('}');
    }

    private static float sourceFloat(JsonObject object) {
        if (!object.keySet().equals(java.util.Set.of("value", "rawBits")))
            throw new IllegalStateException("Float source inventory differs");
        int bits = object.get("rawBits").getAsInt();
        float value = Float.intBitsToFloat(bits);
        if (!Float.isFinite(value) || Float.floatToRawIntBits(object.get("value").getAsFloat()) != bits)
            throw new IllegalStateException("Captured float value/bits differ");
        return value;
    }

    private static float observed(JsonObject state, String key) {
        return sourceFloat(state.getAsJsonObject(key));
    }

    private static boolean flag(JsonObject state, String key) {
        return state.get(key).getAsBoolean();
    }

    private static float math(String name, float... args) throws Exception {
        Class<?>[] signature = new Class<?>[args.length];
        java.util.Arrays.fill(signature, float.class);
        Object[] values = new Object[args.length];
        for (int i = 0; i < args.length; i++) values[i] = args[i];
        return ((Number)Class.forName("ayo").getDeclaredMethod(name, signature).invoke(null, values)).floatValue();
    }

    private static void sourceGate(JsonObject state, JsonObject point, String profile) {
        boolean crouch = profile.startsWith("crouching_");
        String hand = profile.endsWith("_off") ? "OFF_HAND" : "MAIN_HAND";
        if (!state.get("mainArm").getAsString().equals("RIGHT")
                || !state.get("preferredHand").getAsString().equals(hand)
                || !state.get("pose").getAsString().equals(crouch ? "CROUCHING" : "STANDING")
                || flag(state, "isInSneakingPose") != crouch || flag(state, "isSneaking") != crouch
                || !flag(state, "mainHandEmpty") || !flag(state, "offHandEmpty")
                || flag(state, "usingItem") || flag(state, "baby") || flag(state, "riding")
                || !flag(state, "alive") || flag(state, "spectator") || flag(state, "sleeping")
                || flag(state, "fallFlying") || state.get("fallFlyingTicks").getAsInt() != 0
                || flag(state, "inSwimmingPose") || !flag(state, "statusEffectsEmpty")
                || observed(point, "leaningPitch") != 0.0f || observed(point, "limbSpeed") != 0.0f)
            throw new IllegalStateException("Captured player outside admitted six-joint scope");
        String name = state.get("playerName").getAsString();
        if (flag(state, "hasCustomName") || name.equals("Dinnerbone") || name.equals("Grumm"))
            throw new IllegalStateException("Unreviewed upside-down renderer branch");
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        if (args.length != 2 || Files.exists(Path.of(args[1])))
            throw new IllegalArgumentException("Expected fixed captured-player input and fresh output");
        JsonObject source = JsonParser.parseString(Files.readString(Path.of(args[0]), StandardCharsets.UTF_8)).getAsJsonObject();
        if (!source.get("result").getAsString().equals("pass")
                || !source.get("completePlayerTickMethodExecuted").getAsBoolean()
                || !source.getAsJsonObject("scope").get("worldAgeLifecycleVerified").getAsBoolean())
            throw new IllegalStateException("Source lacks successful real World/player tick evidence");
        JsonArray frames = source.getAsJsonArray("frames");
        if (frames.size() != 32) throw new IllegalStateException("Expected 32 captured frames");
        Class.forName("ab").getMethod("a").invoke(null);
        Class.forName("akt").getMethod("a").invoke(null);
        StringBuilder out = new StringBuilder("{\"schemaVersion\":1,\"minecraftVersion\":\"1.21.1\","
                + "\"sourceType\":\"ServerPlayerEntity\",\"sourcePlayerStateCaptured\":true,"
                + "\"sourceFrameCount\":32,\"sampleCount\":96,\"fixtureType\":\"ArmorStandEntity\","
                + "\"fixtureIsPlayer\":false,\"worldNull\":true,\"fixtureEntityTicked\":false,"
                + "\"officialMethodsCalled\":true,\"rendererExecuted\":false,\"nativeApplied\":false,"
                + "\"animationSystemComplete\":false,\"sourceRunTicket\":");
        out.append(quote(source.get("runTicket").getAsString())).append(",\"samples\":[");
        Method animate = Class.forName("fvx").getMethod("a", Class.forName("btn"), float.class, float.class, float.class);
        Method angles = Class.forName("fwp").getMethod("a", Class.forName("btn"), float.class, float.class, float.class, float.class, float.class);
        Method preferred = Class.forName("fvx").getDeclaredMethod("c", Class.forName("btn"));
        preferred.setAccessible(true);
        int calls = 0;
        String[] profiles = {"standing_main", "standing_off", "crouching_main", "crouching_off"};
        for (int index = 0; index < frames.size(); index++) {
            JsonObject frame = frames.get(index).getAsJsonObject();
            String profile = frame.get("profile").getAsString();
            if (!profile.equals(profiles[index / 8]) || frame.get("profileFrame").getAsInt() != index % 8)
                throw new IllegalStateException("Captured profile ordering differs");
            JsonObject state = frame.getAsJsonObject("after");
            JsonArray interpolation = state.getAsJsonArray("interpolation");
            if (interpolation.size() != 3) throw new IllegalStateException("Expected three actual getter samples");
            for (int deltaIndex = 0; deltaIndex < 3; deltaIndex++) {
                JsonObject point = interpolation.get(deltaIndex).getAsJsonObject();
                sourceGate(state, point, profile);
                float delta = observed(point, "tickDelta");
                if (Float.floatToRawIntBits(delta) != Float.floatToRawIntBits(deltaIndex / 2.0f))
                    throw new IllegalStateException("Captured delta inventory differs");
                float progress = observed(point, "handSwingProgress");
                if (progress < 0 || progress > 1) throw new IllegalStateException("Captured progress outside range");
                float limbAngle = observed(point, "limbPosition"), limbDistance = observed(point, "limbSpeed");
                float age = (float)state.get("age").getAsInt() + delta;
                float bodyYaw = math("j", delta, observed(state, "prevBodyYaw"), observed(state, "bodyYaw"));
                float headYaw = math("g", math("j", delta, observed(state, "prevHeadYaw"), observed(state, "headYaw")) - bodyYaw);
                float headPitch = math("i", delta, observed(state, "prevPitch"), observed(state, "pitch"));
                boolean crouch = flag(state, "isInSneakingPose");
                Object hand = Class.forName("bqq").getField(profile.endsWith("_off") ? "b" : "a").get(null);
                Object entity = newEntity();
                entity.getClass().getMethod("a", Class.forName("bqq")).invoke(entity, hand);
                Object[] objects = newModel(progress, crouch); Object model = objects[0], root = objects[1];
                Map<String, Object> before = entityState(entity), modelBefore = modelState(model);
                String armBefore = enumName(preferred.invoke(model, entity));
                String expectedArm = profile.endsWith("_off") ? "LEFT" : "RIGHT";
                if (!armBefore.equals(expectedArm) || !before.get("preferredHand").equals(enumName(hand)))
                    throw new IllegalStateException("Official adapter preferred arm differs");
                animate.invoke(model, entity, limbAngle, limbDistance, delta);
                angles.invoke(model, entity, limbAngle, limbDistance, age, headYaw, headPitch);
                Map<String, Object> after = entityState(entity), modelAfter = modelState(model);
                String armAfter = enumName(preferred.invoke(model, entity));
                if (!before.equals(after) || !modelBefore.equals(modelAfter) || !armBefore.equals(armAfter))
                    throw new IllegalStateException("Same-frame adapter inputs changed");
                Map<String, Object> inputs = new LinkedHashMap<>();
                inputs.put("handSwingProgress", progress); inputs.put("modelSneaking", crouch);
                inputs.put("preferredHand", enumName(hand)); inputs.put("limbAngle", limbAngle);
                inputs.put("limbDistance", limbDistance); inputs.put("age", age);
                inputs.put("headYawDegrees", headYaw); inputs.put("headPitchDegrees", headPitch); inputs.put("tickDelta", delta);
                Map<String, Object> bits = new LinkedHashMap<>();
                for (var entry : inputs.entrySet()) if (entry.getValue() instanceof Float value)
                    bits.put(entry.getKey(), Float.floatToRawIntBits(value));
                inputs.put("rawFloatBits", bits);
                if (calls != 0) out.append(',');
                out.append("{\"sampleIndex\":").append(calls)
                        .append(",\"sourceFrameIndex\":").append(index)
                        .append(",\"sourceDeltaIndex\":").append(deltaIndex)
                        .append(",\"sourceServerTick\":").append(frame.get("serverTick").getAsInt())
                        .append(",\"sourceProfile\":").append(quote(profile))
                        .append(",\"sourceProfileFrame\":").append(frame.get("profileFrame").getAsInt())
                        .append(",\"sourceAge\":").append(state.get("age").getAsInt())
                        .append(",\"inputs\":").append(json(inputs))
                        .append(",\"fixtureStateBefore\":").append(json(before)).append(",\"fixtureStateAfter\":").append(json(after))
                        .append(",\"modelStateBefore\":").append(json(modelBefore)).append(",\"modelStateAfter\":").append(json(modelAfter))
                        .append(",\"officialPreferredArmBefore\":").append(quote(armBefore))
                        .append(",\"officialPreferredArmAfter\":").append(quote(armAfter)).append(",\"parts\":{");
                Map<String, Object> children = (Map<String, Object>)read(root, "fyk", "n");
                for (int i = 0; i < PARTS.length; i++) {
                    if (i != 0) out.append(','); Object part = children.get(PARTS[i]);
                    if (part == null) throw new IllegalStateException("Actual official base part missing");
                    out.append(quote(PARTS[i])).append(':'); partJson(out, part);
                }
                out.append("}}"); calls++;
            }
        }
        out.append("],\"animateModelCalls\":").append(calls).append(",\"setAnglesCalls\":").append(calls)
                .append(",\"swingHandCalls\":").append(calls).append(",\"preferredArmGetterCalls\":").append(2*calls)
                .append(",\"officialMathHelperCalls\":").append(4*calls).append("}\n");
        Files.writeString(Path.of(args[1]), out.toString(), StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
    }
}
