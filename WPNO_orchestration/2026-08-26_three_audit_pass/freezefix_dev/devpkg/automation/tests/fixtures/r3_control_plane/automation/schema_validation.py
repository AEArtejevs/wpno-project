"""A small, strict JSON validator.

Standard library only, so no jsonschema dependency. It supports the subset the
package's schemas actually use, and it is strict by default:

- additionalProperties defaults to false, not true;
- an unknown keyword in a schema is an error, not something to ignore;
- type mismatches are errors even when a value would coerce.

A validator that silently ignores what it does not understand gives the same
answer for a correct document and a malformed one.
"""

import json
import os
import re

SUPPORTED = {
    "type", "properties", "required", "additionalProperties", "items",
    "enum", "minItems", "maxItems", "minLength", "maxLength", "pattern",
    "minimum", "maximum", "const", "description", "title", "$schema", "$id",
    "definitions", "$ref", "uniqueItems",
}

TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


class SchemaError(Exception):
    """The schema itself is wrong."""


class ValidationError(Exception):
    """The document is wrong. The message carries the JSON pointer."""


def _check_schema_keywords(schema, where):
    for key in schema:
        if key not in SUPPORTED:
            raise SchemaError("unsupported schema keyword %r at %s" % (key, where))


def _resolve(ref, root):
    if not ref.startswith("#/"):
        raise SchemaError("only local refs are supported: %r" % ref)
    node = root
    for part in ref[2:].split("/"):
        if part not in node:
            raise SchemaError("unresolvable ref %r" % ref)
        node = node[part]
    return node


def _validate(value, schema, root, pointer):
    _check_schema_keywords(schema, pointer or "/")

    if "$ref" in schema:
        return _validate(value, _resolve(schema["$ref"], root), root, pointer)

    if "const" in schema and value != schema["const"]:
        raise ValidationError("%s: expected const %r, got %r"
                              % (pointer or "/", schema["const"], value))

    if "type" in schema:
        expected = schema["type"]
        names = expected if isinstance(expected, list) else [expected]
        ok = False
        for name in names:
            if name not in TYPES:
                raise SchemaError("unknown type %r at %s" % (name, pointer or "/"))
            # bool is a subclass of int in Python; an integer field must not
            # accept True.
            if name in ("integer", "number") and isinstance(value, bool):
                continue
            if isinstance(value, TYPES[name]):
                ok = True
                break
        if not ok:
            raise ValidationError("%s: expected type %r, got %s"
                                  % (pointer or "/", expected, type(value).__name__))

    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError("%s: %r not in enum %r"
                              % (pointer or "/", value, schema["enum"]))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise ValidationError("%s: shorter than minLength" % (pointer or "/"))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValidationError("%s: longer than maxLength" % (pointer or "/"))
        if "pattern" in schema:
            if not re.search(schema["pattern"], value):
                raise ValidationError("%s: does not match pattern %r"
                                      % (pointer or "/", schema["pattern"]))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError("%s: below minimum" % (pointer or "/"))
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError("%s: above maximum" % (pointer or "/"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise ValidationError("%s: fewer than minItems" % (pointer or "/"))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValidationError("%s: more than maxItems" % (pointer or "/"))
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(set(seen)) != len(seen):
                raise ValidationError("%s: items are not unique" % (pointer or "/"))
        if "items" in schema:
            for i, item in enumerate(value):
                _validate(item, schema["items"], root, "%s/%d" % (pointer, i))

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                raise ValidationError("%s: missing required property %r"
                                      % (pointer or "/", name))
        # Strict by default. An extra property is a defect, not a courtesy.
        if schema.get("additionalProperties", False) is False:
            extra = sorted(set(value) - set(props))
            if extra:
                raise ValidationError("%s: unexpected properties %r"
                                      % (pointer or "/", extra))
        for name, sub in props.items():
            if name in value:
                _validate(value[name], sub, root, "%s/%s" % (pointer, name))

    return True


def validate(document, schema):
    return _validate(document, schema, schema, "")


def load_schema(name):
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "schemas", name)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def validate_named(document, schema_name):
    return validate(document, load_schema(schema_name))


def parse_strict(text):
    """json.loads that rejects duplicate keys.

    The stdlib keeps the last of a duplicated pair silently. In a document
    carrying an approval or a hash, a silently discarded first value is a way
    to smuggle one past a reader.
    """
    def hook(pairs):
        seen = {}
        for key, value in pairs:
            if key in seen:
                raise ValidationError("duplicate key in JSON: %r" % key)
            seen[key] = value
        return seen

    return json.loads(text, object_pairs_hook=hook)
