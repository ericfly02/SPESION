"""Finance Tool - Herramientas financieras con Yahoo Finance."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def get_stock_price(ticker: str) -> dict[str, Any]:
    """Obtiene el precio actual de una acción.
    
    Args:
        ticker: Símbolo del ticker (e.g., 'AAPL', 'NVDA', 'VWCE.DE')
        
    Returns:
        Dict con precio, cambio diario y otros datos
    """
    try:
        import yfinance as yf
        
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            "ticker": ticker,
            "name": info.get("shortName", ticker),
            "price": info.get("currentPrice") or info.get("regularMarketPrice", 0),
            "currency": info.get("currency", "USD"),
            "change_pct": round(
                info.get("regularMarketChangePercent", 0), 2
            ),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
            "52w_high": info.get("fiftyTwoWeekHigh", 0),
            "52w_low": info.get("fiftyTwoWeekLow", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
        }
        
    except ImportError:
        logger.error("yfinance no instalado")
        return {"error": "yfinance no instalado"}
    except Exception as e:
        logger.error(f"Error obteniendo precio de {ticker}: {e}")
        return {"error": str(e), "ticker": ticker}


@tool
def get_crypto_price(symbol: str) -> dict[str, Any]:
    """Obtiene el precio actual de una criptomoneda.
    
    Args:
        symbol: Símbolo de la crypto (e.g., 'BTC', 'ETH')
        
    Returns:
        Dict con precio y datos
    """
    try:
        import yfinance as yf
        
        # Yahoo Finance usa formato SYMBOL-USD
        ticker = f"{symbol.upper()}-USD"
        crypto = yf.Ticker(ticker)
        info = crypto.info
        
        return {
            "symbol": symbol.upper(),
            "price_usd": info.get("regularMarketPrice", 0),
            "change_24h_pct": round(
                info.get("regularMarketChangePercent", 0), 2
            ),
            "market_cap": info.get("marketCap", 0),
            "volume_24h": info.get("volume24Hr", 0),
            "day_high": info.get("dayHigh", 0),
            "day_low": info.get("dayLow", 0),
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo precio de {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}


@tool
def get_portfolio_summary(
    holdings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calcula el resumen de un portfolio.
    
    Args:
        holdings: Lista de posiciones con formato:
            [{"ticker": "AAPL", "shares": 10, "avg_cost": 150}, ...]
            
    Returns:
        Dict con valor total, P&L, y desglose por posición
    """
    try:
        import yfinance as yf
        
        total_value = 0
        total_cost = 0
        positions = []
        
        for holding in holdings:
            ticker = holding.get("ticker", "")
            shares = holding.get("shares", 0)
            avg_cost = holding.get("avg_cost", 0)
            
            if not ticker or shares <= 0:
                continue
            
            # Obtener precio actual
            stock = yf.Ticker(ticker)
            current_price = stock.info.get("regularMarketPrice", 0)
            
            position_value = current_price * shares
            position_cost = avg_cost * shares
            pnl = position_value - position_cost
            pnl_pct = (pnl / position_cost * 100) if position_cost > 0 else 0
            
            positions.append({
                "ticker": ticker,
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "value": round(position_value, 2),
                "pnl": round(pnl, 2),
                "pnl_pct": round(pnl_pct, 2),
            })
            
            total_value += position_value
            total_cost += position_cost
        
        total_pnl = total_value - total_cost
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        
        return {
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "positions": positions,
        }
        
    except Exception as e:
        logger.error(f"Error calculando portfolio: {e}")
        return {"error": str(e)}


@tool
def analyze_allocation(
    portfolio_value: float,
    core_value: float,
    thematic_value: float,
    crypto_value: float,
) -> dict[str, Any]:
    """Analiza la asignación actual vs targets.
    
    Targets del usuario:
    - Core: 50%
    - Temático: 35%
    - Crypto: 15%
    
    Args:
        portfolio_value: Valor total del portfolio
        core_value: Valor en posiciones Core (ETFs globales)
        thematic_value: Valor en posiciones Temáticas
        crypto_value: Valor en crypto
        
    Returns:
        Dict con análisis de asignación y sugerencias
    """
    if portfolio_value <= 0:
        return {"error": "Valor del portfolio inválido"}
    
    # Targets
    targets = {
        "core": 0.50,
        "thematic": 0.35,
        "crypto": 0.15,
    }
    
    # Calcular asignación actual
    current = {
        "core": core_value / portfolio_value,
        "thematic": thematic_value / portfolio_value,
        "crypto": crypto_value / portfolio_value,
    }
    
    # Calcular desviaciones
    deviations = {}
    suggestions = []
    
    for category, target in targets.items():
        curr = current[category]
        dev = curr - target
        deviations[category] = {
            "current_pct": round(curr * 100, 1),
            "target_pct": round(target * 100, 1),
            "deviation_pct": round(dev * 100, 1),
            "status": "OK" if abs(dev) < 0.05 else ("OVER" if dev > 0 else "UNDER"),
        }
        
        if abs(dev) >= 0.05:
            action = "Reducir" if dev > 0 else "Aumentar"
            amount = abs(dev) * portfolio_value
            suggestions.append(
                f"{action} {category} en ~€{amount:.0f} ({abs(dev)*100:.1f}%)"
            )
    
    needs_rebalance = any(
        abs(current[cat] - targets[cat]) >= 0.05 
        for cat in targets
    )
    
    return {
        "portfolio_value": round(portfolio_value, 2),
        "allocation": deviations,
        "needs_rebalance": needs_rebalance,
        "suggestions": suggestions,
    }


@tool
def calculate_dca(
    monthly_amount: float,
    current_allocation: dict[str, float],
) -> dict[str, float]:
    """Calcula cómo distribuir la aportación mensual DCA.
    
    Prioriza categorías infraponderadas para mantener balance.
    
    Args:
        monthly_amount: Cantidad a invertir este mes (€)
        current_allocation: Dict con asignación actual
            {"core": 0.52, "thematic": 0.33, "crypto": 0.15}
            
    Returns:
        Dict con cantidad sugerida por categoría
    """
    targets = {
        "core": 0.50,
        "thematic": 0.35,
        "crypto": 0.15,
    }
    
    # Calcular qué categorías están infraponderadas
    underweight = {}
    for cat, target in targets.items():
        current = current_allocation.get(cat, target)
        gap = target - current
        if gap > 0:
            underweight[cat] = gap
    
    # Si no hay infraponderación, distribuir según targets
    if not underweight:
        return {
            cat: round(monthly_amount * target, 2)
            for cat, target in targets.items()
        }
    
    # Distribuir proporcionalmente a la infraponderación
    total_gap = sum(underweight.values())
    distribution = {}
    
    for cat, gap in underweight.items():
        distribution[cat] = round(monthly_amount * (gap / total_gap), 2)
    
    # Las categorías no infraponderadas no reciben nada
    for cat in targets:
        if cat not in distribution:
            distribution[cat] = 0
    
    return distribution


def create_finance_tools() -> list:
    """Crea las herramientas financieras.
    
    Returns:
        Lista de herramientas
    """
    return [
        get_stock_price,
        get_crypto_price,
        get_portfolio_summary,
        analyze_allocation,
        calculate_dca,
    ]

