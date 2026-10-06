package local.crimsonmc.assets;

import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** Offline geometry reader for the hash-pinned, official Minecraft 1.21.1 client.
 * No client main, game process, native function, rendering or game installation is used.
 * Obfuscated names are valid only for the client SHA checked by build_steve_asset.py.
 */
public final class SteveModelDump {
    private static Object field(Object value, String name) throws Exception {
        Field field = value.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(value);
    }

    private static String numbers(Object value, String... names) throws Exception {
        StringBuilder result = new StringBuilder("[");
        for (int i = 0; i < names.length; i++) {
            if (i > 0) result.append(',');
            float number = ((Number) field(value, names[i])).floatValue();
            if (!Float.isFinite(number)) throw new IllegalStateException("Nonfinite model value");
            result.append(Float.toString(number));
        }
        return result.append(']').toString();
    }

    @SuppressWarnings("unchecked")
    private static void part(StringBuilder result, String name, Object part) throws Exception {
        if (!name.matches("[a-z_]+")) throw new IllegalStateException("Unexpected part name");
        result.append("{\"name\":\"").append(name).append("\",\"pivot\":")
              .append(numbers(part, "b", "c", "d"))
              .append(",\"rotation\":").append(numbers(part, "e", "f", "g"))
              .append(",\"scale\":").append(numbers(part, "h", "i", "j"))
              .append(",\"cuboids\":[");
        boolean firstCuboid = true;
        for (Object cuboid : (List<Object>) field(part, "m")) {
            if (!firstCuboid) result.append(',');
            firstCuboid = false;
            result.append("{\"quads\":[");
            boolean firstQuad = true;
            for (Object quad : (Object[]) field(cuboid, "g")) {
                if (!firstQuad) result.append(',');
                firstQuad = false;
                result.append("{\"normal\":").append(numbers(field(quad, "b"), "x", "y", "z"))
                      .append(",\"vertices\":[");
                boolean firstVertex = true;
                for (Object vertex : (Object[]) field(quad, "a")) {
                    if (!firstVertex) result.append(',');
                    firstVertex = false;
                    String position = numbers(field(vertex, "a"), "x", "y", "z");
                    result.append(position, 0, position.length() - 1).append(',')
                          .append(field(vertex, "b")).append(',').append(field(vertex, "c")).append(']');
                }
                result.append("]}");
            }
            result.append("]}");
        }
        if (!((Map<String, Object>) field(part, "n")).isEmpty()) {
            throw new IllegalStateException("Unexpected nested Minecraft model hierarchy");
        }
        result.append("]}");
    }

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("Expected dump output path");
        Class<?> dilation = Class.forName("fyo");
        Object none = dilation.getField("a").get(null);
        Object modelData = Class.forName("fwp").getDeclaredMethod("a", dilation, boolean.class)
                                      .invoke(null, none, false); // classic 4-pixel arms
        Object rootData = modelData.getClass().getMethod("a").invoke(modelData);
        Object root = rootData.getClass().getMethod("a", int.class, int.class).invoke(rootData, 64, 64);
        Map<String, Object> children = new TreeMap<>((Map<String, Object>) field(root, "n"));
        StringBuilder result = new StringBuilder("{\"minecraftVersion\":\"1.21.1\",\"thinArms\":false,\"textureSize\":[64,64],\"parts\":[");
        boolean first = true;
        for (Map.Entry<String, Object> child : children.entrySet()) {
            if (!first) result.append(',');
            first = false;
            part(result, child.getKey(), child.getValue());
        }
        Files.writeString(Path.of(args[0]), result.append("]}\n").toString(), StandardCharsets.UTF_8);
    }
}
