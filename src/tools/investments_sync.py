"""Investment Sync Tools - IBKR + Bitget -> Notion Transactions DB (idempotent)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_notion_client():
    try:
        from notion_client import Client
        from src.core.config import settings

        if not settings.notion.api_key:
            return None
        return Client(auth=settings.notion.api_key.get_secret_value())
    except Exception:
        return None


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> float | None:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _upsert_transaction(
    *,
    client,
    database_id: str,
    external_id: str,
    name: str,
    date_iso: str,
    broker: str,
    product: str | None,
    symbol: str | None,
    side: str | None,
    qty: float | None,
    price: float | None,
    fees: float | None,
    currency: str | None,
    account: str | None,
    raw: dict[str, Any],
) -> dict[str, Any]:
    """Upsert by External ID (rich_text equals)."""
    # Query existing
    if hasattr(client, "databases") and hasattr(client.databases, "query"):
        existing = client.databases.query(
            database_id=database_id,
            filter={"property": "External ID", "rich_text": {"equals": external_id}},
            page_size=1,
        )
    elif hasattr(client, "data_sources") and hasattr(client.data_sources, "query"):
        existing = client.data_sources.query(
            data_source_id=database_id,
            filter={"property": "External ID", "rich_text": {"equals": external_id}},
            page_size=1,
        )
    else:
        raise AttributeError("Notion client has no databases.query nor data_sources.query")

    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Date": {"date": {"start": date_iso}},
        "Broker": {"select": {"name": broker}},
        "External ID": {"rich_text": [{"text": {"content": external_id}}]},
    }

    if product:
        props["Product"] = {"select": {"name": product}}
    if symbol:
        props["Symbol"] = {"rich_text": [{"text": {"content": symbol}}]}
    if side:
        props["Side"] = {"select": {"name": side}}
    if qty is not None:
        props["Quantity"] = {"number": float(qty)}
    if price is not None:
        props["Price"] = {"number": float(price)}
    if fees is not None:
        props["Fees"] = {"number": float(fees)}
    if currency:
        props["Currency"] = {"select": {"name": currency}}
    if account:
        props["Account"] = {"rich_text": [{"text": {"content": account}}]}

    # Keep raw compact (Notion rich_text limit is small; keep it short)
    raw_str = json.dumps(raw, ensure_ascii=False)[:1800]
    props["Raw"] = {"rich_text": [{"text": {"content": raw_str}}]}

    if existing.get("results"):
        page_id = existing["results"][0]["id"]
        client.pages.update(page_id=page_id, properties=props)
        return {"action": "updated", "id": page_id}

    try:
        created = client.pages.create(parent={"database_id": database_id}, properties=props)
    except Exception:
        created = client.pages.create(parent={"data_source_id": database_id}, properties=props)
    return {"action": "created", "id": created["id"], "url": created.get("url", "")}


def _fetch_ibkr_flex_trades(days: int) -> list[dict[str, Any]]:
    """Fetch trades from IBKR Flex Web Service (requires IBKR_FLEX_TOKEN, IBKR_FLEX_QUERY_ID)."""
    from src.core.config import settings

    if not settings.ibkr.flex_token or not settings.ibkr.flex_query_id:
        raise ValueError("IBKR no configurado: faltan IBKR_FLEX_TOKEN y/o IBKR_FLEX_QUERY_ID en .env")

    try:
        import httpx
        import xml.etree.ElementTree as ET

        token = settings.ibkr.flex_token.get_secret_value()
        qid = settings.ibkr.flex_query_id

        # 1) SendRequest -> reference code
        # IBKR Flex Web Service frequently returns HTTP 302 to ndcdyn.interactivebrokers.com.
        # Official behavior: clients should follow redirects.
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0),
            headers={"User-Agent": "SPESION/1.0"},
        ) as client:
            # 1) SendRequest -> reference code
            send_url = "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest"
            r = client.get(send_url, params={"t": token, "q": qid, "v": "3"})
            r.raise_for_status()
            root = ET.fromstring(r.text)
            ref_code = root.attrib.get("referenceCode") or root.findtext("ReferenceCode")
            if not ref_code:
                raise ValueError(f"IBKR Flex SendRequest failed: {r.text[:300]}")

            # 2) GetStatement -> XML payload (must use same client to follow redirects)
            get_url = "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement"
            r2 = client.get(get_url, params={"t": token, "q": ref_code, "v": "3"})
            r2.raise_for_status()
            root2 = ET.fromstring(r2.text)

        # Trades appear under <Trades> / <Trade> entries
        # XML structure: <Trade dateTime="2025-03-24;04:04:07" tradeDate="2025-03-24" ... />
        trades: list[dict[str, Any]] = []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for elem in root2.iter():
            tag = elem.tag.lower()
            if tag == "trade":  # Exact match for <Trade> elements
                row = dict(elem.attrib)
                row_lc = {str(k).lower(): v for k, v in row.items()}
                
                # IBKR Flex XML uses: dateTime (with semicolon) or tradeDate (YYYY-MM-DD)
                # Priority: dateTime > tradeDate > other date fields
                dt_raw = (
                    row_lc.get("datetime")  # dateTime becomes datetime (lowercase)
                    or row_lc.get("tradedate")
                    or row_lc.get("tradedatetime")
                    or row_lc.get("date/time")
                    or row_lc.get("reportdate")
                    or row_lc.get("date")
                )
                
                # Keep row with lowercase lookup dict for later processing
                row["_dt_raw"] = dt_raw
                row["_lc"] = row_lc
                trades.append(row)

        # Filter by date - only skip if we can parse date AND it's before cutoff
        # If date parsing fails, include the trade (safer for backfill)
        out: list[dict[str, Any]] = []
        for t in trades:
            dt_raw = str(t.get("_dt_raw") or "")
            dt_obj: datetime | None = None
            
            if dt_raw:
                try:
                    from dateutil import parser as date_parser

                    # IBKR uses semicolon separator: "2025-03-24;04:04:07" or just "2025-03-24"
                    cleaned = dt_raw.replace(";", " ").strip()
                    if cleaned:
                        # dayfirst=False because IBKR uses YYYY-MM-DD format
                        dt_obj = date_parser.parse(cleaned, dayfirst=False, fuzzy=True)
                        if dt_obj.tzinfo is None:
                            dt_obj = dt_obj.replace(tzinfo=timezone.utc)
                        
                        # Only filter out if date is definitely before cutoff
                        if dt_obj < cutoff:
                            continue
                except Exception:
                    # If date parsing fails, include the trade (safer for backfill)
                    pass
            
            out.append(t)

        logger.info(f"IBKR Flex: encontrados {len(out)} trades (de {len(trades)} totales) dentro del rango de {days} días")
        return out
    except Exception as e:
        raise ValueError(f"IBKR Flex error: {e}")


def _fetch_bitget_trades(days: int) -> list[dict[str, Any]]:
    """Fetch trades using ccxt (requires BITGET_API_KEY/SECRET/PASSPHRASE)."""
    from src.core.config import settings

    if not settings.bitget.api_key or not settings.bitget.api_secret or not settings.bitget.passphrase:
        raise ValueError("Bitget no configurado: faltan BITGET_API_KEY / BITGET_API_SECRET / BITGET_PASSPHRASE")

    try:
        import ccxt  # type: ignore

        ex = ccxt.bitget({
            "apiKey": settings.bitget.api_key.get_secret_value(),
            "secret": settings.bitget.api_secret.get_secret_value(),
            "password": settings.bitget.passphrase.get_secret_value(),
            "enableRateLimit": True,
            "options": {"defaultType": settings.bitget.default_type},
        })

        since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)

        # ccxt requires symbol for some exchanges; we try a best-effort approach:
        # - load markets
        # - fetch trades for a limited set of active markets (top N)
        ex.load_markets()
        symbols = [s for s in ex.symbols][:25]  # cap to avoid rate limit

        all_trades: list[dict[str, Any]] = []
        for sym in symbols:
            try:
                trades = ex.fetch_my_trades(symbol=sym, since=since_ms, limit=50)
                for t in trades:
                    all_trades.append(t)
            except Exception:
                continue

        # Deduplicate by (id, symbol) if available
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for t in all_trades:
            tid = str(t.get("id") or "")
            sym = str(t.get("symbol") or "")
            key = f"{tid}:{sym}"
            if tid and key in seen:
                continue
            seen.add(key)
            out.append(t)
        return out
    except ImportError:
        raise ValueError("Falta dependencia: instala ccxt")
    except Exception as e:
        raise ValueError(f"Bitget ccxt error: {e}")


@tool
def sync_investments_to_notion(days: int = 7, include_ibkr: bool = True, include_bitget: bool = True) -> dict[str, Any]:
    """Sincroniza trades/movimientos desde IBKR + Bitget y los guarda en Notion (sin duplicados)."""
    from src.core.config import settings

    client = _get_notion_client()
    if client is None:
        return {"error": "Notion no disponible"}

    if not settings.notion.transactions_database_id:
        return {"error": "Transactions DB no configurada. Ejecuta setup_transactions_database primero."}

    db_id = settings.notion.transactions_database_id

    created = 0
    updated = 0
    errors: list[str] = []

    # IBKR
    if include_ibkr:
        try:
            trades = _fetch_ibkr_flex_trades(days=days)
            for tr in trades:
                lc: dict[str, Any] = tr.get("_lc") or {str(k).lower(): v for k, v in tr.items()}

                def pick(*keys: str) -> Any:
                    for k in keys:
                        if k in lc and lc[k] not in (None, ""):
                            return lc[k]
                    return None

                # IBKR Flex XML attribute mapping (case-insensitive via _lc dict)
                # XML: <Trade tradeID="..." buySell="BUY" tradePrice="4.29" quantity="67" ... />
                sym = pick("symbol", "conid", "description") or ""
                side = str(pick("buysell", "side") or "").upper()
                side = "BUY" if side.startswith("B") else "SELL" if side.startswith("S") else None
                qty = _safe_float(pick("quantity", "qty"))
                price = _safe_float(pick("tradeprice", "price"))
                fees = _safe_float(pick("ibcommission", "commission", "fees", "taxes"))
                ccy = pick("currency", "tradecurrency", "currencyprimary")
                acct = pick("accountid", "account", "clientaccountid") or ""

                # Date parsing: use _dt_raw (already extracted) or fallback
                dt_raw = str(tr.get("_dt_raw") or pick("datetime", "tradedate", "tradedatetime", "reportdate") or "")
                date_iso = datetime.now(timezone.utc).date().isoformat()
                try:
                    from dateutil import parser as date_parser

                    cleaned = dt_raw.replace(";", " ").strip()
                    if cleaned:
                        dt = date_parser.parse(cleaned, dayfirst=False, fuzzy=True)
                        date_iso = dt.date().isoformat()
                except Exception:
                    # Fallback to today if parsing fails
                    pass

                # Trade ID: IBKR uses tradeID (or transactionID in some cases)
                trade_id = pick("tradeid", "transactionid")
                external_id = f"ibkr:{acct}:{trade_id or json.dumps(lc, sort_keys=True)[:120]}"

                res = _upsert_transaction(
                    client=client,
                    database_id=db_id,
                    external_id=external_id,
                    name=f"IBKR {side or ''} {sym}".strip(),
                    date_iso=date_iso,
                    broker="IBKR",
                    product="Stock",
                    symbol=str(sym)[:80] if sym else None,
                    side=side,
                    qty=qty,
                    price=price,
                    fees=fees,
                    currency=str(ccy)[:10] if ccy else None,
                    account=str(acct)[:80] if acct else None,
                    raw=lc,
                )
                if res["action"] == "created":
                    created += 1
                else:
                    updated += 1
        except Exception as e:
            errors.append(str(e))

    # Bitget
    if include_bitget:
        try:
            trades = _fetch_bitget_trades(days=days)
            for tr in trades:
                ts = tr.get("timestamp")
                dt = datetime.fromtimestamp((ts or 0) / 1000, tz=timezone.utc) if ts else datetime.now(timezone.utc)
                date_iso = dt.date().isoformat()

                sym = tr.get("symbol") or ""
                side = (tr.get("side") or "").upper()
                side = "BUY" if side.startswith("B") else "SELL" if side.startswith("S") else None
                qty = _safe_float(tr.get("amount"))
                price = _safe_float(tr.get("price"))
                fee = tr.get("fee") or {}
                fees = _safe_float(fee.get("cost")) if isinstance(fee, dict) else None
                ccy = None
                if isinstance(fee, dict):
                    ccy = fee.get("currency")

                tid = tr.get("id") or tr.get("order") or tr.get("orderId") or ""
                external_id = f"bitget:{sym}:{tid}"

                res = _upsert_transaction(
                    client=client,
                    database_id=db_id,
                    external_id=external_id,
                    name=f"Bitget {side or ''} {sym}".strip(),
                    date_iso=date_iso,
                    broker="Bitget",
                    product="Spot",
                    symbol=str(sym)[:80] if sym else None,
                    side=side,
                    qty=qty,
                    price=price,
                    fees=fees,
                    currency=str(ccy)[:10] if ccy else None,
                    account=None,
                    raw=tr,
                )
                if res["action"] == "created":
                    created += 1
                else:
                    updated += 1
        except Exception as e:
            errors.append(str(e))

    return {
        "success": len(errors) == 0,
        "created": created,
        "updated": updated,
        "errors": errors,
        "days": days,
    }


def create_investment_sync_tools() -> list:
    return [sync_investments_to_notion]

