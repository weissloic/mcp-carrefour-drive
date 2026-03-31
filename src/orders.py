from __future__ import annotations
import sys
from .browser import _ensure_api_driver, navigate_and_wait

BASE = "https://www.carrefour.fr"


def _fetch_api(driver, path: str) -> dict | list | None:
    """Direct authenticated fetch() from within the browser."""
    driver.set_script_timeout(20)
    return driver.execute_async_script("""
        var done = arguments[arguments.length - 1];
        fetch('https://www.carrefour.fr' + arguments[0], {
            credentials: 'include',
            headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(function(r) { return r.json(); })
        .then(done)
        .catch(function(e) { done(null); });
    """, path)


def get_order_history() -> dict:
    try:
        driver = _ensure_api_driver()
        # Navigate to the orders page first (sets context + cookies)
        navigate_and_wait(driver, f"{BASE}/mon-compte/mes-achats/en-ligne")
        data = _fetch_api(driver, "/api/user/orders")
        print(f"[carrefour-mcp] orders raw: {str(data)[:200]}", file=sys.stderr)

        orders = []
        for item in ((data or {}).get("data") or []):
            a = item.get("attributes") or item
            orders.append({
                "id":     str(a.get("orderNumber") or item.get("id") or ""),
                "date":   a.get("date") or "",
                "type":   a.get("serviceType") or "",
                "store":  (a.get("store") or {}).get("name") or "",
                "status": a.get("orderStatus") or "",
                "total":  a.get("totalAmount") or 0,
            })
        return {"success": True, "orders": orders}
    except Exception as e:
        return {"success": False, "orders": [], "message": str(e)}


def get_order_items(order_id: str) -> dict:
    try:
        driver = _ensure_api_driver()
        navigate_and_wait(driver, f"{BASE}/mon-compte/mes-achats/en-ligne/{order_id}")
        data = _fetch_api(driver, f"/api/user/orders/{order_id}")

        attrs = (data or {}).get("attributes") or ((data or {}).get("data") or {}).get("attributes") or {}
        cats  = (attrs.get("productList") or {}).get("categories") or []
        raw   = [p for cat in cats for p in (cat.get("products") or [])]

        items = []
        for i, item in enumerate(raw):
            a = item.get("attributes") or item
            items.append({
                "id":       a.get("ean") or a.get("id") or f"item-{i}",
                "name":     a.get("title") or a.get("shortTitle") or a.get("name") or "",
                "brand":    a.get("brand") or "",
                "quantity": a.get("pickedQuantity") or a.get("quantity") or a.get("qty") or 1,
                "price":    a.get("sellingPrice") or a.get("unitPrice") or a.get("price"),
                "image":    ((a.get("images") or {}).get("paths") or [None])[0],
            })

        return {"success": True, "items": items,
                **({"message": f"Clés attrs: {', '.join(attrs.keys())}"} if not items else {})}
    except Exception as e:
        return {"success": False, "items": [], "message": str(e)}
