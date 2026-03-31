from __future__ import annotations
import json
import os

DATA_DIR = os.environ.get("CARREFOUR_DATA_DIR", os.path.expanduser("~/.carrefour-mcp"))
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")


def _load() -> list[dict]:
    if not os.path.exists(FAVORITES_FILE):
        return []
    with open(FAVORITES_FILE) as f:
        return json.load(f)


def _save(favs: list[dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FAVORITES_FILE, "w") as f:
        json.dump(favs, f)


def get_favorites() -> list[dict]:
    return _load()


def add_favorite(product: dict) -> dict:
    favs = _load()
    if any(f["id"] == product["id"] for f in favs):
        return {"success": False, "message": "Déjà dans les favoris"}
    favs.append(product)
    _save(favs)
    return {"success": True, "message": f'"{product["name"]}" ajouté aux favoris'}


def remove_favorite(product_id: str) -> dict:
    favs = _load()
    new = [f for f in favs if f["id"] != product_id]
    if len(new) == len(favs):
        return {"success": False, "message": "Produit non trouvé dans les favoris"}
    _save(new)
    return {"success": True, "message": "Favori supprimé"}
