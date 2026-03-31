from __future__ import annotations
import sys
import time
from urllib.parse import quote_plus

from .browser import _ensure_on_carrefour, navigate_and_wait, save_cookies

_cache: dict = {}
CACHE_TTL = 3600

def _extract_cards(driver, limit: int) -> list:
    """Extract product cards from article elements already in the DOM."""
    limit_int = int(limit)
    script = f"""
var cards = document.querySelectorAll('article');
var n = Math.min(cards.length, {limit_int});
var results = [];
for (var i = 0; i < n; i++) {{
    var c = cards[i];
    try {{
        var nameEl  = c.querySelector('h3');
        var pp      = c.querySelectorAll('[data-testid="product-price__amount--main"] p');
        var priceText = '';
        for (var j = 0; j < pp.length; j++) priceText += pp[j].textContent;
        var brandEl = c.querySelector('a.c-link--tone-accent');
        var unitEl  = c.querySelector('[class*="per-unit-label"]');
        var imgEl   = c.querySelector('.product-card-image-new img, img');
        var promoEl = c.querySelector('[class*="sticker-promo__text"]');
        var linkEl  = c.querySelector('a[href^="/p/"]');
        var link    = linkEl ? linkEl.getAttribute('href') : '';
        var parts   = link.split('/').filter(function(x){{return !!x;}});
        var id      = parts.length ? parts[parts.length - 1] : ('product-' + i);
        var cleaned = priceText.replace(/[^0-9,]/g, '').replace(',', '.');
        var price   = cleaned ? parseFloat(cleaned) : 0;
        results.push({{
            id:           id,
            name:         nameEl  ? nameEl.textContent.trim()  : '',
            brand:        brandEl ? brandEl.textContent.trim() : '',
            price:        isNaN(price) ? 0 : price,
            pricePerUnit: unitEl  ? unitEl.textContent.trim()  : '',
            image:        imgEl   ? imgEl.src                  : '',
            available:    true,
            promotion:    promoEl ? promoEl.textContent.trim() : null
        }});
    }} catch(e) {{ continue; }}
}}
return results;
"""
    result = driver.execute_script(script)
    return result if isinstance(result, list) else []


def search_products(query: str, limit: int = 10) -> list:
    key = f"{query}:{limit}"
    if key in _cache and time.time() - _cache[key]["ts"] < CACHE_TTL:
        return _cache[key]["data"]

    driver = _ensure_on_carrefour()
    navigate_and_wait(driver, f"https://www.carrefour.fr/s?q={quote_plus(query)}")

    article_count = 0
    for _ in range(20):
        article_count = driver.execute_script("return document.querySelectorAll('article').length;") or 0
        if article_count:
            break
        time.sleep(0.5)

    print(f"[carrefour-mcp] search '{query}': {article_count} articles dans le DOM", file=sys.stderr)

    products = _extract_cards(driver, limit)
    print(f"[carrefour-mcp] search '{query}': {len(products)} produits extraits", file=sys.stderr)

    _cache[key] = {"data": products, "ts": time.time()}
    return products


def search_and_add(query: str, quantity: int = 1) -> dict:
    try:
        driver = _ensure_on_carrefour()
        navigate_and_wait(driver, f"https://www.carrefour.fr/s?q={quote_plus(query)}")

        for _ in range(20):
            if driver.execute_script("return document.querySelectorAll('article').length;"):
                break
            time.sleep(0.5)

        count = driver.execute_script("return document.querySelectorAll('article').length;") or 0
        if count == 0:
            return {"success": False, "message": f'Aucun produit trouvé pour "{query}"'}

        # Extract first product info + click add button (mirrors TS searchAndAdd)
        result = driver.execute_script("""
            var c = document.querySelector('article');
            if (!c) return {result: 'no-article'};
            var nameEl = c.querySelector('h3');
            var pp     = c.querySelectorAll('[data-testid="product-price__amount--main"] p');
            var price  = parseFloat(Array.from(pp).map(function(p){return p.textContent;})
                           .join('').replace(/[^\\d,]/g,'').replace(',','.')) || 0;
            var linkEl = c.querySelector('a[href^="/p/"]');
            var link   = linkEl ? linkEl.getAttribute('href') : '';
            var parts  = link.split('/').filter(Boolean);
            var id     = parts[parts.length - 1] || 'product-0';
            c.scrollIntoView();
            var addBtn  = c.querySelector('button[aria-label*="Ajouter le produit"]');
            if (addBtn) { addBtn.click(); return {result:'added',   id:id, name:nameEl?nameEl.textContent.trim():'', price:price}; }
            var plusBtn = c.querySelector('button[aria-label="plus"]');
            if (plusBtn){ plusBtn.click(); return {result:'incremented', id:id, name:nameEl?nameEl.textContent.trim():'', price:price}; }
            return {result:'not-found', id:id, name:nameEl?nameEl.textContent.trim():'', price:price};
        """)

        if not result or result.get("result") in ("no-article", "not-found"):
            return {"success": False, "message": "Bouton d'ajout non trouvé sur la carte produit"}

        time.sleep(1.5)

        for _ in range(quantity - 1):
            driver.execute_script("""
                var c = document.querySelector('article');
                if (c) { var b = c.querySelector('button[aria-label="plus"]'); if(b) b.click(); }
            """)
            time.sleep(0.4)

        save_cookies()
        product = {"id": result["id"], "name": result["name"], "price": result["price"],
                   "brand": "", "pricePerUnit": "", "image": "", "available": True}
        return {"success": True, "message": f'{quantity}x "{result["name"]}" ajouté au panier',
                "product": product}
    except Exception as e:
        return {"success": False, "message": f"Erreur : {e}"}
