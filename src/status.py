from __future__ import annotations
import sys
from .browser import _ensure_api_driver


def get_status() -> dict:
    """
    Navigate to a Carrefour page (ensures the browser is authenticated and on the
    right origin) then fetch /api/me and /api/cart directly via the browser's
    fetch() — same-origin, credentials included.
    """
    try:
        driver = _ensure_api_driver()

        if "www.carrefour.fr" not in driver.current_url:
            driver.get("https://www.carrefour.fr")

        driver.set_script_timeout(30)
        result = driver.execute_async_script("""
            var done = arguments[arguments.length - 1];
            function apiFetch(path) {
                return fetch('https://www.carrefour.fr' + path, {
                    method: 'GET',
                    credentials: 'include',
                    headers: {'Accept': 'application/json, */*', 'X-Requested-With': 'XMLHttpRequest'}
                }).then(function(r) {
                    return r.text().then(function(t) {
                        var d = null;
                        try { d = JSON.parse(t); } catch(e) { d = null; }
                        return {status: r.status, ok: r.ok, data: d, preview: t.slice(0,100)};
                    });
                }).catch(function(e) { return {error: e.toString()}; });
            }
            Promise.all([apiFetch('/api/me'), apiFetch('/api/cart')])
                .then(function(results) { done({me: results[0], cart: results[1]}); })
                .catch(function(e) { done({error: e.toString()}); });
        """)

        me_raw   = result.get("me") or {}
        cart_raw = result.get("cart") or {}
        print(f"[carrefour-mcp] /api/me  → status={me_raw.get('status')} ok={me_raw.get('ok')} preview={me_raw.get('preview','')[:100]}", file=sys.stderr)
        print(f"[carrefour-mcp] /api/cart → status={cart_raw.get('status')} ok={cart_raw.get('ok')}", file=sys.stderr)

        me        = me_raw.get("data") or {}
        cart_data = (cart_raw.get("data") or {}).get("cart") or cart_raw.get("data") or {}

        total_items = sum(
            p.get("counter", 0)
            for cat in cart_data.get("items", [])
            for p in cat.get("products", [])
        )

        connected = bool(
            me.get("sessionId") or me.get("customerId")
            or me.get("email") or me.get("firstName") or me.get("id")
        )

        return {
            "success": True,
            "status": {
                "connected": connected,
                "user":      f"{me.get('firstName','')} {me.get('lastName','')}".strip() or None,
                "nextSlot":  (me.get("slot") or {}).get("title"),
                "cartItems": total_items,
                "cartTotal": cart_data.get("totalAmount", 0),
            },
        }
    except Exception as e:
        return {
            "success": False,
            "status": {"connected": False, "cartItems": 0, "cartTotal": 0},
            "message": str(e),
        }
