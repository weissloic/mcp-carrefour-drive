"""
Browser — two separate roles:
  1. Login:    visible Chrome (noVNC) → user logs in → cookies saved to JSON → browser closed
  2. API:      headless Chrome with cookies injected BEFORE first navigation
               stays alive for all API calls in the same process
"""
from __future__ import annotations
import json
import os
import sys
import time

from seleniumbase import Driver

DATA_DIR    = os.environ.get("CARREFOUR_DATA_DIR", os.path.expanduser("~/.carrefour-mcp"))
COOKIES_FILE = os.path.join(DATA_DIR, "cookies.json")

# Separate profile dirs — avoids Chrome locking the profile when two instances run
LOGIN_PROFILE = os.path.join(DATA_DIR, "login-profile")
API_PROFILE   = os.path.join(DATA_DIR, "api-profile")

IS_LINUX = os.path.exists("/.dockerenv") or sys.platform.startswith("linux")

_api_driver: Driver | None = None          # headless, kept alive for API calls
_login_driver: Driver | None = None        # visible, only during login


# ── Driver factory ─────────────────────────────────────────────────────────────

def _make_driver(headless: bool, profile_dir: str) -> Driver:
    if IS_LINUX:
        os.environ["DISPLAY"] = ":99"  # always override — docker exec inherits Mac DISPLAY
    os.makedirs(profile_dir, exist_ok=True)
    return Driver(
        browser="chrome",
        uc=True,
        headless=headless,
        user_data_dir=profile_dir,
        no_sandbox=IS_LINUX,
        locale_code="fr",
        chromium_arg=(
            "--disable-dev-shm-usage "
            "--disable-gpu "
            "--window-size=1280,900"
        ),
    )


# ── Cookie helpers ─────────────────────────────────────────────────────────────

def _load_cookies() -> list[dict]:
    if not os.path.exists(COOKIES_FILE):
        return []
    try:
        with open(COOKIES_FILE) as f:
            return json.load(f)
    except Exception:
        return []


def _inject_cookies(driver: Driver, cookies: list[dict]) -> int:
    """
    Inject cookies via CDP Network.setCookie BEFORE any navigation.
    This is critical: if carrefour.fr loads first without auth cookies,
    it creates an anonymous session that conflicts with our saved session.
    """
    if not cookies:
        return 0
    try:
        driver.execute_cdp_cmd("Network.enable", {})
    except Exception:
        pass

    ok = 0
    for c in cookies:
        try:
            param: dict = {"name": c["name"], "value": c["value"]}
            if c.get("domain"):
                param["domain"] = c["domain"]
            if c.get("path"):
                param["path"] = c["path"]
            if c.get("secure"):
                param["secure"] = True
            if c.get("httpOnly"):
                param["httpOnly"] = True
            if c.get("sameSite") and c["sameSite"] in ("Strict", "Lax", "None"):
                param["sameSite"] = c["sameSite"]
            if c.get("expires") and isinstance(c["expires"], (int, float)) and c["expires"] > 0:
                param["expires"] = int(c["expires"])
            result = driver.execute_cdp_cmd("Network.setCookie", param)
            if result.get("success"):
                ok += 1
        except Exception:
            pass
    return ok


def save_cookies() -> None:
    """Save ALL browser cookies via CDP (all domains, incl. moncompte.carrefour.fr)."""
    driver = _login_driver or _api_driver
    if driver is None:
        return
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        result = driver.execute_cdp_cmd("Network.getAllCookies", {})
        cookies = result.get("cookies", [])
        if not cookies:
            cookies = driver.get_cookies()
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f)
        print(f"[carrefour-mcp] {len(cookies)} cookies sauvegardés", file=sys.stderr)
    except Exception as e:
        print(f"[carrefour-mcp] save_cookies error: {e}", file=sys.stderr)


# ── Login browser (visible) ────────────────────────────────────────────────────

def open_for_login() -> Driver:
    """Open a VISIBLE browser for manual login. Separate profile from API browser."""
    global _login_driver
    if _login_driver:
        try:
            _login_driver.quit()
        except Exception:
            pass
    _login_driver = _make_driver(headless=False, profile_dir=LOGIN_PROFILE)
    return _login_driver


def close_login_browser() -> None:
    global _login_driver
    if _login_driver:
        try:
            _login_driver.quit()
        except Exception:
            pass
        _login_driver = None


# ── API browser (headless) ─────────────────────────────────────────────────────

def _ensure_api_driver() -> Driver:
    """
    Return a driver ready to make authenticated API calls.

    Priority:
      1. Reuse the login browser if it is still alive — it already holds the
         authenticated session so no cookie injection is needed.
      2. Reuse an existing headless API driver if healthy.
      3. Create a fresh headless driver, inject saved cookies BEFORE the first
         navigation (critical: prevents carrefour.fr from opening an anonymous
         session that would shadow the injected cookies).
    """
    global _api_driver

    # ── 1. Prefer the visible login browser (already authenticated) ────────────
    if _login_driver is not None:
        try:
            _ = _login_driver.current_url
            print("[carrefour-mcp] Réutilisation du navigateur de login pour les appels API", file=sys.stderr)
            return _login_driver
        except Exception:
            pass  # login driver died → fall through

    # ── 2. Reuse healthy headless driver ───────────────────────────────────────
    if _api_driver is not None:
        try:
            _ = _api_driver.current_url
            return _api_driver
        except Exception:
            _api_driver = None

    # ── 3. Create a fresh headless driver with cookie pre-injection ────────────
    print("[carrefour-mcp] Démarrage du navigateur API headless...", file=sys.stderr)
    _api_driver = _make_driver(headless=True, profile_dir=API_PROFILE)

    cookies = _load_cookies()
    if cookies:
        injected = _inject_cookies(_api_driver, cookies)
        print(f"[carrefour-mcp] {injected}/{len(cookies)} cookies injectés avant navigation", file=sys.stderr)
    else:
        print("[carrefour-mcp] Aucun cookie sauvegardé — connecte-toi d'abord via tool_login", file=sys.stderr)

    _api_driver.get("https://www.carrefour.fr")
    return _api_driver


