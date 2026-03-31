from __future__ import annotations
import time

from .browser import _ensure_on_carrefour, navigate_and_wait, api_call, save_cookies


def select_store_by_postal_code(postal_code: str, store_name: str | None = None) -> dict:
    """
    Navigate to /magasin, fill the search input, extract store cards from DOM,
    then click the select button — mirrors TS selectStoreByPostalCode.
    """
    driver = _ensure_on_carrefour()
    navigate_and_wait(driver, "https://www.carrefour.fr/magasin")

    # Wait for the search input (selector from TS)
    input_ready = False
    for _ in range(20):
        found = driver.execute_script(
            "return !!document.querySelector('input[name=\"search\"].c-base-input__input');"
        )
        if found:
            input_ready = True
            break
        time.sleep(0.5)

    if not input_ready:
        # Fallback: any visible search input
        driver.execute_script("""
            var inp = document.querySelector('input[type="text"], input[type="search"]');
            if (inp) { inp.value = arguments[0]; inp.dispatchEvent(new Event('input',{bubbles:true})); }
        """, postal_code)
    else:
        driver.execute_script("""
            var inp = document.querySelector('input[name="search"].c-base-input__input');
            inp.focus();
            inp.value = arguments[0];
            inp.dispatchEvent(new Event('input',  {bubbles:true}));
            inp.dispatchEvent(new Event('change', {bubbles:true}));
            inp.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter', bubbles:true}));
            inp.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter', bubbles:true}));
            inp.dispatchEvent(new KeyboardEvent('keyup',   {key:'Enter', bubbles:true}));
        """, postal_code)

    # Wait for results (networkidle equivalent)
    time.sleep(3)

    # Extract store cards from DOM (mirrors TS storeCards locator)
    stores_raw = driver.execute_script("""
        var sel = '[data-testid="store-card"],.c-store-card,.store-card,.store-result,article';
        var cards = document.querySelectorAll(sel);
        var results = [];
        for (var i = 0; i < Math.min(cards.length, 15); i++) {
            var c = cards[i];
            var nameEl = c.querySelector('h2,h3,.c-store-card__name,.store-name,[data-testid="store-name"]');
            var addrEl = c.querySelector('.c-store-card__address,.address,.store-address,[data-testid="store-address"]');
            var name = nameEl ? nameEl.textContent.trim() : '';
            if (!name) continue;
            results.push({index: i, name: name, address: addrEl ? addrEl.textContent.trim() : ''});
        }
        return results;
    """) or []

    if not stores_raw:
        return {"success": False, "message": f"Aucun magasin trouvé pour {postal_code}"}

    stores = [
        {
            "id": str(s["index"]),
            "name": s["name"],
            "address": s["address"],
            "postalCode": postal_code,
            "city": "",
            "type": "drive" if "drive" in s["name"].lower() else "magasin",
        }
        for s in stores_raw
    ]

    # Pick target store
    if store_name:
        target = next((s for s in stores if store_name.lower() in s["name"].lower()), None)
        if not target:
            return {"success": False,
                    "message": f'Magasin "{store_name}" non trouvé.',
                    "stores": stores}
    else:
        target = next((s for s in stores if s["type"] == "drive"), stores[0])

    # Click the select button on the target card (mirrors TS selectStore)
    idx = int(target["id"])
    clicked = driver.execute_script(f"""
        var sel = '[data-testid="store-card"],.c-store-card,.store-card,.store-result,article';
        var cards = document.querySelectorAll(sel);
        var card = cards[{idx}];
        if (!card) return false;
        var btns = card.querySelectorAll('button,a');
        for (var i = 0; i < btns.length; i++) {{
            var t = btns[i].textContent.toLowerCase();
            if (t.includes('choisir') || t.includes('sélectionner') || t.includes('drive')) {{
                btns[i].click(); return true;
            }}
        }}
        // fallback: first button
        if (btns.length) {{ btns[0].click(); return true; }}
        return false;
    """)

    if not clicked:
        return {"success": False,
                "message": f"Bouton de sélection non trouvé pour {target['name']}",
                "stores": stores}

    time.sleep(2)
    save_cookies()
    return {"success": True,
            "message": f"Magasin \"{target['name']}\" sélectionné",
            "stores": stores}
