// WpnoCmsVerify - an independent detached-CMS verifier for L1-A31 and L1-A34.
//
// Independent of OpenSSL by construction: this program never launches a
// subprocess, and the only cryptography it performs comes from Bouncy Castle
// and the JDK. That is the whole point of it. RUN-B has to be able to
// disagree with RUN-A, and two runs of the same openssl binary cannot.
//
// Every input is explicit and named on the command line. Nothing is taken
// from a default store, an environment variable, or the certificate bag
// inside the CMS itself. In particular:
//
//   * the trust anchor is the single certificate given as --root, and the
//     PKIX parameters are built from that one anchor and nothing else;
//   * revocation checking is disabled rather than attempted, because it would
//     need the network and this program must not use it;
//   * the signer certificate is the one given as --leaf. The CMS carries its
//     own certificates; using those would mean verifying a signature against
//     whatever the signature brought with it.
//
// What is checked, and reported separately so a failure names itself:
//
//   1. the CMS parses as ContentInfo/SignedData
//   2. it is detached (no encapsulated content)
//   3. exactly one SignerInfo, and its SID matches the supplied leaf
//   4. signed attributes are present
//   5. the messageDigest signed attribute equals the digest of --content
//   6. the signature verifies over those signed attributes
//   7. leaf -> intermediate -> root builds and validates against the
//      explicit anchor at the given validation time
//   8. every certificate in the path is valid at that time
//
// Exit code 0 only if all of them hold. Any failure exits non-zero, and the
// JSON on stdout says which check failed.

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.Security;
import java.security.cert.CertPath;
import java.security.cert.CertPathValidator;
import java.security.cert.CertificateFactory;
import java.security.cert.PKIXCertPathValidatorResult;
import java.security.cert.PKIXParameters;
import java.security.cert.TrustAnchor;
import java.security.cert.X509Certificate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.Date;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.bouncycastle.asn1.ASN1Encodable;
import org.bouncycastle.asn1.ASN1OctetString;
import org.bouncycastle.asn1.cms.Attribute;
import org.bouncycastle.asn1.cms.AttributeTable;
import org.bouncycastle.asn1.cms.CMSAttributes;
import org.bouncycastle.cert.X509CertificateHolder;
import org.bouncycastle.cms.CMSException;
import org.bouncycastle.cms.CMSProcessableByteArray;
import org.bouncycastle.cms.CMSSignedData;
import org.bouncycastle.cms.SignerInformation;
import org.bouncycastle.cms.jcajce.JcaSimpleSignerInfoVerifierBuilder;
import org.bouncycastle.jce.provider.BouncyCastleProvider;

public final class WpnoCmsVerify {

    // Bounded on purpose. A detached CMS and its content are audit inputs of
    // known size; an unbounded read is a denial-of-service surface and a way
    // to exhaust the heap on a malformed file.
    private static final long MAX_CMS_BYTES = 8L * 1024 * 1024;
    private static final long MAX_CONTENT_BYTES = 256L * 1024 * 1024;
    private static final long MAX_CERT_BYTES = 64L * 1024;

    private final Map<String, Object> report = new LinkedHashMap<String, Object>();
    private final List<String> failures = new ArrayList<String>();

    public static void main(String[] args) {
        WpnoCmsVerify verifier = new WpnoCmsVerify();
        int code;
        try {
            code = verifier.run(args);
        } catch (Throwable t) {
            verifier.report.put("fatal_error", t.getClass().getName() + ": " + t.getMessage());
            verifier.failures.add("FATAL");
            code = 3;
        }
        verifier.report.put("failed_checks", verifier.failures);
        verifier.report.put("verified", verifier.failures.isEmpty());
        System.out.println(toJson(verifier.report));
        System.exit(code);
    }

    private void check(String name, boolean ok, Object detail) {
        Map<String, Object> node = new LinkedHashMap<String, Object>();
        node.put("passed", Boolean.valueOf(ok));
        node.put("detail", detail);
        report.put(name, node);
        if (!ok) {
            failures.add(name);
        }
    }