def close_api_browser() -> None:
    global _api_driver
    if _api_driver:
        try:
            _api_driver.quit()
        except Exception:
            pass
        _api_driver = None


def close_browser() -> None:
    close_login_browser()
    close_api_browser()


# ── API calls (fetch inside headless browser) ──────────────────────────────────

def api_call(method: str, path: str, body: dict | None = None) -> dict | None:
    driver = _ensure_api_driver()
    url = path if path.startswith("http") else f"https://www.carrefour.fr{path}"
    driver.set_script_timeout(20)
    return driver.execute_async_script("""
        var done = arguments[arguments.length - 1];
        fetch(arguments[1], {
            method: arguments[0],
            credentials: 'include',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/plain, */*',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: arguments[2] ? JSON.stringify(arguments[2]) : undefined
        })
        .then(function(r) {
            return r.text().then(function(t) {
                var d = null;
                try { d = JSON.parse(t); } catch(e) { d = t; }
                return {ok: r.ok, status: r.status, data: d};
            });
        })
        .catch(function(e) { done({ok: false, status: 0, error: e.toString()}); })
        .then(done);
    """, method, url, body)


def _ensure_on_carrefour():
    """Alias used by cart/search modules that need the driver directly."""
    return _ensure_api_driver()


# ── DOM navigation helper ───────────────────────────────────────────────────────

def navigate_and_wait(driver, url: str) -> None:
    """Navigate to url and dismiss the OneTrust cookie banner if present."""
    driver.get(url)
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        btn.click()
        time.sleep(0.5)
    except Exception:
        pass


# ── Network interception (port of TS interceptApi / waitForResponse) ────────────

# Spy injected as a document-level init script so it runs before any page JS.
_SPY_SCRIPT = """
(function() {
    if (window.__mcpSpyInstalled) return;
    window.__mcpSpyInstalled = true;
    window.__apiCaptures = {};

    // Intercept fetch()
    var _origFetch = window.fetch;
    window.fetch = function() {
        var url = String(arguments[0] || '');
        var promise = _origFetch.apply(this, arguments);
        promise.then(function(resp) {
            resp.clone().json().then(function(data) {
                window.__apiCaptures[url] = data;
            }).catch(function() {});
        }).catch(function() {});
        return promise;
    };

    // Intercept XMLHttpRequest
    var _OrigXHR = window.XMLHttpRequest;
    function McpXHR() {
        var xhr = new _OrigXHR();
        var origOpen = xhr.open;
        xhr.open = function(method, url) {
            xhr.__mcpUrl = String(url);
            return origOpen.apply(xhr, arguments);
        };
        xhr.addEventListener('load', function() {
            if (xhr.__mcpUrl) {
                try { window.__apiCaptures[xhr.__mcpUrl] = JSON.parse(xhr.responseText); }
                catch(e) {}
            }
        });
        return xhr;
    }
    McpXHR.prototype = _OrigXHR.prototype;
    window.XMLHttpRequest = McpXHR;
})();
"""


def intercept_apis(url_patterns: list, trigger_url: str, timeout: int = 20) -> dict:
    """
    Navigate to trigger_url and capture JSON responses whose URLs contain any
    of url_patterns (like Playwright's waitForResponse).
    Returns {pattern: data} for every pattern that was captured.
    """
    driver = _ensure_api_driver()

    # Install spy that survives the upcoming navigation
    cdp_result = driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": _SPY_SCRIPT}
    )
    script_id = (cdp_result or {}).get("identifier")

    try:
        driver.get(trigger_url)
        captures: dict = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            all_caps = driver.execute_script("return window.__apiCaptures || {};") or {}
            if all_caps:
                print(f"[carrefour-mcp] intercept_apis captured URLs: {list(all_caps.keys())[:10]}", file=sys.stderr)
            for pat in url_patterns:
                if pat not in captures:
                    for url, data in all_caps.items():
                        if pat in url:
                            captures[pat] = data
                            break
            if len(captures) == len(url_patterns):
                break
            time.sleep(0.5)
        print(
            f"[carrefour-mcp] intercept_apis result: {list(captures.keys())} / {url_patterns}",
            file=sys.stderr,
        )
        return captures
    finally:
        if script_id:
            try:
                driver.execute_cdp_cmd(
                    "Page.removeScriptToEvaluateOnNewDocument", {"identifier": script_id}
                )
            except Exception:
                pass


def screenshot(name: str) -> str | None:
    driver = _api_driver or _login_driver
    if not driver:
        return None
    try:
        path = os.path.join(DATA_DIR, "screenshots", f"{name}-{int(time.time())}.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        driver.save_screenshot(path)
        return path
    except Exception:
        return None
