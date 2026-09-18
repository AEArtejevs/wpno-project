"""
WPNO -- MCP rīku reģistra vārti LiteLLM gateway (V-2 WP: 'Configure LiteLLM
config.yaml such that only MCP tool names listed in the registry are routed
to allowed models and calls are logged and capped').

Ielādē mcp.registry.json un pārbauda katra ienākošā pieprasījuma 'tools'
lauku: ja pieprasījumā minēts rīka vārds, kura nav reģistrā, izsaukums
tiek noraidīts ar HTTP 403 PIRMS tas sasniedz modeli.
"""
import json
from pathlib import Path

REGISTRY_PATH = Path(__file__).parent / "mcp.registry.json"

def _load_registered_tool_names():
    # P2-7: Registry-Datei fehlend/korrupt darf das Modul (und damit den
    # gesamten Egress-Callback) nicht am Import scheitern lassen. Bei Fehler
    # leere Allowlist -> fail-closed (jeder Tool-Aufruf gilt als nicht registriert).
    try:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    names = set()
    for srv_cfg in registry.get("servers", {}).values():
        if isinstance(srv_cfg, dict):
            tools = srv_cfg.get("tools", {})
            if isinstance(tools, dict):
                names.update(tools.keys())
    return names

REGISTERED_TOOLS = _load_registered_tool_names()

def check_tool_allowlist(data: dict):
    """
    data: LiteLLM pre_call_hook payload. Skata 'tools' lauku (Anthropic/OpenAI
    tool_use formats: [{"name": ..., ...}]).
    Atgriezt (True, None) ja OK, citadi (False, "kluda_teksts").

    Fail-closed (P2-6): unparsebare/nicht-dict Tool-Eintraege gelten als NICHT
    registriert und werden geblockt, statt eine Ausnahme zu werfen oder still
    durchzulassen.
    """
    tools = data.get("tools") or []
    if not isinstance(tools, (list, tuple)):
        return False, "MCP_TOOL_MALFORMED: 'tools' is not a list"
    unregistered = []
    for t in tools:
        if isinstance(t, dict):
            fn = t.get("function")
            name = t.get("name") or (fn.get("name") if isinstance(fn, dict) else None)
        else:
            name = None
        if name is None:
            unregistered.append(f"<unparseable:{type(t).__name__}>")
        elif name not in REGISTERED_TOOLS:
            unregistered.append(name)
    if unregistered:
        return False, f"MCP_TOOL_NOT_REGISTERED: {unregistered} not in mcp.registry.json"
    return True, None