    private int run(String[] args) throws Exception {
        Map<String, String> opt = parseArgs(args);
        for (String required : new String[] {"cms", "content", "leaf", "root", "validation-time"}) {
            if (!opt.containsKey(required)) {
                report.put("usage_error", "missing required option --" + required);
                failures.add("ARGUMENTS");
                return 2;
            }
        }

        // The provider is added explicitly and by instance. No provider is
        // taken from the JVM's configured list by name alone.
        Security.addProvider(new BouncyCastleProvider());

        report.put("verifier", "WpnoCmsVerify");
        report.put("implementation", "Bouncy Castle + JDK PKIX");
        report.put("openssl_used", Boolean.FALSE);
        report.put("subprocess_launched", Boolean.FALSE);
        report.put("network_used", Boolean.FALSE);
        report.put("system_default_trust_used", Boolean.FALSE);
        report.put("java_version", System.getProperty("java.version"));
        report.put("bc_version", String.valueOf(new BouncyCastleProvider().getVersionStr()));

        long epoch = Long.parseLong(opt.get("validation-time"));
        Date validationTime = new Date(epoch * 1000L);
        report.put("validation_time_epoch", Long.valueOf(epoch));
        report.put("validation_time_utc", validationTime.toInstant().toString());

        byte[] cmsBytes = read(opt.get("cms"), MAX_CMS_BYTES);
        byte[] content = read(opt.get("content"), MAX_CONTENT_BYTES);
        report.put("cms_sha256", hex(sha256(cmsBytes)));
        report.put("content_sha256", hex(sha256(content)));
        report.put("content_bytes", Integer.valueOf(content.length));

        X509Certificate leaf = readCert(opt.get("leaf"));
        X509Certificate root = readCert(opt.get("root"));
        X509Certificate intermediate = opt.containsKey("intermediate")
                ? readCert(opt.get("intermediate")) : null;
        report.put("leaf_subject", leaf.getSubjectX500Principal().getName());
        report.put("root_subject", root.getSubjectX500Principal().getName());
        if (intermediate != null) {
            report.put("intermediate_subject", intermediate.getSubjectX500Principal().getName());
        }

        // --- 1. parse ----------------------------------------------------
        CMSSignedData signed;
        try {
            signed = new CMSSignedData(new CMSProcessableByteArray(content), cmsBytes);
            check("cms_parses", true, "SignedData parsed");
        } catch (CMSException e) {
            check("cms_parses", false, String.valueOf(e.getMessage()));
            return 1;
        }

        // --- 2. detached --------------------------------------------------
        boolean detached = signed.isDetachedSignature();
        check("is_detached_signature", detached,
              detached ? "no encapsulated content, content supplied separately"
                       : "the CMS encapsulates its own content");

        // --- 3. one signer, matching the supplied leaf --------------------
        Collection<SignerInformation> signers = signed.getSignerInfos().getSigners();
        check("exactly_one_signer", signers.size() == 1,
              "signer count " + signers.size());
        if (signers.isEmpty()) {
            return 1;
        }
        SignerInformation signer = signers.iterator().next();

        X509CertificateHolder holder = new X509CertificateHolder(leaf.getEncoded());
        boolean sidMatches = signer.getSID().match(holder);
        check("signer_id_matches_supplied_leaf", sidMatches,
              sidMatches ? "SignerInfo SID matches --leaf"
                         : "SignerInfo SID does not identify the supplied leaf");

        // --- 4. signed attributes present ---------------------------------
        AttributeTable signedAttrs = signer.getSignedAttributes();
        check("signed_attributes_present", signedAttrs != null,
              signedAttrs == null ? "absent"
                                  : String.valueOf(signedAttrs.toASN1EncodableVector().size()) + " attributes");

        // --- 5. messageDigest equals the digest of --content --------------
        if (signedAttrs != null) {
            Attribute md = signedAttrs.get(CMSAttributes.messageDigest);
            if (md == null) {
                check("message_digest_attribute_present", false, "absent");
            } else {
                check("message_digest_attribute_present", true, "present");
                ASN1Encodable value = md.getAttrValues().getObjectAt(0);
                byte[] declared = ASN1OctetString.getInstance(value).getOctets();
                String algo = signer.getDigestAlgOID();
                byte[] actual = digest(algo, content);
                boolean equal = Arrays.equals(declared, actual);
                Map<String, Object> detail = new LinkedHashMap<String, Object>();
                detail.put("digest_algorithm_oid", algo);
                detail.put("declared_in_signature", hex(declared));
                detail.put("computed_over_supplied_content", hex(actual));
                check("message_digest_matches_content", equal, detail);
            }
        }

        // --- 6. signature over the signed attributes ----------------------
        boolean sigOk;
        String sigDetail;
        try {
            sigOk = signer.verify(new JcaSimpleSignerInfoVerifierBuilder()
                    .setProvider("BC").build(leaf));
            sigDetail = sigOk ? "signature verifies against --leaf"
                              : "signature does not verify";
        } catch (Exception e) {
            sigOk = false;
            sigDetail = e.getClass().getSimpleName() + ": " + e.getMessage();
        }
        check("signature_verifies", sigOk, sigDetail);

        // --- 7 & 8. path validation against the explicit anchor -----------
        validatePath(leaf, intermediate, root, validationTime);

        return failures.isEmpty() ? 0 : 1;
    }

