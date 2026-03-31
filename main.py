#!/usr/bin/env python3
"""MCP server for Carrefour Drive — SeleniumBase UC edition."""
import atexit
import json
import signal
import sys

from mcp.server.fastmcp import FastMCP

from src.auth import login, is_logged_in, logout, open_browser_for_login, save_login_cookies
from src.browser import close_browser
from src.cart import add_to_cart, remove_from_cart, get_cart, update_cart_item_quantity
from src.checkout import get_checkout_summary, confirm_and_pay
from src.delivery import set_delivery_mode
from src.favorites import get_favorites, add_favorite, remove_favorite
from src.orders import get_order_history, get_order_items
from src.search import search_products, search_and_add
from src.slots import get_available_slots, select_slot
from src.status import get_status
from src.store import select_store_by_postal_code

mcp = FastMCP("carrefour-drive")

# ── Graceful shutdown ─────────────────────────────────────────────────────────

def _shutdown(*_):
    close_browser()
    sys.exit(0)

atexit.register(close_browser)
signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

# ── Auth ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_open_browser() -> str:
    """Ouvrir Chrome sur la page de login Carrefour (visible via http://localhost:6080/vnc.html). À appeler avant de se connecter manuellement."""
    return json.dumps(open_browser_for_login())

@mcp.tool()
def tool_save_cookies() -> str:
    """Sauvegarder les cookies après connexion manuelle dans le navigateur VNC. À appeler une fois connecté sur Carrefour."""
    return json.dumps(save_login_cookies())

@mcp.tool()
def tool_login() -> str:
    """Se connecter à Carrefour (attente automatique de la connexion). En mode Docker, ouvrir http://localhost:6080/vnc.html pour se connecter manuellement."""
    return json.dumps(login())

@mcp.tool()
def tool_check_login() -> str:
    """Vérifier si on est connecté à Carrefour."""
    logged = is_logged_in()
    return json.dumps({"loggedIn": logged, "message": "Connecté" if logged else "Non connecté"})

@mcp.tool()
def tool_logout() -> str:
    """Se déconnecter de Carrefour."""
    return json.dumps(logout())

# ── Store & delivery ──────────────────────────────────────────────────────────

@mcp.tool()
def tool_select_store(postal_code: str, store_name: str = "") -> str:
    """Sélectionner un magasin Carrefour Drive par code postal."""
    return json.dumps(select_store_by_postal_code(postal_code, store_name or None))

@mcp.tool()
def tool_set_delivery_mode(mode: str) -> str:
    """Définir le mode de livraison : 'drive', 'delivery' ou 'express'."""
    return json.dumps(set_delivery_mode(mode))

# ── Search ────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_search_products(query: str, limit: int = 10) -> str:
    """Chercher des produits sur Carrefour Drive."""
    results = search_products(query, limit)
    return json.dumps(results, ensure_ascii=False)

@mcp.tool()
def tool_search_and_add(query: str, quantity: int = 1) -> str:
    """Chercher un produit et l'ajouter directement au panier."""
    return json.dumps(search_and_add(query, quantity), ensure_ascii=False)

# ── Cart ──────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_add_to_cart(product_id: str, quantity: int = 1) -> str:
    """Ajouter un produit au panier par son ID."""
    return json.dumps(add_to_cart(product_id, quantity))

@mcp.tool()
def tool_remove_from_cart(product_id: str) -> str:
    """Retirer un produit du panier."""
    return json.dumps(remove_from_cart(product_id))

@mcp.tool()
def tool_update_cart_quantity(product_id: str, quantity: int) -> str:
    """Modifier la quantité d'un produit dans le panier."""
    return json.dumps(update_cart_item_quantity(product_id, quantity))

@mcp.tool()
def tool_get_cart() -> str:
    """Voir le contenu du panier."""
    return json.dumps(get_cart(), ensure_ascii=False)

# ── Shopping list ─────────────────────────────────────────────────────────────

@mcp.tool()
def tool_add_shopping_list(items_json: str, max_budget: float = 0) -> str:
    """
    Ajouter une liste d'articles au panier en une fois.
    items_json : JSON array de {"query": str, "quantity": int}
    max_budget : budget max en € (0 = illimité)
    """
    try:
        items = json.loads(items_json)
    except Exception:
        return json.dumps({"success": False, "message": "items_json invalide"})

    results = []
    running_total = 0.0
    if max_budget > 0:
        try:
            running_total = get_cart().get("totalPrice", 0.0)
        except Exception:
            pass

    for item in items:
        if max_budget > 0 and running_total >= max_budget:
            results.append({"query": item["query"], "success": False,
                             "message": f"Budget {max_budget}€ atteint", "skipped": True})
            continue
        r = search_and_add(item.get("query", ""), item.get("quantity", 1))
        results.append({"query": item["query"], "success": r["success"], "message": r["message"]})
        if r["success"] and r.get("product", {}).get("price"):
            running_total += r["product"]["price"] * item.get("quantity", 1)

    ok = sum(1 for r in results if r["success"])
    skipped = sum(1 for r in results if r.get("skipped"))
    summary = f"{ok}/{len(items)} articles ajoutés" + (f" ({skipped} ignorés — budget {max_budget}€)" if skipped else "")
    return json.dumps({"summary": summary, "results": results}, ensure_ascii=False)

# ── Slots ─────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_get_available_slots() -> str:
    """Voir les créneaux de livraison disponibles."""
    slots = get_available_slots()
    return json.dumps(slots if slots else {"message": "Aucun créneau disponible"})

@mcp.tool()
def tool_select_slot(slot_id: str) -> str:
    """Réserver un créneau de livraison (ex: 'slot-0')."""
    return json.dumps(select_slot(slot_id))

# ── Favorites ─────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_list_favorites() -> str:
    """Lister les produits favoris."""
    favs = get_favorites()
    return json.dumps(favs if favs else {"message": "Aucun favori"}, ensure_ascii=False)

@mcp.tool()
def tool_add_favorite(product_id: str, product_name: str, price: float = 0) -> str:
    """Ajouter un produit aux favoris."""
    return json.dumps(add_favorite({"id": product_id, "name": product_name, "price": price,
                                     "brand": "", "pricePerUnit": "", "image": "", "available": True}))

@mcp.tool()
def tool_remove_favorite(product_id: str) -> str:
    """Retirer un produit des favoris."""
    return json.dumps(remove_favorite(product_id))

# ── Orders ────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_get_order_history() -> str:
    """Voir l'historique des commandes."""
    return json.dumps(get_order_history(), ensure_ascii=False)

@mcp.tool()
def tool_get_order_items(order_id: str) -> str:
    """Voir le détail d'une commande."""
    return json.dumps(get_order_items(order_id), ensure_ascii=False)

# ── Checkout ──────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_get_checkout_summary() -> str:
    """Voir le récapitulatif de commande."""
    return json.dumps(get_checkout_summary(), ensure_ascii=False)

@mcp.tool()
def tool_confirm_and_pay() -> str:
    """Confirmer et payer la commande."""
    return json.dumps(confirm_and_pay())

# ── Status ────────────────────────────────────────────────────────────────────

@mcp.tool()
def tool_get_status() -> str:
    """Voir le statut global : connexion, panier, prochain créneau."""
    return json.dumps(get_status(), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
