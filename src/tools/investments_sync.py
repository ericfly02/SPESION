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


def _normalize_database_id(db_id: str) -> str:
    """Normalize Notion database ID: add dashes if missing."""
    if not db_id:
        return db_id
    clean = db_id.replace("-", "")
    if len(clean) == 32:
        return f"{clean[0:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
    return db_id


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
    # Normalize database ID
    db_id_normalized = _normalize_database_id(database_id)
    
    # Query existing
    if hasattr(client, "databases") and hasattr(client.databases, "query"):
        existing = client.databases.query(
            database_id=db_id_normalized,
            filter={"property": "External ID", "rich_text": {"equals": external_id}},
            page_size=1,
        )
    elif hasattr(client, "data_sources") and hasattr(client.data_sources, "query"):
        existing = client.data_sources.query(
            data_source_id=db_id_normalized,
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
        created = client.pages.create(parent={"database_id": db_id_normalized}, properties=props)
    except Exception:
        created = client.pages.create(parent={"data_source_id": db_id_normalized}, properties=props)
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
            
            logger.info(f"IBKR Flex SendRequest: reference code = {ref_code}")

            # 2) GetStatement -> XML payload (must use same client to follow redirects)
            # IBKR statements can take a few seconds to generate, so we wait and retry if needed
            import time
            get_url = "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement"
            
            max_retries = 3
            wait_seconds = 5
            r2 = None
            
            for attempt in range(max_retries):
                if attempt > 0:
                    logger.info(f"IBKR Flex GetStatement: intento {attempt + 1}/{max_retries}, esperando {wait_seconds}s...")
                    time.sleep(wait_seconds)
                
                r2 = client.get(get_url, params={"t": token, "q": ref_code, "v": "3"})
                r2.raise_for_status()
                
                # Quick check: if response is very small (< 500 bytes), it's likely an error
                # Wait and retry
                if len(r2.text) < 500:
                    xml_preview = ET.fromstring(r2.text)
                    error_elem = xml_preview.find(".//ErrorCode")
                    if error_elem is not None:
                        error_code = error_elem.text
                        # Error 1019 = "Statement generation in progress"
                        if error_code == "1019" and attempt < max_retries - 1:
                            logger.warning(f"IBKR Flex: statement aún generándose (error 1019), reintentando...")
                            continue
                
                # If we got here, either it's ready or it's a different error
                break
            
            if r2 is None:
                raise ValueError("IBKR Flex GetStatement: no se pudo obtener el statement después de varios intentos")
            
            # Debug: log XML response size and first 500 chars
            xml_text = r2.text
            logger.info(f"IBKR Flex GetStatement: recibidos {len(xml_text)} bytes de XML")
            logger.debug(f"IBKR Flex XML (primeros 500 chars): {xml_text[:500]}")
            
            root2 = ET.fromstring(xml_text)
            
            # Check for error response from IBKR BEFORE processing trades
            error_code_elem = root2.find(".//ErrorCode")
            error_msg_elem = root2.find(".//ErrorMessage")
            status_elem = root2.find(".//Status")
            
            if error_code_elem is not None or error_msg_elem is not None:
                error_code = error_code_elem.text if error_code_elem is not None else "Unknown"
                error_msg = error_msg_elem.text if error_msg_elem is not None else "No error message"
                status = status_elem.text if status_elem is not None else "Unknown"
                
                error_detail = f"IBKR Flex Error: Code={error_code}, Status={status}, Message={error_msg}"
                logger.error(error_detail)
                logger.error(f"IBKR Flex XML completo: {xml_text}")
                
                # Common issues and solutions
                if "1019" in str(error_code) or "not ready" in error_msg.lower():
                    error_detail += " (El statement aún no está listo. Espera 10-30 segundos y vuelve a intentar.)"
                elif "1018" in str(error_code) or "invalid" in error_msg.lower():
                    error_detail += " (Query ID inválido o token expirado. Verifica IBKR_FLEX_QUERY_ID y IBKR_FLEX_TOKEN.)"
                
                raise ValueError(error_detail)

        # Trades appear under <Trades> / <Trade> entries
        # XML structure: <Trade dateTime="2025-03-24;04:04:07" tradeDate="2025-03-24" ... />
        trades: list[dict[str, Any]] = []
        
        # Debug: count all elements and find Trades container
        all_tags = {}
        for elem in root2.iter():
            tag = elem.tag
            all_tags[tag] = all_tags.get(tag, 0) + 1
        
        logger.info(f"IBKR Flex XML: elementos encontrados: {dict(sorted(all_tags.items()))}")

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        logger.info(f"IBKR Flex: cutoff date = {cutoff.isoformat()} (últimos {days} días)")

        # Find all Trade elements - try multiple approaches
        # Approach 1: Direct iteration (works for most cases)
        for elem in root2.iter():
            tag = elem.tag
            # Handle namespaces: strip namespace prefix if present
            tag_clean = tag.split("}")[-1] if "}" in tag else tag
            tag_lower = tag_clean.lower()
            
            if tag_lower == "trade":  # Exact match for <Trade> elements
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
                
                # Debug: log first few trades
                if len(trades) < 3:
                    logger.info(f"IBKR Trade #{len(trades)+1}: symbol={row_lc.get('symbol')}, dt_raw={dt_raw}, tradeID={row_lc.get('tradeid')}")
                
                # Keep row with lowercase lookup dict for later processing
                row["_dt_raw"] = dt_raw
                row["_lc"] = row_lc
                trades.append(row)
        
        # Approach 2: If no trades found, try finding <Trades> container explicitly
        if len(trades) == 0:
            logger.warning("IBKR Flex: no se encontraron trades con iter(), intentando buscar <Trades> container")
            # Try to find Trades element
            for trades_elem in root2.iter():
                tag_clean = trades_elem.tag.split("}")[-1] if "}" in trades_elem.tag else trades_elem.tag
                if tag_clean.lower() == "trades":
                    logger.info(f"IBKR Flex: encontrado container <Trades> con {len(trades_elem)} hijos")
                    for trade_elem in trades_elem:
                        if trade_elem.tag.split("}")[-1].lower() == "trade":
                            row = dict(trade_elem.attrib)
                            row_lc = {str(k).lower(): v for k, v in row.items()}
                            dt_raw = (
                                row_lc.get("datetime")
                                or row_lc.get("tradedate")
                                or row_lc.get("tradedatetime")
                                or row_lc.get("date/time")
                                or row_lc.get("reportdate")
                                or row_lc.get("date")
                            )
                            row["_dt_raw"] = dt_raw
                            row["_lc"] = row_lc
                            trades.append(row)
                            if len(trades) <= 3:
                                logger.info(f"IBKR Trade (via Trades container) #{len(trades)}: symbol={row_lc.get('symbol')}, dt_raw={dt_raw}")

        logger.info(f"IBKR Flex: encontrados {len(trades)} elementos <Trade> en el XML")

        # Filter by date - only skip if we can parse date AND it's before cutoff
        # If date parsing fails, include the trade (safer for backfill)
        out: list[dict[str, Any]] = []
        filtered_out = 0
        parse_failed = 0
        
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
                            filtered_out += 1
                            if filtered_out <= 3:
                                logger.debug(f"IBKR Trade filtrado (fecha {dt_obj.isoformat()} < cutoff): {t.get('_lc', {}).get('symbol', '?')}")
                            continue
                except Exception as e:
                    # If date parsing fails, include the trade (safer for backfill)
                    parse_failed += 1
                    if parse_failed <= 3:
                        logger.warning(f"IBKR Trade: fallo parseando fecha '{dt_raw}': {e}, incluyendo trade de todas formas")
            
            out.append(t)

        logger.info(f"IBKR Flex: {len(out)} trades dentro del rango, {filtered_out} filtrados por fecha, {parse_failed} con parse fallido")
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
            logger.info(f"IBKR Sync: iniciando fetch para últimos {days} días")
            trades = _fetch_ibkr_flex_trades(days=days)
            logger.info(f"IBKR Sync: procesando {len(trades)} trades para upsert en Notion")
            
            processed = 0
            for tr in trades:
                processed += 1
                if processed <= 3:
                    logger.debug(f"IBKR Sync: procesando trade #{processed}: {tr.get('_lc', {}).get('symbol', '?')}")
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
            
            logger.info(f"IBKR Sync: completado - {created} creados, {updated} actualizados")
        except Exception as e:
            logger.error(f"IBKR Sync error: {e}", exc_info=True)
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
    return [sync_investments_to_notion, check_ibkr_connection]


@tool
def check_ibkr_connection() -> dict[str, Any]:
    """Verifica la conexión con IBKR Flex Web Service y muestra la configuración.

    Returns:
        Dict con estado: token configurado, query id, test request result
    """
    from src.core.config import settings

    has_token = bool(settings.ibkr.flex_token and settings.ibkr.flex_token.get_secret_value())
    has_query = bool(settings.ibkr.flex_query_id)

    if not has_token or not has_query:
        missing = []
        if not has_token:
            missing.append("IBKR_FLEX_TOKEN")
        if not has_query:
            missing.append("IBKR_FLEX_QUERY_ID")
        return {
            "connected": False,
            "error": f"Missing .env variables: {', '.join(missing)}",
            "setup_url": "https://www.interactivebrokers.com/en/software/am/am/reports/activityflexquery.htm",
        }

    # Try a minimal Flex SendRequest to validate credentials
    try:
        import httpx
        import xml.etree.ElementTree as ET

        token = settings.ibkr.flex_token.get_secret_value()
        qid = settings.ibkr.flex_query_id

        with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(15.0)) as client:
            r = client.get(
                "https://www.interactivebrokers.com/Universal/servlet/FlexStatementService.SendRequest",
                params={"t": token, "q": qid, "v": "3"},
            )
            r.raise_for_status()
            root = ET.fromstring(r.text)
            ref_code = root.attrib.get("referenceCode") or root.findtext("ReferenceCode")
            if ref_code:
                return {
                    "connected": True,
                    "reference_code": ref_code,
                    "message": "IBKR Flex connection OK — statement can be retrieved",
                }
            error_msg = root.findtext("ErrorMessage") or root.attrib.get("errorMessage", r.text[:200])
            return {"connected": False, "error": f"IBKR Flex error: {error_msg}"}

    except Exception as e:
        return {"connected": False, "error": str(e)}

