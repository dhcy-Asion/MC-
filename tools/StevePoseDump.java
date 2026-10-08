package local.crimsonmc.assets;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.LinkedHashMap;
import java.util.Map;

/** Limited offline oracle: invokes the pinned 1.21.1 PlayerEntityModel itself.
 * A normally constructed ArmorStandEntity is an explicitly declared fixture.
 * No world, player/client main, tick, rendering, native hook or Unsafe is used.
 */
public final class StevePoseDump {
    private static final int CYCLE_TICKS = 40;
    private static final String[] PARTS = {"head", "body", "right_arm", "left_arm", "right_leg", "left_leg"};
    private static final String[] FIELDS = {"b", "c", "d", "e", "f", "g", "h", "i", "j"};
    private static final String[] NAMES = {"pivotX", "pivotY", "pivotZ", "pitch", "yaw", "roll", "scaleX", "scaleY", "scaleZ"};

    private static Object read(Object object, Class<?> owner, String name) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(object);
    }

    private static void set(Object object, Class<?> owner, String name, Object value) throws Exception {
        Field field = owner.getDeclaredField(name);
        field.setAccessible(true);
        field.set(object, value);
    }

    private static Object call(Object object, String name) throws Exception {
        return object.getClass().getMethod(name).invoke(object);
    }

    private static String number(float value) {
        if (!Float.isFinite(value)) throw new IllegalStateException("Nonfinite pose value");
        return Float.toString(value);
    }

    private static void vector(StringBuilder out, float... values) {
        out.append('[');
        for (int i = 0; i < values.length; i++) {
            if (i != 0) out.append(',');
            out.append(number(values[i]));
        }
        out.append(']');
    }

    private static Map<String, Object> entityState(Object entity) throws Exception {
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("fallFlyingTicks", call(entity, "fB"));
        state.put("swimmingPose", call(entity, "ce"));
        state.put("usingItem", call(entity, "fr"));
        state.put("sneaking", call(entity, "cb"));
        state.put("mainArmRight", call(entity, "fq") == Class.forName("btg").getField("b").get(null));
        state.put("activeHandMain", call(entity, "fs") == Class.forName("bqq").getField("a").get(null));
        Object velocity = call(entity, "dr");
        state.put("velocityZero", velocity.equals(Class.forName("exc").getField("b").get(null)));
        Object chest = entity.getClass().getMethod("a", Class.forName("bsy"))
                             .invoke(entity, Class.forName("bsy").getField("e").get(null));
        state.put("chestEmpty", call(chest, "e"));
        Map<String, Object> expected = new LinkedHashMap<>();
        expected.put("fallFlyingTicks", 0);
        expected.put("swimmingPose", false);
        expected.put("usingItem", false);
        expected.put("sneaking", false);
        expected.put("mainArmRight", true);
        expected.put("activeHandMain", true);
        expected.put("velocityZero", true);
        expected.put("chestEmpty", true);
        if (!state.equals(expected)) throw new IllegalStateException("Entity fixture state is outside the limited contract: " + state);
        return state;
    }

    private static void stateJson(StringBuilder out, Map<String, Object> state) {
        out.append('{');
        boolean first = true;
        for (Map.Entry<String, Object> entry : state.entrySet()) {
            if (!first) out.append(',');
            first = false;
            out.append('"').append(entry.getKey()).append("\":").append(entry.getValue());
        }
        out.append('}');
    }

    private static Object[] newModel() throws Exception {
        Class<?> partClass = Class.forName("fyk");
        Object none = Class.forName("fyo").getField("a").get(null);
        Object data = Class.forName("fwp").getDeclaredMethod("a", Class.forName("fyo"), boolean.class)
                              .invoke(null, none, false);
        Object rootData = data.getClass().getMethod("a").invoke(data);
        Object root = rootData.getClass().getMethod("a", int.class, int.class).invoke(rootData, 64, 64);
        Object model = Class.forName("fwp").getConstructor(partClass, boolean.class).newInstance(root, false);
        Class<?> entityModel = Class.forName("fvk"), biped = Class.forName("fvx");
        set(model, entityModel, "c", 0.0f); // handSwingProgress: no attack
        set(model, entityModel, "d", false); // riding
        set(model, entityModel, "e", false); // child
        set(model, biped, "t", false); // sneaking
        set(model, biped, "u", 0.0f); // leaningPitch
        Object empty = Class.forName("fvx$a").getField("a").get(null);
        set(model, biped, "r", empty);
        set(model, biped, "s", empty);
        return new Object[]{model, root};
    }

    private static void assertModelState(Object model) throws Exception {
        Class<?> base = Class.forName("fvk"), biped = Class.forName("fvx");
        Object empty = Class.forName("fvx$a").getField("a").get(null);
        if (!read(model, base, "c").equals(0.0f) || !read(model, base, "d").equals(false)
                || !read(model, base, "e").equals(false) || !read(model, biped, "t").equals(false)
                || !read(model, biped, "u").equals(0.0f) || read(model, biped, "r") != empty
                || read(model, biped, "s") != empty) {
            throw new IllegalStateException("Model state departed from the admitted empty-hand adult standing contract");
        }
    }

    private static void partJson(StringBuilder out, Object part) throws Exception {
        float[] raw = new float[9];
        Class<?> partClass = Class.forName("fyk");
        out.append("{\"rawModelPart\":{");
        for (int i = 0; i < raw.length; i++) {
            raw[i] = ((Number) read(part, partClass, FIELDS[i])).floatValue();
            if (i != 0) out.append(',');
            out.append('"').append(NAMES[i]).append("\":").append(number(raw[i]));
        }
        out.append("},\"rawFloatBits\":[");
        for (int i = 0; i < raw.length; i++) {
            if (i != 0) out.append(',');
            out.append(Float.floatToRawIntBits(raw[i]));
        }
        out.append("],\"translationMetres\":");
        vector(out, raw[0] / 16.0f, 1.5f - raw[1] / 16.0f, -raw[2] / 16.0f);
        // Coordinate conversion only; the pose angles above came from MC.
        Object q = Class.forName("org.joml.Quaternionf").getConstructor().newInstance();
        q.getClass().getMethod("rotationZYX", float.class, float.class, float.class).invoke(q, raw[5], raw[4], raw[3]);
        out.append(",\"rotationQuaternionXYZW\":");
        vector(out, q.getClass().getField("x").getFloat(q), -q.getClass().getField("y").getFloat(q),
                    -q.getClass().getField("z").getFloat(q), q.getClass().getField("w").getFloat(q));
        out.append(",\"scale\":");
        vector(out, raw[6], raw[7], raw[8]);
        out.append('}');
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected one fresh pose output path");
        Path output = Path.of(args[0]);
        if (Files.exists(output)) throw new IllegalArgumentException("Pose output already exists");
        Class.forName("ab").getMethod("a").invoke(null); // official version initialization
        Class.forName("akt").getMethod("a").invoke(null); // registry bootstrap, no server/client main
        Object type = Class.forName("bsx").getField("d").get(null);
        Object entity = Class.forName("ciw").getConstructor(Class.forName("bsx"), Class.forName("dcw"))
                                .newInstance(type, null);
        if (read(entity, Class.forName("bsr"), "r") != null) throw new IllegalStateException("Fixture unexpectedly acquired a World");
        Map<String, Object> initial = entityState(entity);
        Method animate = Class.forName("fvx").getMethod("a", Class.forName("btn"), float.class, float.class, float.class);
        Method angles = Class.forName("fwp").getMethod("a", Class.forName("btn"), float.class, float.class,
                                                       float.class, float.class, float.class);
        StringBuilder out = new StringBuilder("{\"schemaVersion\":1,\"minecraftVersion\":\"1.21.1\","
                + "\"fixtureType\":\"ArmorStandEntity\",\"fixtureIsPlayer\":false,\"worldNull\":true,\"entityTicked\":false,"
                + "\"officialMethodsCalled\":true,\"cycleTicks\":40,\"endpointIncluded\":true,"
                + "\"nativeApplied\":false,\"animationSystemComplete\":false,\"fixtureState\":");
        stateJson(out, initial);
        out.append(",\"profiles\":{");
        int calls = 0;
        String[] profiles = {"standing", "look", "walk"};
        for (int profile = 0; profile < profiles.length; profile++) {
            if (profile != 0) out.append(',');
            out.append('"').append(profiles[profile]).append("\":[");
            for (int tick = 0; tick <= CYCLE_TICKS; tick++) {
                if (tick != 0) out.append(',');
                Object[] objects = newModel();
                Object model = objects[0], root = objects[1];
                Map<String, Object> before = entityState(entity);
                float phase = (float) (2.0 * Math.PI * tick / CYCLE_TICKS);
                float limbAngle = profile == 2 ? phase / 0.6662f : 0.0f;
                float limbDistance = profile == 2 ? 0.6f : 0.0f;
                float age = tick, headYaw = profile == 1 ? 30.0f : 0.0f, headPitch = profile == 1 ? 15.0f : 0.0f;
                animate.invoke(model, entity, limbAngle, limbDistance, 0.0f);
                angles.invoke(model, entity, limbAngle, limbDistance, age, headYaw, headPitch);
                calls++;
                assertModelState(model);
                Map<String, Object> after = entityState(entity);
                if (!initial.equals(before) || !initial.equals(after)) throw new IllegalStateException("Entity state changed during pose evaluation");
                out.append("{\"tick\":").append(tick).append(",\"inputs\":{\"phaseRadians\":").append(number(phase))
                   .append(",\"limbAngle\":").append(number(limbAngle)).append(",\"limbDistance\":").append(number(limbDistance))
                   .append(",\"age\":").append(number(age)).append(",\"headYawDegrees\":").append(number(headYaw))
                   .append(",\"headPitchDegrees\":").append(number(headPitch)).append(",\"tickDelta\":0.0},\"fixtureStateBefore\":");
                stateJson(out, before);
                out.append(",\"fixtureStateAfter\":");
                stateJson(out, after);
                out.append(",\"parts\":{");
                Map<String, Object> children = (Map<String, Object>) read(root, Class.forName("fyk"), "n");
                for (int i = 0; i < PARTS.length; i++) {
                    if (i != 0) out.append(',');
                    Object part = children.get(PARTS[i]);
                    if (part == null) throw new IllegalStateException("Missing classic model part " + PARTS[i]);
                    out.append('"').append(PARTS[i]).append("\":");
                    partJson(out, part);
                }
                out.append("}}");
            }
            out.append(']');
        }
        out.append("},\"animateModelCalls\":").append(calls).append(",\"setAnglesCalls\":").append(calls).append("}\n");
        Files.writeString(output, out.toString(), StandardCharsets.UTF_8, StandardOpenOption.CREATE_NEW);
    }
}
