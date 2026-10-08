package local.crimsonmc.assets;

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

/** Calls the fixed official model, with explicit model-input pose samples.
 * The normal ArmorStand fixture remains STANDING, has a null World and is not a
 * Player. MAIN/OFF are its right main arm / left off arm, never a left-main Player.
 * No entity tick, renderer, substitute World, Unsafe or native hook is used.
 */
public final class SteveActionPoseDump {
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

    private static Map<String, Object> preconditions() throws Exception {
        Map<String, Object> evidence = new LinkedHashMap<>();
        Object flagFixture = newEntity();
        flagFixture.getClass().getMethod("g", boolean.class).invoke(flagFixture, true);
        if (!call(flagFixture, "bW").equals(true) || !call(flagFixture, "cb").equals(false))
            throw new IllegalStateException("Official sneak flag unexpectedly changed Pose");
        evidence.put("setSneakingTrueGetter", call(flagFixture, "bW"));
        evidence.put("poseAfterSneakFlag", enumName(call(flagFixture, "at")));
        Object poseFixture = newEntity();
        try {
            poseFixture.getClass().getMethod("b", Class.forName("bua"))
                    .invoke(poseFixture, Class.forName("bua").getField("f").get(null));
            throw new IllegalStateException("Crouch Pose unexpectedly accepted; review World boundary before export");
        } catch (InvocationTargetException failure) {
            Throwable reason = failure.getCause();
            if (!(reason instanceof NullPointerException)) throw failure;
            List<String> frames = new ArrayList<>();
            for (StackTraceElement frame : reason.getStackTrace())
                if (List.of("bsr", "btn", "ciw", "aka").contains(frame.getClassName()))
                    frames.add(frame.getClassName() + '.' + frame.getMethodName() + ':' + frame.getLineNumber());
            if (frames.isEmpty() || !frames.get(0).equals("bsr.i_:3064")) throw new IllegalStateException("Unreviewed Pose failure", reason);
            evidence.put("setCrouchPoseAccepted", false);
            evidence.put("setCrouchPoseException", reason.getClass().getName());
            evidence.put("setCrouchPoseExceptionMessage", reason.getMessage());
            evidence.put("setCrouchPoseOfficialStack", frames);
        }
        evidence.put("failedPoseFixtureReused", false);
        evidence.put("playerConstructed", false); evidence.put("mobConstructed", false);
        evidence.put("worldConstructed", false); evidence.put("entityTickCalled", false);
        return evidence;
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

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || Files.exists(Path.of(args[0]))) throw new IllegalArgumentException("Expected one fresh output path");
        Class.forName("ab").getMethod("a").invoke(null);
        Class.forName("akt").getMethod("a").invoke(null);
        StringBuilder out = new StringBuilder("{\"schemaVersion\":1,\"minecraftVersion\":\"1.21.1\","
                + "\"fixtureType\":\"ArmorStandEntity\",\"fixtureIsPlayer\":false,\"worldNull\":true,\"entityTicked\":false,"
                + "\"officialMethodsCalled\":true,\"progressIsTickCycle\":false,\"leftMainHandPlayerCovered\":false,"
                + "\"rendererSynchronizationApplied\":false,\"crouchingEntityPoseApplied\":false,"
                + "\"nativeApplied\":false,\"animationSystemComplete\":false,\"preconditions\":");
        out.append(json(preconditions())).append(",\"profiles\":{");
        String[] profiles = {"model_crouch", "right_main_hand_swing", "right_off_hand_swing"};
        int calls = 0;
        Method animate = Class.forName("fvx").getMethod("a", Class.forName("btn"), float.class, float.class, float.class);
        Method angles = Class.forName("fwp").getMethod("a", Class.forName("btn"), float.class, float.class, float.class, float.class, float.class);
        Method preferred = Class.forName("fvx").getDeclaredMethod("c", Class.forName("btn")); preferred.setAccessible(true);
        for (int profile = 0; profile < profiles.length; profile++) {
            if (profile != 0) out.append(','); out.append(quote(profiles[profile])).append(":[");
            int samples = profile >= 1 ? 21 : 1;
            Object hand = Class.forName("bqq").getField(profile == 2 ? "b" : "a").get(null);
            for (int index = 0; index < samples; index++) {
                if (index != 0) out.append(',');
                float progress = profile >= 1 ? index / 20.0f : 0.0f;
                Object entity = newEntity();
                // Official method sets real preferredHand; activeHand stays MAIN_HAND.
                entity.getClass().getMethod("a", Class.forName("bqq")).invoke(entity, hand);
                Object[] modelObjects = newModel(progress, profile == 0);
                Object model = modelObjects[0], root = modelObjects[1];
                Map<String, Object> before = entityState(entity), modelBefore = modelState(model);
                String preferredBefore = enumName(preferred.invoke(model, entity));
                String expectedArm = profile == 2 ? "LEFT" : "RIGHT";
                if (!preferredBefore.equals(expectedArm) || !before.get("preferredHand").equals(enumName(hand)))
                    throw new IllegalStateException("Official preferred-arm input branch differs");
                animate.invoke(model, entity, 0.0f, 0.0f, 0.0f);
                angles.invoke(model, entity, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f);
                calls++;
                Map<String, Object> after = entityState(entity), modelAfter = modelState(model);
                String preferredAfter = enumName(preferred.invoke(model, entity));
                if (!before.equals(after) || !modelBefore.equals(modelAfter) || !preferredBefore.equals(preferredAfter))
                    throw new IllegalStateException("Same-frame entity/model inputs changed during official evaluation");
                out.append("{\"sampleIndex\":").append(index).append(",\"inputs\":{\"handSwingProgress\":").append(progress)
                        .append(",\"modelSneaking\":").append(profile == 0)
                        .append(",\"preferredHand\":").append(quote(enumName(hand)))
                        .append(",\"limbAngle\":0.0,\"limbDistance\":0.0,\"age\":0.0,\"headYawDegrees\":0.0,\"headPitchDegrees\":0.0,\"tickDelta\":0.0}")
                        .append(",\"fixtureStateBefore\":").append(json(before)).append(",\"fixtureStateAfter\":").append(json(after))
                        .append(",\"modelStateBefore\":").append(json(modelBefore)).append(",\"modelStateAfter\":").append(json(modelAfter))
                        .append(",\"officialPreferredArmBefore\":").append(quote(preferredBefore))
                        .append(",\"officialPreferredArmAfter\":").append(quote(preferredAfter)).append(",\"parts\":{");
                Map<String, Object> children = (Map<String, Object>)read(root, "fyk", "n");
                for (int i = 0; i < PARTS.length; i++) {
                    if (i != 0) out.append(','); Object part = children.get(PARTS[i]);
                    if (part == null) throw new IllegalStateException("Missing actual model part");
                    out.append(quote(PARTS[i])).append(':'); partJson(out, part);
                }
                out.append("}}");
            }
            out.append(']');
        }
        out.append("},\"animateModelCalls\":").append(calls).append(",\"setAnglesCalls\":").append(calls)
                .append(",\"swingHandCalls\":").append(calls).append(",\"preferredArmGetterCalls\":").append(2*calls).append("}\n");
        Files.writeString(Path.of(args[0]), out.toString(), StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
    }
}
