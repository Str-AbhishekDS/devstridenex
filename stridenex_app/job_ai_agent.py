"""
Job description generator with a vector-database semantic cache.

Flow:
  1. Embed the incoming role query (Voyage AI).
  2. Search Qdrant for a semantically close previously-generated description.
  3. If a close match exists (cosine similarity >= SIMILARITY_THRESHOLD) -> return it,
     skipping the LLM call entirely.
  4. Otherwise -> call Claude to generate a new description, embed it, store it in
     Qdrant for next time, and return it.

Required in site_config.json:
  "anthropic_api_key": "sk-ant-...",
  "voyage_api_key": "pa-...",
  "qdrant_url": "http://localhost:6333"

Qdrant quickstart (Docker):
  docker run -p 6333:6333 qdrant/qdrant
"""

import hashlib
import json

import frappe
import requests

VOYAGE_EMBED_URL = "https://api.voyageai.com/v1/embeddings"
EMBED_MODEL = "voyage-3.5"
COLLECTION = "job_descriptions"
SIMILARITY_THRESHOLD = 0.90  # cosine similarity cutoff for treating a match as "the same role"


# ---------- embeddings ----------

def _get_embedding(text: str) -> list:
    api_key = frappe.conf.get("voyage_api_key")
    if not api_key:
        frappe.throw("Missing 'voyage_api_key' in site_config.json")

    resp = requests.post(
        VOYAGE_EMBED_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"input": [text], "model": EMBED_MODEL, "input_type": "query"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


# ---------- vector db (Qdrant) ----------

def _qdrant_base() -> str:
    base = frappe.conf.get("qdrant_url")
    if not base:
        frappe.throw("Missing 'qdrant_url' in site_config.json")
    return base.rstrip("/")


def _ensure_collection(vector_size: int) -> None:
    base = _qdrant_base()
    check = requests.get(f"{base}/collections/{COLLECTION}", timeout=10)
    if check.status_code == 200:
        return
    create = requests.put(
        f"{base}/collections/{COLLECTION}",
        json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        timeout=10,
    )
    create.raise_for_status()


def _search_vector_db(embedding: list):
    base = _qdrant_base()
    resp = requests.post(
        f"{base}/collections/{COLLECTION}/points/search",
        json={"vector": embedding, "limit": 1, "with_payload": True},
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    hits = resp.json().get("result", [])
    if hits and hits[0]["score"] >= SIMILARITY_THRESHOLD:
        return hits[0]["payload"]
    return None


def _store_in_vector_db(role: str, embedding: list, data: dict) -> None:
    base = _qdrant_base()
    # deterministic id so re-generating the exact same role overwrites its old entry
    point_id = int(hashlib.sha256(role.lower().strip().encode()).hexdigest(), 16) % (10**12)
    resp = requests.put(
        f"{base}/collections/{COLLECTION}/points",
        json={"points": [{"id": point_id, "vector": embedding, "payload": {"role": role, **data}}]},
        timeout=10,
    )
    resp.raise_for_status()


# ---------- LLM generation (your original logic, unchanged) ----------

def _generate_with_claude(role: str) -> dict:
    api_key = frappe.conf.get("anthropic_api_key")
    if not api_key:
        frappe.throw("Missing 'anthropic_api_key' in site_config.json")

    system_prompt = (
        "You write concise, realistic job requisitions. Respond with ONLY a raw JSON object, "
        "no markdown fences, no commentary, matching exactly this shape:\n"
        '{"title": string, "basics": {"department": string, "level": string, '
        '"employment_type": string, "location": string}, "summary": string (2-3 sentences), '
        '"mandatory": string[] (5-8 concise items), "good_to_have": string[] (4-6 concise items)}\n'
        "Keep each list item under 12 words. Be specific to the role, not generic filler."
    )

    try:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": f"Role: {role}"}],
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        frappe.log_error(frappe.get_traceback(), "generate_job_description: API call failed")
        frappe.throw(f"Failed to reach AI service: {e}")

    payload = response.json()
    text_block = next((b for b in payload.get("content", []) if b.get("type") == "text"), None)
    if not text_block:
        frappe.throw("AI response contained no text content")

    raw_text = text_block["text"].strip()
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        frappe.log_error(raw_text, "generate_job_description: JSON parse failed")
        frappe.throw("Could not parse AI response as JSON")


# ---------- public endpoint ----------

@frappe.whitelist(allow_guest=False)
def generate_job_description(role: str = None):
    """
    Usage:
        GET /api/method/your_app.api.generate_job_description?role=Software%20Developer

    Returns the same JSON shape as before, plus a "_source" field:
        "_source": "vector_cache"  -> served from Qdrant, no LLM call made
        "_source": "generated"     -> freshly generated by Claude and cached for next time
    """
    role = (role or frappe.form_dict.get("role") or "").strip()
    if not role:
        frappe.throw("Query param 'role' is required, e.g. ?role=Software Developer")

    embedding = _get_embedding(role)
    _ensure_collection(vector_size=len(embedding))

    cached = _search_vector_db(embedding)
    if cached:
        cached["_source"] = "vector_cache"
        return cached

    data = _generate_with_claude(role)
    _store_in_vector_db(role, embedding, data)
    data["_source"] = "generated"
    return data