from __future__ import annotations
from .browser import api_call, save_cookies


def get_checkout_summary() -> dict:
    try:
        r = api_call("GET", "/api/cart/checkout") or api_call("GET", "/api/checkout")
        if r and r.get("ok"):
            return {"success": True, "summary": r.get("data"), "message": "Résumé récupéré"}

        # Fallback: compose from cart + status
        from .cart import get_cart
        from .status import get_status
        cart = get_cart()
        status = get_status().get("status", {})
        return {
            "success": True,
            "summary": {
                "totalPrice": cart.get("totalPrice", 0),
                "deliverySlot": status.get("nextSlot") or "non sélectionné",
                "cartItems": cart.get("totalItems", 0),
            },
            "message": "Résumé composé depuis /api/cart + /api/me",
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


def confirm_and_pay() -> dict:
    try:
        for path, payload in [
            ("/api/cart/order", {}),
            ("/api/checkout/confirm", {}),
            ("/api/order", {}),
        ]:
            r = api_call("POST", path, payload)
            if r and r.get("ok"):
                data = r.get("data") or {}
                order_id = (
                    data.get("orderNumber")
                    or data.get("orderId")
                    or (data.get("data") or {}).get("orderNumber")
                )
                save_cookies()
                return {
                    "success": True,
                    "message": f"Commande confirmée !{f' N° {order_id}' if order_id else ''}",
                    "orderNumber": order_id,
                }

        return {"success": False, "message": "Endpoint confirm-and-pay inconnu — vérifiez manuellement sur carrefour.fr"}
    except Exception as e:
        return {"success": False, "message": str(e)}