    private void validatePath(X509Certificate leaf, X509Certificate intermediate,
                              X509Certificate root, Date when) {
        List<X509Certificate> chain = new ArrayList<X509Certificate>();
        chain.add(leaf);
        if (intermediate != null) {
            chain.add(intermediate);
        }
        // The root is the anchor, not a path element: PKIX takes the anchor
        // separately and a path that also contains it is rejected.
        try {
            CertificateFactory cf = CertificateFactory.getInstance("X.509");
            CertPath path = cf.generateCertPath(chain);

            Set<TrustAnchor> anchors = new HashSet<TrustAnchor>();
            anchors.add(new TrustAnchor(root, null));

            PKIXParameters params = new PKIXParameters(anchors);
            // No network. Revocation is not attempted rather than silently
            // skipped: the flag is set explicitly and reported.
            params.setRevocationEnabled(false);
            params.setDate(when);

            CertPathValidator validator = CertPathValidator.getInstance("PKIX");
            PKIXCertPathValidatorResult result =
                    (PKIXCertPathValidatorResult) validator.validate(path, params);

            Map<String, Object> detail = new LinkedHashMap<String, Object>();
            detail.put("anchor_subject",
                       result.getTrustAnchor().getTrustedCert().getSubjectX500Principal().getName());
            detail.put("path_length", Integer.valueOf(chain.size()));
            detail.put("revocation_checking", "DISABLED_EXPLICITLY_NO_NETWORK");
            detail.put("anchors_supplied", Integer.valueOf(1));
            check("certificate_path_validates_against_explicit_anchor", true, detail);
        } catch (Exception e) {
            check("certificate_path_validates_against_explicit_anchor", false,
                  e.getClass().getSimpleName() + ": " + e.getMessage());
        }

        // Validity at the selected time, reported per certificate so an
        // expiry names the certificate that expired.
        List<X509Certificate> all = new ArrayList<X509Certificate>(chain);
        all.add(root);
        boolean allValid = true;
        Map<String, Object> validity = new LinkedHashMap<String, Object>();
        for (X509Certificate c : all) {
            String name = c.getSubjectX500Principal().getName();
            try {
                c.checkValidity(when);
                validity.put(name, "VALID_AT_VALIDATION_TIME");
            } catch (Exception e) {
                validity.put(name, e.getClass().getSimpleName());
                allValid = false;
            }
        }
        check("all_certificates_valid_at_validation_time", allValid, validity);
    }

    // ---------------------------------------------------------------- io
    private static byte[] read(String path, long limit) throws IOException {
        File f = new File(path);
        if (!f.isFile()) {
            throw new IOException("not a regular file: " + path);
        }
        long size = f.length();
        if (size > limit) {
            throw new IOException("input exceeds its bound (" + size + " > " + limit + "): " + path);
        }
        return Files.readAllBytes(Path.of(path));
    }

    private static X509Certificate readCert(String path) throws Exception {
        byte[] raw = read(path, MAX_CERT_BYTES);
        CertificateFactory cf = CertificateFactory.getInstance("X.509");
        InputStream in = new ByteArrayInputStream(raw);
        return (X509Certificate) cf.generateCertificate(in);
    }

    private static byte[] sha256(byte[] data) throws Exception {
        return MessageDigest.getInstance("SHA-256").digest(data);
    }

    private static byte[] digest(String oid, byte[] data) throws Exception {
        return MessageDigest.getInstance(oid, "BC").digest(data);
    }

    private static String hex(byte[] b) {
        StringBuilder sb = new StringBuilder(b.length * 2);
        for (byte x : b) {
            sb.append(Character.forDigit((x >> 4) & 0xf, 16));
            sb.append(Character.forDigit(x & 0xf, 16));
        }
        return sb.toString();
    }

    private static Map<String, String> parseArgs(String[] args) {
        Map<String, String> out = new HashMap<String, String>();
        for (int i = 0; i < args.length; i++) {
            if (args[i].startsWith("--") && i + 1 < args.length) {
                out.put(args[i].substring(2), args[i + 1]);
                i++;
            }
        }
        return out;
    }

    // ---------------------------------------------------------------- json
    @SuppressWarnings("unchecked")
    private static String toJson(Object o) {
        StringBuilder sb = new StringBuilder();
        writeJson(o, sb);
        return sb.toString();
    }

    @SuppressWarnings("unchecked")
    private static void writeJson(Object o, StringBuilder sb) {
        if (o == null) {
            sb.append("null");
        } else if (o instanceof Map) {
            sb.append('{');
            boolean first = true;
            for (Map.Entry<String, Object> e : ((Map<String, Object>) o).entrySet()) {
                if (!first) { sb.append(','); }
                first = false;
                writeString(e.getKey(), sb);
                sb.append(':');
                writeJson(e.getValue(), sb);
            }
            sb.append('}');
        } else if (o instanceof Collection) {
            sb.append('[');
            boolean first = true;
            for (Object e : (Collection<Object>) o) {
                if (!first) { sb.append(','); }
                first = false;
                writeJson(e, sb);
            }
            sb.append(']');
        } else if (o instanceof Boolean || o instanceof Number || o instanceof BigInteger) {
            sb.append(o.toString());
        } else {
            writeString(o.toString(), sb);
        }
    }

    private static void writeString(String s, StringBuilder sb) {
        sb.append('"');
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
        sb.append('"');
    }

    private WpnoCmsVerify() { }
}
