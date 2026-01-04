"""Finance Tools - Herramientas para procesamiento de datos financieros."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def process_portfolio_csv(file_path: str) -> str:
    """Procesa un archivo CSV con datos de portfolio (e.g. IBKR) y devuelve los datos para importación.
    
    El CSV debe tener encabezados como: Symbol/Ticker, Quantity, Price, Value/Amount, Type, Category.
    Si no tiene formato estándar, intentará inferirlo.
    
    Args:
        file_path: Ruta al archivo CSV.
        
    Returns:
        Resumen de los datos encontrados y listos para importar.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: El archivo {file_path} no existe."
            
        holdings = []
        
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            
            # Normalizar headers (lowercase)
            headers_map = {h.lower(): h for h in headers}
            
            for row in reader:
                # Intentar mapear columnas comunes
                ticker = row.get(headers_map.get("symbol")) or row.get(headers_map.get("ticker"))
                qty = row.get(headers_map.get("quantity")) or row.get(headers_map.get("shares"))
                price = row.get(headers_map.get("price")) or row.get(headers_map.get("close price"))
                value = row.get(headers_map.get("value")) or row.get(headers_map.get("amount")) or row.get(headers_map.get("market value"))
                asset_type = row.get(headers_map.get("type")) or "Stock"
                
                if ticker and qty:
                    try:
                        # Limpiar datos numéricos (quitar 'EUR', '$', ',')
                        def clean_num(n):
                            if not n: return 0.0
                            return float(str(n).replace("EUR", "").replace("$", "").replace(",", "").strip())
                            
                        qty_val = clean_num(qty)
                        price_val = clean_num(price)
                        value_val = clean_num(value)
                        
                        # Si falta value, calcular
                        if value_val == 0 and qty_val and price_val:
                            value_val = qty_val * price_val
                            
                        holdings.append({
                            "ticker": ticker,
                            "quantity": qty_val,
                            "current_price": price_val,
                            "amount": value_val,
                            "type": asset_type
                        })
                    except ValueError:
                        continue
                        
        if not holdings:
            return "No se pudieron extraer holdings válidos. Asegúrate que el CSV tenga columnas Symbol, Quantity y Value."
            
        # Formato resumen para el LLM
        summary = f"Encontrados {len(holdings)} activos:\n"
        for h in holdings[:10]:
            summary += f"- {h['ticker']}: {h['quantity']} @ {h['current_price']} (Total: {h['amount']:.2f})\n"
            
        if len(holdings) > 10:
            summary += f"... y {len(holdings)-10} más."
            
        summary += "\n\nPara importarlos, usa la herramienta `add_portfolio_holding` para cada uno."
        
        return summary
        
    except Exception as e:
        logger.error(f"Error procesando CSV: {e}")
        return f"Error procesando CSV: {e}"

def create_finance_tools() -> list:
    return [process_portfolio_csv]

