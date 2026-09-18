// L1-A19 RUN-B: the German IdNr check digit in its verification form.
//
// RUN-A folds the first ten digits, produces the eleventh and compares it.
// This program never produces a check digit. It folds all eleven digits and
// requires the final intermediate value to be 1, which is the ISO/IEC 7064
// hybrid-system verification condition. The two are equivalent in arithmetic
// and different in expression, and they are written in different languages by
// different code paths, so a defect in one does not reproduce itself in the
// other.
//
// It reads no RUN-A output and knows nothing about RUN-A's conclusions. Its
// only inputs are the value list it is given and its own arithmetic.

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class WpnoIdnrValidateRunB {

    // Every input line carries this marker so that an empty identifier is
    // still one input and not an empty line indistinguishable from the file's
    // own structure.
    private static final String INPUT_MARKER = ">";
    private static final String SEPARATORS = " -./,";

    private static String compact(String value) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (SEPARATORS.indexOf(c) < 0) {
                sb.append(c);
            }
        }
        return sb.toString().strip();
    }

    private static boolean allAsciiDigits(String s) {
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c < '0' || c > '9') {
                return false;
            }
        }
        return s.length() > 0;
    }

    // The verification fold. Runs over every digit including the check digit
    // and returns the final intermediate. A valid number yields 1.
    private static int finalIntermediate(String digits) {
        int p = 10;
        int m = 0;
        for (int i = 0; i < digits.length(); i++) {
            m = (digits.charAt(i) - '0' + p) % 10;
            if (m == 0) {
                m = 10;
            }
            p = (2 * m) % 11;
        }
        return m;
    }

    // Structural rule, computed here independently of RUN-A: exactly one of
    // the first ten digits repeats, and it repeats twice or three times.
    private static boolean repetitionRuleSatisfied(String firstTen) {
        Map<Character, Integer> counter = new HashMap<>();
        for (int i = 0; i < firstTen.length(); i++) {
            counter.merge(firstTen.charAt(i), 1, Integer::sum);
        }
        int repeated = 0;
        int repeatCount = 0;
        for (int c : counter.values()) {
            if (c > 1) {
                repeated++;
                repeatCount = c;
            }
        }
        return repeated == 1 && (repeatCount == 2 || repeatCount == 3);
    }

    private static String jsonEscape(String s) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }

    private static String classify(String raw) {
        String compacted = compact(raw);
        if (compacted.length() != 11) {
            return "INVALID_LENGTH";
        }
        if (!allAsciiDigits(compacted)) {
            return "INVALID_FORMAT_NON_DIGIT";
        }
        if (compacted.charAt(0) == '0') {
            return "INVALID_FORMAT_LEADING_ZERO";
        }
        if (!repetitionRuleSatisfied(compacted.substring(0, 10))) {
            return "INVALID_FORMAT_REPETITION";
        }
        if (finalIntermediate(compacted) != 1) {
            return "INVALID_CHECKSUM";
        }
        return "VALID";
    }

    public static void main(String[] args) throws IOException {
        Path inputs = null;
        Path out = null;
        for (int i = 0; i < args.length - 1; i++) {
            if ("--values".equals(args[i])) {
                inputs = Paths.get(args[i + 1]);
            } else if ("--out".equals(args[i])) {
                out = Paths.get(args[i + 1]);
            }
        }
        if (inputs == null || out == null) {
            System.err.println("usage: --values <file> --out <file>");
            System.exit(2);
            return;
        }

        List<String> values = new ArrayList<>();
        try (BufferedReader reader = Files.newBufferedReader(
                inputs, StandardCharsets.UTF_8)) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (!line.startsWith(INPUT_MARKER)) {
                    System.err.println("input line without the marker");
                    System.exit(3);
                    return;
                }
                values.add(line.substring(INPUT_MARKER.length()));
            }
        }

        try (BufferedWriter writer = Files.newBufferedWriter(
                out, StandardCharsets.UTF_8)) {
            for (String raw : values) {
                String compacted = compact(raw);
                String result = classify(raw);
                int intermediate = (compacted.length() == 11
                        && allAsciiDigits(compacted))
                        ? finalIntermediate(compacted) : -1;
                writer.write("{\"raw\":\"" + jsonEscape(raw)
                        + "\",\"compacted\":\"" + jsonEscape(compacted)
                        + "\",\"final_intermediate\":" + intermediate
                        + ",\"result\":\"" + result + "\"}");
                writer.newLine();
            }
        }
        System.out.println("answered " + values.size() + " inputs");
    }
}
