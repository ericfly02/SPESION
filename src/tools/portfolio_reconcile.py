"""Portfolio reconcile - derive holdings from Transactions DB and update Finance Portfolio DB."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@dataclass
class Position:
    qty: float = 0.0
    cost_eur: float = 0.0  # cost basis in EUR (including fees)
    currency: str | None = None
    kind: str | None = None  # "Crypto" | "Stock" | "ETF" (best-effort)


def _safe_float(x: Any) -> float:
    try:
        if x is None or x == "":
            return 0.0
        return float(x)
    except Exception:
        return 0.0


def _fx_to_eur(currency: str) -> float | None:
    """Return multiplier to convert 1 unit of `currency` to EUR."""
    c = (currency or "").upper().strip()
    if not c:
        return None
    if c in {"EUR"}:
        return 1.0
    if c in {"USDT"}:
        c = "USD"

    try:
        import yfinance as yf

        # yfinance fx tickers use e.g. EURUSD=X (USD per 1 EUR)
        if c == "USD":
            t = yf.Ticker("EURUSD=X")
            px = float(t.info.get("regularMarketPrice") or 0)
            if px > 0:
                return 1.0 / px
            return None

        # generic: EUR{CCY}=X gives CCY per EUR, so 1 CCY = 1/(EURCCY) EUR
        pair = f"EUR{c}=X"
        t = yf.Ticker(pair)
        px = float(t.info.get("regularMarketPrice") or 0)
        if px > 0:
            return 1.0 / px
        return None
    except Exception:
        return None


def _current_price_eur(symbol: str) -> tuple[float | None, str | None]:
    """Best-effort current price in EUR for a symbol."""
    s = (symbol or "").strip()
    if not s:
        return None, None

    # Crypto pair like BTC/USDT -> BTC-USD
    is_crypto = "/" in s
    base = s.split("/")[0] if is_crypto else s

    try:
        import yfinance as yf

        if is_crypto:
            t = yf.Ticker(f"{base}-USD")
            px_usd = float(t.info.get("regularMarketPrice") or 0)
            fx = _fx_to_eur("USD")
            if px_usd > 0 and fx:
                return px_usd * fx, "EUR"
            return None, None

        t = yf.Ticker(base)
        info = t.info
        px = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
        ccy = (info.get("currency") or "").upper()
        if px <= 0:
            return None, None
        fx = _fx_to_eur(ccy) if ccy else None
        if fx:
            return px * fx, "EUR"
        # If unknown currency, return raw price without conversion (caller decides)
        return px, ccy or None
    except Exception:
        return None, None


def _state_path() -> Path:
    p = Path("data/portfolio_reconcile_state.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@tool
def update_finance_portfolio_from_transactions(
    days: int | None = None,
    force_full_rebuild: bool = False,
) -> dict[str, Any]:
    """Updates Finance Portfolio DB using Transactions DB as source-of-truth.

    - Aggregates BUY/SELL transactions into holdings.
    - Computes avg cost (EUR) best-effort using FX.
    - Updates Notion Finance Portfolio via add_portfolio_holding.
    """
    from src.core.config import settings

    if not settings.notion.transactions_database_id:
        return {"error": "Transactions DB no configurada (NOTION_TRANSACTIONS_DATABASE_ID)."}
    if not settings.notion.finance_database_id:
        return {"error": "Finance Portfolio DB no configurada (NOTION_FINANCE_DATABASE_ID)."}

    # Determine start_date window
    start_date: str
    last_run: str | None = None
    
    # Check state unless forced rebuild
    if not force_full_rebuild:
        try:
            payload = json.loads(_state_path().read_text(encoding="utf-8"))
            last_run = payload.get("last_run")
        except Exception:
            last_run = None

    # Logic:
    # 1. If days provided (explicit override) -> Windowed mode (ignore last_run)
    # 2. If last_run exists -> Incremental mode
    # 3. Default -> Windowed mode (365 days)
    
    if days is not None:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        mode = "windowed_explicit"
    elif last_run and not force_full_rebuild:
        # Re-run 1 day overlap for safety
        dt = datetime.strptime(last_run, "%Y-%m-%d") - timedelta(days=1)
        start_date = dt.strftime("%Y-%m-%d")
        mode = "incremental"
    else:
        # Default fallback
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        mode = "windowed_default"

    # Fetch transactions
    from src.tools.notion_mcp import get_transactions, get_portfolio_holdings, add_portfolio_holding

    logger.info(f"Portfolio reconcile: fetching transactions desde {start_date} (mode: {mode})")
    txs = get_transactions.invoke({"start_date": start_date, "limit": 500})
    if isinstance(txs, list) and txs and isinstance(txs[0], dict) and txs[0].get("error"):
        return {"error": txs[0]["error"]}
    
    if not txs or len(txs) == 0:
        logger.warning(f"Portfolio reconcile: no se encontraron transacciones desde {start_date}")
        return {
            "success": True,
            "mode": mode,
            "start_date": start_date,
            "created": 0,
            "updated": 0,
            "skipped_zero_qty": 0,
            "message": "No transactions found in the date range",
        }
    
    logger.info(f"Portfolio reconcile: encontradas {len(txs)} transacciones")

    # Current holdings map (to preserve category/type when present)
    existing = get_portfolio_holdings.invoke({})
    existing_map: dict[str, dict[str, Any]] = {}
    if isinstance(existing, list):
        for h in existing:
            if isinstance(h, dict) and h.get("ticker"):
                existing_map[str(h["ticker"]).upper()] = h

    positions: dict[str, Position] = defaultdict(Position)
    realized_pnl_eur = 0.0
    fx_missing = 0

    # Apply transactions
    processed_count = 0
    buy_count = 0
    sell_count = 0
    skipped_count = 0
    
    for tx in (txs or []):
        if not isinstance(tx, dict) or tx.get("error"):
            skipped_count += 1
            continue

        side = (tx.get("side") or "").upper()
        if side not in {"BUY", "SELL"}:
            skipped_count += 1
            continue

        symbol = (tx.get("symbol") or "").strip()
        if not symbol:
            skipped_count += 1
            continue
        
        processed_count += 1
        if side == "BUY":
            buy_count += 1
        else:
            sell_count += 1

        qty = _safe_float(tx.get("quantity"))
        price = _safe_float(tx.get("price"))
        fees = _safe_float(tx.get("fees"))
        ccy = (tx.get("currency") or "").upper()

        fx = _fx_to_eur(ccy) if ccy else None
        if fx is None:
            fx_missing += 1
            # Skip FX conversion rather than hallucinate: treat as EUR if unknown
            fx = 1.0

        # Normalize ticker key for portfolio DB:
        # - crypto pairs: BTC/USDT -> BTC
        ticker_key = symbol.split("/")[0].upper() if "/" in symbol else symbol.upper()

        pos = positions[ticker_key]
        pos.currency = "EUR"
        pos.kind = "Crypto" if "/" in symbol else "Stock"

        gross = qty * price
        total_cost_eur = (gross + fees) * fx

        if side == "BUY":
            pos.cost_eur += total_cost_eur
            pos.qty += qty
        else:  # SELL
            if pos.qty > 0:
                avg_cost = pos.cost_eur / pos.qty if pos.qty else 0.0
                cost_removed = avg_cost * qty
                proceeds = (gross - fees) * fx
                realized_pnl_eur += (proceeds - cost_removed)
                pos.cost_eur = max(0.0, pos.cost_eur - cost_removed)
                pos.qty = pos.qty - qty
            else:
                # No position tracked: ignore to avoid corrupting
                continue
    
    logger.info(f"Portfolio reconcile: procesadas {processed_count} transacciones ({buy_count} BUY, {sell_count} SELL, {skipped_count} skipped)")
    logger.info(f"Portfolio reconcile: calculadas {len(positions)} posiciones únicas")

    # Upsert portfolio holdings
    updated = 0
    created = 0
    skipped = 0
    errors: list[str] = []

    for ticker, pos in positions.items():
        if abs(pos.qty) < 1e-9:
            skipped += 1
            continue

        avg_cost_eur = (pos.cost_eur / pos.qty) if pos.qty else 0.0
        cur_px, cur_ccy = _current_price_eur(ticker if pos.kind != "Crypto" else f"{ticker}/USDT")
        if cur_px is None:
            # no price: use avg cost to compute value
            cur_px = avg_cost_eur if avg_cost_eur > 0 else None

        market_value = (pos.qty * cur_px) if cur_px else pos.cost_eur

        prev = existing_map.get(ticker)
        category = (prev or {}).get("category") or ("Speculative" if pos.kind == "Crypto" else "Core")
        typ = (prev or {}).get("type") or ("Crypto" if pos.kind == "Crypto" else "Stock")

        logger.debug(f"Portfolio reconcile: upserting {ticker} - qty={pos.qty:.4f}, cost_eur={pos.cost_eur:.2f}, market_value={market_value:.2f}")
        
        res = add_portfolio_holding.invoke({
            "ticker": ticker,
            "amount": float(market_value),
            "quantity": float(pos.qty),
            "type": typ,
            "category": category,
            "avg_price": float(avg_cost_eur) if avg_cost_eur else None,
            "current_price": float(cur_px) if cur_px else None,
        })

        if isinstance(res, dict) and res.get("success"):
            if res.get("action") == "created":
                created += 1
                logger.info(f"Portfolio reconcile: creado holding {ticker}")
            else:
                updated += 1
                logger.info(f"Portfolio reconcile: actualizado holding {ticker}")
        else:
            error_msg = str(res)
            errors.append(error_msg)
            logger.error(f"Portfolio reconcile: error upserting {ticker}: {error_msg}")

    # Save state
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        _state_path().write_text(json.dumps({"last_run": today}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    result = {
        "success": len(errors) == 0,
        "mode": mode,
        "start_date": start_date,
        "transactions_found": len(txs) if txs else 0,
        "transactions_processed": processed_count,
        "buy_count": buy_count,
        "sell_count": sell_count,
        "positions_calculated": len(positions),
        "created": created,
        "updated": updated,
        "skipped_zero_qty": skipped,
        "fx_missing_assumed_eur": fx_missing,
        "realized_pnl_eur_est": round(realized_pnl_eur, 2),
        "errors": errors[:5],
    }
    
    logger.info(f"Portfolio reconcile: completado - {created} creados, {updated} actualizados, {skipped} skipped, {len(errors)} errores")
    
    return result


def create_portfolio_reconcile_tools() -> list:
    return [update_finance_portfolio_from_transactions]

