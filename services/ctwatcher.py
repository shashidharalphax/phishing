import os
import time
import random
import threading
import logging

import certstream

log = logging.getLogger("phishguard.ctwatcher")
DEFAULT_URL = "wss://certstream.calidog.io/"

def _run_certstream(stop_event: threading.Event, url: str):
    def handle_event(message, context):
        if message.get("message_type") != "certificate_update":
            return
        domains = message["data"]["leaf_cert"].get("all_domains") or []
        # TODO: push domains to your queue/DB

    backoff = 1
    while not stop_event.is_set():
        try:
            log.info("Connecting to CertStream: %s", url)
            # This call blocks until the connection drops or stop_event is set
            certstream.listen_for_events(handle_event, url=url, skip_heartbeats=True)
            backoff = 1  # reset if we return normally
        except Exception as e:
            log.warning("CertStream connection lost: %s", e)
            sleep_for = min(60, backoff) + random.random() * 0.5
            if stop_event.wait(sleep_for):
                break
            backoff = min(60, backoff * 2)

def attach_ctwatcher(app, *, enabled: bool | None = None, url: str | None = None):
    enabled = (os.getenv("ENABLE_CT_WATCHER", "1") == "1") if enabled is None else enabled
    if not enabled:
        log.info("CT watcher disabled")
        return

    url = url or os.getenv("CERTSTREAM_URL", DEFAULT_URL)
    stop_event = threading.Event()

    @app.on_event("startup")
    async def _start_ctwatcher():
        app.state.ct_stop_event = stop_event
        app.state.ct_thread = threading.Thread(
            target=_run_certstream, args=(stop_event, url), daemon=True
        )
        app.state.ct_thread.start()
        log.info("CT watcher started")

    @app.on_event("shutdown")
    async def _stop_ctwatcher():
        stop_event.set()
        t = getattr(app.state, "ct_thread", None)
        if t:
            t.join(timeout=5)
        log.info("CT watcher stopped")