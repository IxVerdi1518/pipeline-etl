from pathlib import Path
import json
import pandas as pd
import sys

# Allow running as module (`python -m src.transform`) and as script (`python src/transform.py`).
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.logger import get_logger
from src.utils import DATA_DIR, ensure_dir

logger = get_logger("transform")

BRONZE_DIR = DATA_DIR / "bronze" / "coins_markets"
SILVER_DIR = DATA_DIR / "silver" / "coins_markets"

SILVER_COLUMNS =[
    "snapshot_utc",
    "id",
    "symbol",
    "name",
    "current_price",
    "market_cap",
    "market_cap_rank",
    "total_volume",
    "high_24h",
    "low_24h",
    "price_change_percentage_1h_in_currency",
    "price_change_percentage_24h_in_currency",
    "price_change_percentage_7d_in_currency",
    "last_updated"
]

NUMERIC_COLS = [
    "current_price",
    "market_cap",
    "market_cap_rank",
    "total_volume",
    "high_24h",
    "low_24h",
    "price_change_percentage_1h_in_currency",
    "price_change_percentage_24h_in_currency",
    "price_change_percentage_7d_in_currency"
]

def find_latest_bronze_file() -> Path:
    files = sorted(BRONZE_DIR.glob("coins_markets_*.json"))
    if not files:
        raise FileNotFoundError(f"No bronze files found in {BRONZE_DIR}")
    return files[-1]

def read_bronze_file(file_path: Path) -> dict:
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return payload

def normalize_to_df(payload: dict) -> pd.DataFrame:
    snapshot_utc = payload["meta"]["fetched_at_utc"]
    data = payload["data"]
    df = pd.json_normalize(data)

    df.insert(0, "snapshot_utc", snapshot_utc)
    return df

def enforce_schema(df: pd.DataFrame) -> pd.DataFrame:
    # Asegura todas las columnas objetivo (si falta alguna, la crea en NaN)
    for col in SILVER_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df = df[SILVER_COLUMNS].copy()

    # Tipos numéricos
    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Timestamps
    # snapshot_utc viene como ISO-8601 (ej: 2026-03-02T16:05:22Z)
    df["snapshot_utc"] = pd.to_datetime(df["snapshot_utc"], utc=True, errors="coerce")
    df["last_updated"] = pd.to_datetime(df["last_updated"], utc=True, errors="coerce")

    # Limpieza de strings
    for col in ["id", "symbol", "name"]:
        df[col] = df[col].astype("string").str.strip()

    return df

def quality_checks(df: pd.DataFrame) -> None:
    # Checks simples pero reales
    if df.empty:
        raise ValueError("Silver DF está vacío")

    if df["id"].isna().mean() > 0.05:
        raise ValueError("Muchos IDs nulos (>5%)")

    # Precio no debería ser negativo (si lo fuese, lo marcamos como issue)
    neg_prices = (df["current_price"] < 0).sum()
    if neg_prices > 0:
        logger.warning(f"Hay {neg_prices} precios negativos (revisar fuente)")

def write_silver(df: pd.DataFrame) -> Path:
    # Partición por fecha (YYYY-MM-DD) basada en snapshot_utc
    part_date = df["snapshot_utc"].dt.strftime("%Y-%m-%d").iloc[0]
    out_dir = SILVER_DIR / f"snapshot_date={part_date}"
    ensure_dir(out_dir)

    out_path = out_dir / "coins_markets.parquet"
    df.to_parquet(out_path, index=False)
    logger.info(f"Saved silver parquet: {out_path}")

    # opcional: CSV limpio para inspección rápida
    csv_path = out_dir / "coins_markets.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Saved silver csv: {csv_path}")

    return out_path

if __name__ == "__main__":
    latest = find_latest_bronze_file()
    logger.info(f"Latest bronze: {latest.name}")

    payload = read_bronze_file(latest)
    df_raw = normalize_to_df(payload)
    df_silver = enforce_schema(df_raw)

    quality_checks(df_silver)
    logger.info(f"Silver rows={len(df_silver)} cols={len(df_silver.columns)}")

    write_silver(df_silver)
