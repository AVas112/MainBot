import httpx
import logging

from src.config.config import CONFIG


def create_proxy_client() -> httpx.Client | None:
    """
    Создает HTTP клиент с настройками прокси.
    Если USE_PROXY=False, возвращает None.

    Returns
    -------
    httpx.Client | None
        Настроенный HTTP клиент с прокси или None.
    """
    if CONFIG.PROXY.USE_PROXY is False:
        logging.info("Прокси отключен в конфигурации.")
        return None

    proxy_url = f"socks5://{CONFIG.PROXY.USERNAME}:{CONFIG.PROXY.PASSWORD}@{CONFIG.PROXY.HOST}:{CONFIG.PROXY.PORT}"
    return httpx.Client(
        proxies={
            "http://": proxy_url,
            "https://": proxy_url
        }
    )
