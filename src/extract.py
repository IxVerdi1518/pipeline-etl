import sys
import time
from pathlib import Path
from typing import Optional

import requests

# Allow running as module (`python -m src.extract`) and as script (`python src/extract.py`).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.logger import get_logger
from src.utils import DATA_DIR, utc_timestamp, save_json

logger = get_logger("extract")

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

def fetch_market_snapshot(vs_currency: str = "usd", per_page: int = 50, page: int = 1) -> dict:
    """
    Trae un snapshot de mercado (precio, market cap, volumen, etc.) para N monedas.
    Fuente: /coins/markets
    """
    url = f"{COINGECKO_BASE}/coins/markets"
    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": per_page,
        "page": page,
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d",
    }
    return request_with_retries(url, params=params)

def request_with_retries(url: str, params: Optional[dict] = None, retries: int = 3, timeout: int = 20) -> dict:
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"GET {url} attempt={attempt}/{retries}")
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return {
                "meta": {
                    "source": "coingecko",
                    "url": url,
                    "params": params,
                    "fetched_at_utc": utc_timestamp(),
                    "status_code": resp.status_code,
                },
                "data": resp.json(),
            }
        except Exception as e:
            last_err = e
            wait = 2 ** attempt
            logger.warning(f"Error: {e} | retry in {wait}s")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {retries} retries: {last_err}")

def write_bronze(payload: dict, dataset_name: str) -> Path:
    ts = payload["meta"]["fetched_at_utc"]
    out_path = DATA_DIR / "bronze" / dataset_name / f"{dataset_name}_{ts}.json"
    save_json(payload, out_path)
    logger.info(f"Saved bronze: {out_path}")
    return out_path

if __name__ == "__main__":
    payload = fetch_market_snapshot(vs_currency="usd", per_page=50, page=1)
    write_bronze(payload, dataset_name="coins_markets")
