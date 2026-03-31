from __future__ import annotations
from .browser import api_call, save_cookies

MODE_MAP = {
    "drive": "driveclcv",
    "delivery": "clivhome",
    "express": "express",
}


def set_delivery_mode(mode: str) -> dict:
    if mode not in MODE_MAP:
        return {"success": False, "message": f"Mode inconnu: {mode}. Valeurs: drive, delivery, express"}

    service_type = MODE_MAP[mode]
    for path, payload in [
        ("/api/cart/service-type", {"serviceType": service_type}),
        ("/api/delivery/mode", {"mode": service_type}),
        ("/api/cart", {"serviceType": service_type}),
    ]:
        r = api_call("PATCH", path, payload)
        if r and r.get("ok"):
            save_cookies()
            return {"success": True, "message": f"Mode '{mode}' activé", "serviceType": service_type}

    return {"success": False, "message": f"Endpoint set-delivery-mode inconnu pour '{mode}'"}
