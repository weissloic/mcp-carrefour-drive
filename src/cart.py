from __future__ import annotations
import re
import time
from urllib.parse import quote_plus, urlparse

from .browser import _ensure_on_carrefour, _ensure_api_driver, navigate_and_wait, save_cookies

CART_URL = "https://www.carrefour.fr/cart/driveclcv"


def get_cart() -> dict:
    """Direct authenticated fetch to /api/cart from within the browser."""
    try:
        driver = _ensure_api_driver()
        if "www.carrefour.fr" not in driver.current_url:
            driver.get("https://www.carrefour.fr")

        driver.set_script_timeout(20)
        data = driver.execute_async_script("""
            var done = arguments[arguments.length - 1];
            fetch('https://www.carrefour.fr/api/cart', {
                credentials: 'include',
                headers: {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
            })
            .then(function(r) { return r.json(); })
            .then(done)
            .catch(function(e) { done(null); });
        """)
        cart_data = (data or {}).get("cart") or {}

        items = []
        for cat in cart_data.get("items", []):
            for entry in cat.get("products", []):
                p = ((entry.get("product") or {}).get("attributes")) or {}
                price = (p.get("selling") or {}).get("price") or p.get("price") or 0
                qty   = entry.get("counter", 1)
                items.append({
                    "product": {
                        "id":           p.get("ean") or (entry.get("product") or {}).get("id") or "",
                        "name":         p.get("title") or p.get("shortTitle") or "",
                        "brand":        p.get("brand") or "",
                        "price":        float(price),
                        "pricePerUnit": p.get("pricePerUnit") or "",
                        "image":        ((p.get("images") or {}).get("paths") or [""])[0],
                        "available":    entry.get("available", True) is not False,
                    },
                    "quantity": qty,
                    "subtotal": entry.get("totalItemPrice") or float(price) * qty,
                })

        return {
            "items":      items,
            "totalItems": sum(i["quantity"] for i in items),
            "totalPrice": cart_data.get("totalAmount") or 0,
        }
    except Exception as e:
        return {"items": [], "totalItems": 0, "totalPrice": 0, "error": str(e)}


def add_to_cart(product_id: str, quantity: int = 1) -> dict:
    """Navigate to search page and click the add-to-cart button (mirrors TS addToCart)."""
    try:
        slug = product_id
        if product_id.startswith("http"):
            slug = urlparse(product_id).path.rstrip("/").split("/")[-1]
        elif product_id.startswith("/p/"):
            slug = product_id[3:]

        search_query = re.sub(r"-\d{8,13}$", "", slug).replace("-", " ").strip() or slug

        driver = _ensure_on_carrefour()
        navigate_and_wait(driver, f"https://www.carrefour.fr/s?q={quote_plus(search_query)}")

        for _ in range(20):
            if driver.execute_script("return document.querySelectorAll('article').length;"):
                break
            time.sleep(0.5)

        result = driver.execute_script(f"""
            var arts = document.querySelectorAll('article');
            var target = null, productName = '{slug}';
            for (var i = 0; i < arts.length; i++) {{
                var a = arts[i].querySelector('a[href^="/p/"]');
                if (a && a.getAttribute('href').includes('{slug}')) {{
                    target = arts[i]; break;
                }}
            }}
            if (!target && arts.length > 0) target = arts[0];
            if (!target) return {{result: 'no-article'}};
            var nameEl = target.querySelector('h3');
            productName = nameEl ? nameEl.textContent.trim() : productName;
            target.scrollIntoView();
            var addBtn  = target.querySelector('button[aria-label*="Ajouter le produit"]');
            if (addBtn)  {{ addBtn.click();  return {{result:'added',       name:productName}}; }}
            var plusBtn = target.querySelector('button[aria-label="plus"]');
            if (plusBtn) {{ plusBtn.click(); return {{result:'incremented', name:productName}}; }}
            return {{result:'not-found', name:productName}};
        """)

        if not result or result.get("result") in ("no-article", "not-found"):
            return {"success": False, "message": f"Bouton d'ajout non trouvé pour {product_id}"}

        time.sleep(1.5)

        for _ in range(quantity - 1):
            driver.execute_script("""
                var arts = document.querySelectorAll('article');
                for (var i = 0; i < arts.length; i++) {
                    var b = arts[i].querySelector('button[aria-label="plus"]');
                    if (b) { b.click(); break; }
                }
            """)
            time.sleep(0.4)

        save_cookies()
        return {"success": True, "message": f'{quantity}x "{result["name"]}" ajouté au panier'}
    except Exception as e:
        return {"success": False, "message": f"Échec ajout : {e}"}


def remove_from_cart(product_id: str) -> dict:
    try:
        driver = _ensure_on_carrefour()
        navigate_and_wait(driver, CART_URL)
        time.sleep(2)

        result = driver.execute_script(f"""
            var items = document.querySelectorAll('[data-testid="cart-item"],.cart-item,[class*="cart-item"]');
            for (var i = 0; i < items.length; i++) {{
                var a = items[i].querySelector('a');
                if (a && (a.getAttribute('href')||'').includes('{product_id}')) {{
                    var btn = items[i].querySelector(
                        'button[aria-label*="supprimer"],button[aria-label*="retirer"],' +
                        'button[data-testid*="remove"],button[data-testid*="delete"]'
                    );
                    if (btn) {{ btn.click(); return 'removed'; }}
                }}
            }}
            return 'not-found';
        """)

        if result != "removed":
            return {"success": False, "message": "Produit non trouvé dans le panier"}
        time.sleep(1.5)
        save_cookies()
        return {"success": True, "message": "Produit retiré du panier"}
    except Exception as e:
        return {"success": False, "message": f"Échec suppression : {e}"}


def update_cart_item_quantity(product_id: str, quantity: int) -> dict:
    try:
        driver = _ensure_on_carrefour()
        navigate_and_wait(driver, CART_URL)
        time.sleep(3)

        result = driver.execute_script(f"""
            var items = document.querySelectorAll('[data-testid="cart-item"],.cart-item,[class*="cart-item"]');
            for (var i = 0; i < items.length; i++) {{
                var a = items[i].querySelector('a');
                if (a && (a.getAttribute('href')||'').includes('{product_id}')) {{
                    var inp = items[i].querySelector('input[type="number"],.quantity-selector input');
                    if (inp) {{
                        inp.value = '{quantity}';
                        inp.dispatchEvent(new Event('input',{{bubbles:true}}));
                        inp.dispatchEvent(new KeyboardEvent('keypress',{{key:'Enter',bubbles:true}}));
                        return 'updated';
                    }}
                }}
            }}
            return 'not-found';
        """)

        if result != "updated":
            return {"success": False, "message": "Produit non trouvé dans le panier"}
        time.sleep(1.5)
        save_cookies()
        return {"success": True, "message": f"Quantité mise à jour : {quantity}"}
    except Exception as e:
        return {"success": False, "message": f"Échec mise à jour : {e}"}
