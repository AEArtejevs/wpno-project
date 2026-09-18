// WpnoIbanValidateRunB - L1-A18 RUN-B: IBAN validation against REF-01.
//
// This is the second opinion, and it is written to be able to differ from the
// first. Where RUN-A is Python, this is Java: a different language, a
// different runtime, a different standard library. Where RUN-A folds the
// MOD97-10 remainder character by character and never builds the large
// number, this expands the IBAN into its full decimal string and takes a
// single BigInteger modulus. Where RUN-A walks structure tokens one at a
// time, this expands the structure into a per-position character-class array
// and indexes into it.
//
// Same rules, same inputs, deliberately different machinery. Two
// implementations that agree because they are the same implementation twice
// would prove nothing at all.
//
// RUN-B reads the immutable REF-01 rules and the immutable REF-02 vectors and
// nothing else. It does not import, call, or read anything belonging to
// RUN-A, and it is never told what RUN-A concluded.

import java.io.BufferedReader;
import java.io.IOException;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class WpnoIbanValidateRunB {

    private static final BigInteger NINETY_SEVEN = BigInteger.valueOf(97);
    private static final String SEPARATORS = " -.";
    private static final String NORMALIZATION = "clean(number, ' -.').strip().upper()";

    private static final Map<Character, String> CLASSES = new HashMap<>();
    static {
        CLASSES.put('n', "0123456789");
        CLASSES.put('a', "ABCDEFGHIJKLMNOPQRSTUVWXYZ");
        CLASSES.put('c', "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                       + "abcdefghijklmnopqrstuvwxyz");
    }

    /** One country's rule set, as read from the immutable REF-01 corpus. */
    private static final class Rule {
        String countryCode;
        int ibanLength;
        String bbanStructure;
        char[] classPerPosition;   // expanded once, indexed per character
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> opt = new HashMap<>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--") && i + 1 < args.length) {
                opt.put(args[i].substring(2), args[i + 1]);
                i++;
            }
        }
        if (!opt.containsKey("rules") || !opt.containsKey("ibans")) {
            System.err.println("usage: --rules <ref01.jsonl> --ibans <file> "
                             + "[--out <file>]");
            System.exit(2);
        }

        Map<String, Rule> rules = loadRules(opt.get("rules"));

        // Every line is one input, and every line carries a leading marker
        // so that an empty IBAN survives the round trip.
        //
        // The first version skipped empty lines. An empty string is a
        // perfectly good thing to ask a validator about - RUN-A answers it
        // INVALID - and skipping it meant RUN-B silently returned fewer
        // answers than it was asked for. A validator that drops an input it
        // does not recognise is the "counter that counts what it knows"
        // failure in CLAUDE.md section 10.
        List<String> inputs = new ArrayList<>();
        for (String line : Files.readAllLines(Path.of(opt.get("ibans")),
                                              StandardCharsets.UTF_8)) {
            if (line.isEmpty()) {
                throw new IOException("input line is missing its marker");
            }
            inputs.add(line.substring(1));
        }

        StringBuilder out = new StringBuilder();
        for (String raw : inputs) {
            out.append(toJson(validate(raw, rules))).append('\n');
        }

        if (opt.containsKey("out")) {
            Files.writeString(Path.of(opt.get("out")), out.toString(),
                              StandardCharsets.UTF_8);
        } else {
            System.out.print(out);
        }
        System.exit(0);
    }

    // ------------------------------------------------------------ rules
    private static Map<String, Rule> loadRules(String path) throws IOException {
        Map<String, Rule> rules = new LinkedHashMap<>();
        try (BufferedReader r = Files.newBufferedReader(Path.of(path),
                                                        StandardCharsets.UTF_8)) {
            String line;
            while ((line = r.readLine()) != null) {
                line = line.trim();
                if (line.isEmpty()) {
                    continue;
                }
                Rule rule = new Rule();
                rule.countryCode = jsonString(line, "country_code");
                rule.bbanStructure = jsonString(line, "bban_structure");
                rule.ibanLength = jsonInt(line, "iban_length");
                rule.classPerPosition = expandStructure(rule.bbanStructure);
                rules.put(rule.countryCode, rule);
            }
        }
        if (rules.isEmpty()) {
            throw new IOException("REF-01 rules are empty: " + path);
        }
        return rules;
    }

    /**
     * Expand `4!n4!n12!c` into one character class per BBAN position.
     *
     * RUN-A keeps the tokens and walks them. This flattens them once, so the
     * per-character test is an array index rather than a loop over tokens.
     * The length parse consumes every digit: a parser that read only the
     * first digit of `12!c` would silently build a structure of the wrong
     * length and accept the wrong strings.
     */
    private static char[] expandStructure(String structure) throws IOException {
        StringBuilder expanded = new StringBuilder();
        int i = 0;
        while (i < structure.length()) {
            int start = i;
            while (i < structure.length()
                   && Character.isDigit(structure.charAt(i))) {
                i++;
            }
            if (i == start) {
                throw new IOException("structure token has no length: " + structure);
            }
            int length = Integer.parseInt(structure.substring(start, i));
            if (i >= structure.length() || structure.charAt(i) != '!') {
                throw new IOException("structure token is not fixed-length: "
                                    + structure);
            }
            i++;
            if (i >= structure.length()) {
                throw new IOException("structure token has no class: " + structure);
            }
            char cls = structure.charAt(i);
            if (!CLASSES.containsKey(cls)) {
                throw new IOException("unknown character class " + cls
                                    + " in " + structure);
            }
            i++;
            for (int k = 0; k < length; k++) {
                expanded.append(cls);
            }
        }
        if (expanded.length() == 0) {
            throw new IOException("empty structure: " + structure);
        }
        return expanded.toString().toCharArray();
    }

    // -------------------------------------------------------- validation
    private static String normalize(String value) {
        StringBuilder sb = new StringBuilder(value.length());
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (SEPARATORS.indexOf(c) < 0) {
                sb.append(c);
            }
        }
        return sb.toString().trim().toUpperCase();
    }

    /**
     * MOD97-10 by full expansion and one big-integer modulus.
     *
     * Structurally different from RUN-A's streaming fold on purpose. The
     * arithmetic result must be identical; the route to it is not.
     */
    private static int mod97Expanded(String rearranged) {
        StringBuilder digits = new StringBuilder(rearranged.length() * 2);
        for (int i = 0; i < rearranged.length(); i++) {
            char c = rearranged.charAt(i);
            if (c >= '0' && c <= '9') {
                digits.append(c);
            } else {
                digits.append(Integer.toString(c - 55));
            }
        }
        return new BigInteger(digits.toString()).mod(NINETY_SEVEN).intValue();
    }

    private static Map<String, Object> validate(String raw, Map<String, Rule> rules) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("input", raw);
        out.put("normalization", NORMALIZATION);
        out.put("run_phase", "RUN-B");
        out.put("method", "JAVA_BIGINTEGER_MOD97_10_WITH_REF01_RULES");

        String iban = normalize(raw);
        out.put("normalized", iban);

        if (iban.length() < 4) {
            return finish(out, "INVALID", "SHORTER_THAN_FOUR_CHARACTERS");
        }
        for (int i = 0; i < iban.length(); i++) {
            char c = iban.charAt(i);
            boolean ok = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z');
            if (!ok) {
                return finish(out, "INVALID", "ILLEGAL_CHARACTER:'" + c + "'");
            }
        }

        String country = iban.substring(0, 2);
        if (!Character.isLetter(country.charAt(0))
            || !Character.isLetter(country.charAt(1))) {
            return finish(out, "INVALID", "COUNTRY_CODE_NOT_ALPHABETIC");
        }
        out.put("country", country);

        Rule rule = rules.get(country);
        if (rule == null) {
            return finish(out, "INVALID", "UNKNOWN_COUNTRY_CODE");
        }
        if (!Character.isDigit(iban.charAt(2)) || !Character.isDigit(iban.charAt(3))) {
            return finish(out, "INVALID", "CHECK_DIGITS_NOT_NUMERIC");
        }
        if (iban.length() != rule.ibanLength) {
            return finish(out, "INVALID",
                          "LENGTH_" + iban.length() + "_EXPECTED_" + rule.ibanLength);
        }

        String bban = iban.substring(4);
        if (bban.length() != rule.classPerPosition.length) {
            return finish(out, "INVALID",
                          "BBAN_STRUCTURE:length " + bban.length()
                        + " does not match structure length "
                        + rule.classPerPosition.length);
        }
        for (int i = 0; i < bban.length(); i++) {
            char cls = rule.classPerPosition[i];
            if (CLASSES.get(cls).indexOf(bban.charAt(i)) < 0) {
                return finish(out, "INVALID",
                              "BBAN_STRUCTURE:character '" + bban.charAt(i)
                            + "' at position " + (i + 1) + " is not " + cls);
            }
        }

        int remainder = mod97Expanded(iban.substring(4) + iban.substring(0, 4));
        out.put("mod97_remainder", Integer.valueOf(remainder));
        if (remainder != 1) {
            return finish(out, "INVALID",
                          "MOD97_10_REMAINDER_" + remainder + "_EXPECTED_1");
        }
        return finish(out, "VALID", "ALL_REF01_RULES_SATISFIED");
    }

    private static Map<String, Object> finish(Map<String, Object> out,
                                              String result, String reason) {
        out.put("result", result);
        out.put("reason", reason);
        return out;
    }

    // ------------------------------------------------------------- json
    /** Minimal reader for the flat, known corpus format. */
    private static String jsonString(String line, String key) throws IOException {
        String needle = "\"" + key + "\":";
        int i = line.indexOf(needle);
        if (i < 0) {
            throw new IOException("key " + key + " not present");
        }
        i += needle.length();
        while (i < line.length() && line.charAt(i) == ' ') {
            i++;
        }
        if (line.charAt(i) != '"') {
            throw new IOException("value of " + key + " is not a string");
        }
        i++;
        StringBuilder sb = new StringBuilder();
        while (i < line.length() && line.charAt(i) != '"') {
            char c = line.charAt(i);
            if (c == '\\' && i + 1 < line.length()) {
                i++;
                c = line.charAt(i);
            }
            sb.append(c);
            i++;
        }
        return sb.toString();
    }

    private static int jsonInt(String line, String key) throws IOException {
        String needle = "\"" + key + "\":";
        int i = line.indexOf(needle);
        if (i < 0) {
            throw new IOException("key " + key + " not present");
        }
        i += needle.length();
        while (i < line.length() && line.charAt(i) == ' ') {
            i++;
        }
        int start = i;
        while (i < line.length() && (Character.isDigit(line.charAt(i))
                                     || line.charAt(i) == '-')) {
            i++;
        }
        if (start == i) {
            throw new IOException("value of " + key + " is not a number");
        }
        return Integer.parseInt(line.substring(start, i));
    }

    private static String toJson(Map<String, Object> map) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Object> e : map.entrySet()) {
            if (!first) {
                sb.append(',');
            }
            first = false;
            sb.append('"').append(e.getKey()).append("\":");
            Object v = e.getValue();
            if (v instanceof Number) {
                sb.append(v);
            } else {
                sb.append('"').append(escape(String.valueOf(v))).append('"');
            }
        }
        return sb.append('}').toString();
    }

    private static String escape(String s) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' || c == '\\') {
                sb.append('\\').append(c);
            } else if (c == '\n') {
                sb.append("\\n");
            } else if (c < 0x20) {
                sb.append(String.format("\\u%04x", (int) c));
            } else {
                sb.append(c);
            }
        }
        return sb.toString();
    }

    private WpnoIbanValidateRunB() { }
}
