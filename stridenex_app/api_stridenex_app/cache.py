import json
import hashlib
from functools import wraps
import frappe


def make_cache_key(prefix: str, *args, **kwargs) -> str:
    """Stable cache key from any args/kwargs, namespaced by prefix."""
    raw = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    return f"api_cache:{prefix}:" + hashlib.md5(raw.encode()).hexdigest()


def cache_response(ttl=300, prefix=None):
    """
    Generic response cache for whitelisted API methods.
    Caches only successful (status 200) gen_response() payloads.

    Usage:
        @frappe.whitelist(allow_guest=True)
        @cache_response(ttl=180)
        def get_project_list(...):
            ...
    """
    def decorator(fn):
        cache_prefix = prefix or fn.__name__

        @wraps(fn)
        def wrapper(*args, **kwargs):
            cache_key = make_cache_key(cache_prefix, *args, **kwargs)

            cached = frappe.cache().get_value(cache_key)
            if cached is not None:
                try:
                    return json.loads(cached)
                except Exception:
                    frappe.cache().delete_value(cache_key)

            result = fn(*args, **kwargs)

            try:
                if isinstance(result, dict) and result.get("status") == 200:
                    frappe.cache().set_value(
                        cache_key,
                        json.dumps(result, default=str),
                        expires_in_sec=ttl
                    )
            except Exception:
                # never let caching break the actual response
                frappe.log_error(frappe.get_traceback(), "cache_response set failed")

            return result
        return wrapper
    return decorator


def clear_cache_prefix(prefix: str):
    """Invalidate all cached entries for a given function/prefix."""
    try:
        frappe.cache().delete_keys(f"api_cache:{prefix}:*")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "clear_cache_prefix failed")