from __future__ import annotations
import os
import sys
import time

from .browser import open_for_login, save_cookies, close_browser, api_call, DATA_DIR

IS_LINUX = os.path.exists("/.dockerenv") or sys.platform.startswith("linux")


def is_logged_in() -> bool:
    try:
        r = api_call("GET", "/api/me")
        if not (r and r.get("ok")):
            return False
        data = r.get("data") or {}
        # Accept any field that proves the user has an authenticated identity
        return bool(
            data.get("sessionId")
            or data.get("customerId")
            or data.get("email")
            or data.get("firstName")
            or data.get("id")
        )
    except Exception:
        return False


def open_browser_for_login() -> dict:
    """Force-open a visible Chrome browser on carrefour.fr login page."""
    try:
        print("[carrefour-mcp] Ouverture forcée du navigateur...", file=sys.stderr)
        driver = open_for_login()
        driver.uc_open_with_reconnect("https://www.carrefour.fr/mon-compte/login", reconnect_time=4)
        url = driver.current_url
        print(f"[carrefour-mcp] Navigateur ouvert sur : {url}", file=sys.stderr)
        return {"success": True, "message": f"Navigateur ouvert sur {url}. Connectez-vous via http://localhost:6080/vnc.html puis appelez tool_save_login_cookies."}
    except Exception as e:
        return {"success": False, "message": f"Échec ouverture navigateur : {e}"}


def save_login_cookies() -> dict:
    """Save cookies after manual login in VNC browser."""
    try:
        import src.browser as _b
        if _b._login_driver is None:
            return {"success": False, "message": "Aucun navigateur de login ouvert. Appelez tool_open_browser d'abord."}
        url = _b._login_driver.current_url
        if "login" in url or "connexion" in url or "moncompte" in url:
            return {"success": False, "message": f"Pas encore connecté (URL: {url}). Connectez-vous d'abord via VNC."}
        import json, os
        cookies_file = os.path.join(DATA_DIR, "cookies.json")
        try:
            with open(cookies_file) as f:
                count = len(json.load(f))
        except Exception:
            count = 0
        return {"success": True, "message": f"Cookies sauvegardés ({count}) depuis {url}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def login() -> dict:
    if is_logged_in():
        return {"success": True, "message": "Déjà connecté"}

    try:
        print("[carrefour-mcp] Démarrage du navigateur...", file=sys.stderr)
        driver = open_for_login()
        print("[carrefour-mcp] Navigateur démarré, ouverture de Carrefour...", file=sys.stderr)
        driver.uc_open_with_reconnect("https://www.carrefour.fr/mon-compte/login", reconnect_time=4)
        print(f"[carrefour-mcp] Page ouverte : {driver.current_url}", file=sys.stderr)

        if IS_LINUX:
            hint = (
                " → http://localhost:6080/vnc.html"
                if os.environ.get("BROWSER_HEADLESS", "true").lower() == "false"
                else " (BROWSER_HEADLESS=false requis pour noVNC)"
            )
            print(f"[carrefour-mcp] Connexion manuelle attendue.{hint}", file=sys.stderr)

        deadline = time.time() + 300
        while time.time() < deadline:
            url = driver.current_url
            if (
                "www.carrefour.fr" in url
                and "moncompte" not in url
                and "login" not in url
                and "connexion" not in url
            ):
                break
            time.sleep(1)
        else:
            return {"success": False, "message": "Délai de connexion dépassé (5 min)"}

        time.sleep(1.5)
        save_cookies()

        cookies_count = len(driver.get_cookies())
        return {"success": True, "message": f"Connexion réussie — {cookies_count} cookies sauvegardés"}
    except Exception as e:
        return {"success": False, "message": f"Échec connexion : {e}"}


def logout() -> dict:
    try:
        api_call("GET", "/mon-compte/deconnexion")
        cookies_file = os.path.join(DATA_DIR, "cookies.json")
        if os.path.exists(cookies_file):
            os.remove(cookies_file)
        close_browser()
        return {"success": True, "message": "Déconnecté"}
    except Exception as e:
        return {"success": False, "message": f"Échec déconnexion : {e}"}
