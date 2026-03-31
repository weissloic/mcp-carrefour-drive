from __future__ import annotations
from .browser import api_call, save_cookies


def get_available_slots() -> list[dict]:
    for path in ["/api/slots", "/api/cart/slots", "/api/delivery/slots"]:
        r = api_call("GET", path)
        if r and r.get("ok"):
            data = r.get("data") or {}
            raw = data if isinstance(data, list) else data.get("data") or data.get("slots") or []
            if raw:
                slots = []
                for i, s in enumerate(raw):
                    a = s.get("attributes") or s
                    slots.append({
                        "id": str(a.get("slotId") or a.get("id") or f"slot-{i}"),
                        "date": a.get("date") or a.get("day") or "",
                        "timeRange": a.get("timeRange") or a.get("label") or "",
                        "available": a.get("available", True),
                        "price": a.get("price") or a.get("deliveryCost"),
                    })
                return slots
    return []


def select_slot(slot_id: str) -> dict:
    for path, payload in [
        (f"/api/slots/{slot_id}/select", {}),
        ("/api/cart/slot", {"slotId": slot_id}),
        ("/api/delivery/slot", {"slotId": slot_id}),
    ]:
        r = api_call("POST", path, payload)
        if r and r.get("ok"):
            save_cookies()
            return {"success": True, "message": f"Créneau {slot_id} sélectionné"}

    return {"success": False, "message": f"Endpoint select-slot inconnu pour {slot_id}"}
