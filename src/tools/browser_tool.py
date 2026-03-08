"""Browser Automation Tool — Playwright-based web interaction.

SPESION can browse the web, fill forms, extract data, take screenshots,
and interact with websites autonomously (e.g. submit a complaint form on
Endesa's website, check a tracking number, scrape a price).

Requires:
  pip install playwright
  playwright install chromium
"""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ─── Lazy browser singleton ──────────────────────────────────────────────────

_browser = None
_playwright = None


async def _get_browser():
    """Return (or create) a persistent Chromium browser instance."""
    global _browser, _playwright
    if _browser and _browser.is_connected():
        return _browser

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "playwright not installed.  Run:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"],
    )
    logger.info("🌐 Playwright Chromium browser launched (headless)")
    return _browser


def _run_async(coro):
    """Run an async coroutine from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ─── Core browser actions (async) ────────────────────────────────────────────

async def _browse_url(url: str, wait_seconds: float = 3.0) -> dict[str, Any]:
    """Navigate to URL and return page info."""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(int(wait_seconds * 1000))

        title = await page.title()
        # Extract main text content (no scripts/styles)
        text = await page.evaluate("""
            () => {
                const body = document.body.cloneNode(true);
                body.querySelectorAll('script, style, noscript, svg').forEach(e => e.remove());
                return body.innerText.substring(0, 8000);
            }
        """)

        return {
            "url": page.url,
            "title": title,
            "text_content": text,
            "status": "ok",
        }
    except Exception as e:
        return {"url": url, "error": str(e), "status": "error"}
    finally:
        await page.close()


async def _screenshot_url(url: str) -> dict[str, Any]:
    """Take a screenshot of a webpage."""
    browser = await _get_browser()
    page = await browser.new_page(viewport={"width": 1280, "height": 900})
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        screenshot_bytes = await page.screenshot(full_page=False, type="png")
        screenshot_path = Path("./data/screenshots")
        screenshot_path.mkdir(parents=True, exist_ok=True)

        import hashlib
        filename = hashlib.md5(url.encode()).hexdigest()[:12] + ".png"
        filepath = screenshot_path / filename
        filepath.write_bytes(screenshot_bytes)

        return {
            "url": page.url,
            "title": await page.title(),
            "screenshot_path": str(filepath),
            "screenshot_size_kb": len(screenshot_bytes) // 1024,
            "status": "ok",
        }
    except Exception as e:
        return {"url": url, "error": str(e), "status": "error"}
    finally:
        await page.close()


async def _fill_and_submit_form(
    url: str,
    fields: dict[str, str],
    submit_selector: str | None = None,
) -> dict[str, Any]:
    """Navigate to URL, fill form fields, optionally submit."""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        filled = []
        for selector, value in fields.items():
            try:
                await page.fill(selector, value)
                filled.append(selector)
            except Exception as e:
                logger.warning(f"Could not fill {selector}: {e}")

        submitted = False
        if submit_selector:
            try:
                await page.click(submit_selector)
                await page.wait_for_timeout(3000)
                submitted = True
            except Exception as e:
                logger.warning(f"Could not click submit {submit_selector}: {e}")

        title = await page.title()
        current_url = page.url

        return {
            "url": current_url,
            "title": title,
            "fields_filled": filled,
            "submitted": submitted,
            "status": "ok",
        }
    except Exception as e:
        return {"url": url, "error": str(e), "status": "error"}
    finally:
        await page.close()


async def _extract_data(url: str, css_selectors: dict[str, str]) -> dict[str, Any]:
    """Extract specific data from a page using CSS selectors."""
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        extracted: dict[str, str | None] = {}
        for name, selector in css_selectors.items():
            try:
                el = await page.query_selector(selector)
                if el:
                    extracted[name] = await el.inner_text()
                else:
                    extracted[name] = None
            except Exception:
                extracted[name] = None

        return {
            "url": page.url,
            "title": await page.title(),
            "data": extracted,
            "status": "ok",
        }
    except Exception as e:
        return {"url": url, "error": str(e), "status": "error"}
    finally:
        await page.close()


# ─── LangChain Tools (sync wrappers) ─────────────────────────────────────────

@tool
def browse_webpage(url: str, wait_seconds: float = 3.0) -> dict[str, Any]:
    """Browse a webpage and extract its text content.

    Args:
        url: Full URL to browse (https://...)
        wait_seconds: Seconds to wait for JS rendering (default 3)

    Returns:
        Dict with url, title, text_content (first ~8000 chars).
    """
    return _run_async(_browse_url(url, wait_seconds))


@tool
def take_screenshot(url: str) -> dict[str, Any]:
    """Take a screenshot of a webpage and save it locally.

    Args:
        url: Full URL to screenshot

    Returns:
        Dict with screenshot_path and metadata.
    """
    return _run_async(_screenshot_url(url))


@tool
def browser_fill_form(
    url: str,
    fields: dict[str, str],
    submit_selector: str | None = None,
) -> dict[str, Any]:
    """Navigate to a URL, fill in form fields, and optionally submit.

    ⚠️ DANGEROUS — requires user approval if submitting.

    Args:
        url: URL of the page with the form
        fields: Dict mapping CSS selectors to values. Example:
                {"#name": "Eric González", "#email": "eric@example.com"}
        submit_selector: CSS selector for the submit button (optional).
                         If None, fields are filled but form is NOT submitted.

    Returns:
        Dict with fields_filled, submitted status.
    """
    return _run_async(_fill_and_submit_form(url, fields, submit_selector))


@tool
def browser_extract_data(url: str, selectors: dict[str, str]) -> dict[str, Any]:
    """Extract specific data points from a webpage using CSS selectors.

    Useful for scraping prices, order status, tracking numbers, etc.

    Args:
        url: URL to extract from
        selectors: Dict mapping friendly names to CSS selectors. Example:
                   {"price": ".product-price", "status": "#order-status"}

    Returns:
        Dict with extracted data.
    """
    return _run_async(_extract_data(url, selectors))


@tool
def search_web_browser(query: str) -> dict[str, Any]:
    """Search the web using a browser (Google search) and return results.

    Use this when you need to find a company's contact number,
    complaint form URL, or any real-time information.

    Args:
        query: Search query (e.g. "Endesa phone number complaints Spain")

    Returns:
        Dict with search results text.
    """
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&hl=es"
    return _run_async(_browse_url(search_url, wait_seconds=2.0))


# ─── Factory ──────────────────────────────────────────────────────────────────

def create_browser_tools() -> list:
    """Return all browser automation tools."""
    return [browse_webpage, take_screenshot, browser_fill_form, browser_extract_data, search_web_browser]
