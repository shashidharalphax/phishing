import os
import asyncio
import logging
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MAX_WAIT_SEC = 30      # ⬅️  increase total timeout from 30 → 90 seconds
POST_LOAD_WAIT_SEC = 3  # ⬅️  wait this long for redirects and scripts

def _safe_name(url: str) -> str:
    return url.replace("://", "_").replace("/", "_")[:150]

async def _shot(url: str, path: str):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1366, "height": 768})
        page = await ctx.new_page()
        html = ""
        try:
            logging.info(f"Navigating to {url} (timeout={MAX_WAIT_SEC}s)…")
            await page.goto(url, timeout=MAX_WAIT_SEC * 1000, wait_until="load")
            await asyncio.sleep(POST_LOAD_WAIT_SEC)
            html = await page.content()
            await page.screenshot(path=path, full_page=True)
        except PlaywrightTimeout:
            logging.warning(f"Timeout visiting {url} — took longer than {MAX_WAIT_SEC}s")
            try:
                await page.screenshot(path=path, full_page=False)
            except Exception:
                pass
        except Exception as e:
            logging.warning(f"Screenshot failed for {url}: {e}")
            try:
                await page.screenshot(path=path, full_page=False)
            except Exception:
                pass
        await browser.close()
        return html

async def _pair(orig_url, cand_url, orig_path, cand_path):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1366, "height": 768})
        p1 = await ctx.new_page()
        p2 = await ctx.new_page()
        h1 = ""
        h2 = ""

        # --- Original
        try:
            logging.info(f"Opening original: {orig_url}")
            await p1.goto(orig_url, timeout=MAX_WAIT_SEC * 1000, wait_until="load")
            await asyncio.sleep(POST_LOAD_WAIT_SEC)
            h1 = await p1.content()
            await p1.screenshot(path=orig_path, full_page=True)
        except PlaywrightTimeout:
            logging.warning(f"Original page timed out ({orig_url})")
        except Exception as e:
            logging.warning(f"Original page failed ({orig_url}): {e}")

        # --- Candidate
        try:
            logging.info(f"Opening candidate: {cand_url}")
            await p2.goto(cand_url, timeout=MAX_WAIT_SEC * 1000, wait_until="load")
            await asyncio.sleep(POST_LOAD_WAIT_SEC)
            h2 = await p2.content()
            await p2.screenshot(path=cand_path, full_page=True)
        except PlaywrightTimeout:
            logging.warning(f"Candidate timed out ({cand_url})")
        except Exception as e:
            logging.warning(f"Candidate failed ({cand_url}): {e}")

        await browser.close()
        return h1, h2

def capture_screens(orig_url: str, cand_url: str, out_dir="screens"):
    os.makedirs(out_dir, exist_ok=True)
    op = os.path.join(out_dir, f"orig_{_safe_name(orig_url)}.png")
    cp = os.path.join(out_dir, f"cand_{_safe_name(cand_url)}.png")
    oh = op.replace(".png", ".html")
    ch = cp.replace(".png", ".html")
    h1, h2 = asyncio.run(_pair(orig_url, cand_url, op, cp))
    open(oh, "w", encoding="utf-8", errors="ignore").write(h1 or "")
    open(ch, "w", encoding="utf-8", errors="ignore").write(h2 or "")
    return {"orig": op, "cand": cp, "orig_html": oh, "cand_html": ch}