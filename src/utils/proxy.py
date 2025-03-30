import logging

import httpx

from src.config.config import CONFIG


def create_proxy_client() -> httpx.Client | None:
    """
    Creates an HTTP client with proxy settings.
    If USE_PROXY=False, returns None.

    Returns
    -------
    httpx.Client | None
        Configured HTTP client with proxy or None.
    """
    if CONFIG.PROXY.USE_PROXY is False:
        logging.info("Proxy is disabled in the configuration.")
        return None

    proxy_url = f"socks5://{CONFIG.PROXY.USERNAME}:{CONFIG.PROXY.PASSWORD}@{CONFIG.PROXY.HOST}:{CONFIG.PROXY.PORT}"
    return httpx.Client(
        proxies={
            "http://": proxy_url,
            "https://": proxy_url
        }
    )
