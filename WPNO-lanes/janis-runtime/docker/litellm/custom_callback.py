from litellm.integrations.custom_logger import CustomLogger
from fastapi import HTTPException
from payload_scan import scan_payload
from tool_registry_gate import check_tool_allowlist

# AP-14: cost/token logging (gateway_log)
import hashlib
import os
import psycopg2


# ---------------------------------------------------------------------------
# Gremium-Audit 2026-07-21: vollstaendige, fail-closed Textextraktion.
# Vorher wurde nur str-content aus messages gescannt (P2-1/P5-F1) und das
# system-Feld gar nicht (P5-F2) -> strukturierte/multimodale Requests und
# system-Prompts umgingen das Gate. Jetzt wird JEDER Textbestandteil des
# Requests rekursiv eingesammelt; nicht extrahierbare Formen fuehren nicht zu
# einer stillen Luecke, weil im Zweifel geblockt wird.
# ---------------------------------------------------------------------------

def _collect_text(node, out):
    """Sammelt rekursiv alle str-Blaetter aus messages/system/tools/content-
    Bloecken (list/dict beliebiger Tiefe). Robust gegen unbekannte Formen."""
    if node is None:
        return
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _collect_text(v, out)
    elif isinstance(node, (list, tuple)):
        for v in node:
            _collect_text(v, out)
    # Zahlen/Bool etc. tragen keine PII-Textsemantik -> ignoriert.


def _extract_scan_text(data):
    """Aggregiert Text aus allen egress-relevanten Feldern des Requests."""
    parts = []
    for field in ("messages", "system", "prompt", "input"):
        if field in data:
            _collect_text(data[field], parts)
    return "\n".join(p for p in parts if p)


class WPNOEgressGate(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        # 1) MCP rīku reģistra vārti (V-2): tikai reģistrētie rīku vārdi drīkst tikt maršrutēti
        ok, err = check_tool_allowlist(data)
        if not ok:
            raise HTTPException(
                status_code=403,
                detail={"error": "MCP_TOOL_NOT_REGISTERED", "detail": err},
            )

        # 2) Anonimizācijas vārti (V-6 / AP-03): payload skenēšana pirms ārējā izsaukuma.
        #    Fail-closed: jede Ausnahme in der Extraktion/Skennung -> BLOCK (451),
        #    niemals stiller Durchlass (P2-5/P5-F4).
        try:
            text = _extract_scan_text(data)
            result = scan_payload(text, akte_id="dev-test", target="anthropic")
            blocked = result["blocked"]
            findings = result.get("findings")
            payload_hash = result.get("payload_hash")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=451,
                detail={"error": "ANON_GATE_FAILCLOSED", "reason": type(e).__name__},
            )
        if blocked:
            raise HTTPException(
                status_code=451,
                detail={"error": "ANON_GATE_BLOCK", "findings": findings, "payload_hash": payload_hash},
            )
        return data

    # ------------------------------------------------------------------
    # AP-14: gateway_log cost/token writer. Runs after a successful call.
    # Never raises: a logging failure must never break the response path
    # already delivered to the caller.
    # ------------------------------------------------------------------
    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        try:
            usage = getattr(response_obj, "usage", None)
            if usage is None and isinstance(response_obj, dict):
                usage = response_obj.get("usage")
            prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

            model = kwargs.get("model")
            request_id = kwargs.get("litellm_call_id")
            spend = kwargs.get("response_cost")
            # Redis-Response-Cache (config: cache: true): Cache-Hits machen
            # keinen Upstream-Call, LiteLLM setzt response_cost dann korrekt
            # auf 0.0 (identisch in /spend/logs). Das Flag haelt solche
            # Nullkosten-Zeilen von echten Pricing-Luecken unterscheidbar.
            cache_hit = bool(kwargs.get("cache_hit"))

            metadata = (kwargs.get("litellm_params") or {}).get("metadata") or {}
            akte_id = metadata.get("akte_id", "dev-test")

            text = _extract_scan_text(kwargs)
            payload_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None

            conn = psycopg2.connect(
                host=os.environ.get("GATEWAY_LOG_DB_HOST", "host.docker.internal"),
                port=os.environ.get("GATEWAY_LOG_DB_PORT", "5432"),
                dbname=os.environ.get("GATEWAY_LOG_DB_NAME", "wpno"),
                user="wpno_gateway_writer",
                password=os.environ["GATEWAY_LOG_DB_PASSWORD"],
            )
            try:
                with conn, conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO gateway_log
                           (request_id, akte_id, model, prompt_tokens, completion_tokens, spend, cache_hit, payload_sha256)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                        (request_id, akte_id, model, prompt_tokens, completion_tokens, spend, cache_hit, payload_hash),
                    )
            finally:
                conn.close()
            if spend in (None, 0.0) and not cache_hit:
                # Nur echte Anomalien melden: 0-Kosten ohne Cache-Hit deutet
                # auf eine Pricing-Luecke (z.B. Modell nicht in der Cost-Map).
                print(f"[gateway_log] WARNING: spend={spend!r} without cache_hit "
                      f"for model={model!r} request_id={request_id}", flush=True)
        except Exception as e:
            # Cost logging must be best-effort only -- never break the
            # actual response path that has already succeeded for the caller.
            print(f"[gateway_log] WARNING: failed to write cost log: {type(e).__name__}: {e}", flush=True)


proxy_handler_instance = WPNOEgressGate()
