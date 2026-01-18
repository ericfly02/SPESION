"""Smart Wake Up Feature.

Calcula la hora óptima para despertar basándose en:
1. Preferencias del usuario (ventana de despertar)
2. Datos de sueño de Garmin (fase de sueño)
3. Eventos del calendario (para no despertar tarde)

Luego envía la hora calculada a un Webhook de Make.com para que el iPhone la recoja.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, time
from typing import Optional, Tuple
import requests

from src.core.config import settings
from src.tools.garmin_mcp import get_garmin_stats
from src.tools.calendar_mcp import get_calendar_events

logger = logging.getLogger(__name__)

# Archivo simple para persistencia de configuración manual
PREFS_FILE = "./data/smart_wake_prefs.json"

def _load_prefs() -> dict:
    import json
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_prefs(prefs: dict) -> None:
    import json
    os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
    with open(PREFS_FILE, "w") as f:
        json.dump(prefs, f)

from langchain_core.tools import tool

@tool
def set_manual_wake_window(start: str, end: str) -> str:
    """Configura la ventana de despertar manualmente.
    
    Args:
        start: Hora inicio (HH:MM)
        end: Hora fin (HH:MM)
    """
    try:
        # Validar formato
        datetime.strptime(start, "%H:%M")
        datetime.strptime(end, "%H:%M")
        
        prefs = _load_prefs()
        prefs["manual_window"] = {
            "start": start,
            "end": end,
            "date": datetime.now().strftime("%Y-%m-%d") # Válido solo para el próximo despertar
        }
        _save_prefs(prefs)
        return f"Ventana de despertar configurada: {start} - {end}"
    except ValueError:
        return "Error: Formato de hora inválido. Usa HH:MM (ej: 08:30)"

def _get_active_window() -> Tuple[str, str]:
    """Obtiene la ventana activa (manual o default)."""
    prefs = _load_prefs()
    manual = prefs.get("manual_window")
    
    # Chequear si hay override manual válido para "mañana" 
    # (o hoy si es madrugada)
    if manual:
        # Aquí simplificamos: si se configuró en las últimas 24h, lo usamos
        last_set = manual.get("date")
        if last_set:
            last_date = datetime.strptime(last_set, "%Y-%m-%d")
            if (datetime.now() - last_date).days < 1:
                return manual["start"], manual["end"]
    
    # Default 8:30 - 8:50
    return "08:30", "08:50"

def check_calendar_constraints(target_date: str) -> Optional[str]:
    """Verifica si hay reuniones temprano que fuercen despertar antes.
    
    Returns:
        Hora límite (HH:MM) o None
    """
    try:
        events = get_calendar_events.invoke({"days": 1})
        if not isinstance(events, list):
            return None
            
        # Buscar primer evento del día target
        first_event = None
        for evt in events:
            # Parsear start time
            # El tool devuelve strings formateados, necesitamos raw data idealmente
            # Pero el tool `get_calendar_events` devuelve lista de dicts con 'start'
            if "start" in evt and target_date in evt["start"]:
                # Asumimos formato ISO o similar que devuelve el tool
                # Simplificación: si hay evento antes de las 9, sugerir 1h antes
                pass 
                
        # TODO: Refinar lógica con output real del calendar tool
        return None
    except Exception as e:
        logger.error(f"Error checking calendar: {e}")
        return None

def _get_sleep_phase(stats: dict) -> str:
    """Intenta determinar la fase de sueño actual/última."""
    # Nota: La API pública de Garmin Connect no siempre da fases en tiempo real.
    # Usamos heurísticas con lo que haya.
    # Si hay 'sleepLevels', miramos el último bloque.
    try:
        if "sleepLevels" in stats:
            last_level = stats["sleepLevels"][-1] if stats["sleepLevels"] else {}
            return last_level.get("activityLevel", "unknown")  # light, deep, rem, awake
    except Exception:
        pass
    
    return "unknown"

async def calculate_wake_decision_now(assistant: Any) -> Tuple[str, str]:
    """Decisión en tiempo real usando el Asistente (Coach/Brain).
    
    1. Obtiene métricas de Garmin (Stats de hoy/ayer).
    2. Pide al LLM que decida: "Despertar AHORA o ESPERAR".
    """
    start_str, end_str = _get_active_window()
    
    try:
        # Contexto: Hora actual
        now_str = datetime.now().strftime("%H:%M")
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Obtener Stats (Body Battery, Sleep Score, HRV)
        # Nota: Garmin Sync puede tener delay. Si 'hoy' está vacío, mirar 'ayer' para tendencias
        # pero para fase de sueño necesitamos 'hoy'.
        stats = get_garmin_stats.invoke({"date": today})
        
        # Prompt para el LLM
        prompt = f"""
        CONTEXTO:
        - Hora Actual: {now_str}
        - Ventana Deseada: {start_str} - {end_str}
        - Datos de Sueño (Garmin): {stats}
        
        OBJETIVO:
        Decidir si despertar al usuario AHORA MISMO ({start_str}) o dejarle dormir hasta el final de la ventana ({end_str}).
        
        REGLAS:
        1. Si está en sueño ligero/despierto (según Sleep Levels/HR) -> Despertar YA.
        2. Si está en sueño profundo -> Esperar.
        3. Si tuvo muy mal sueño (Score < 50) y hay margen -> Dejar dormir al máximo.
        4. Si Body Battery ya está alto (>80) -> Despertar YA.
        
        RESPONDE SOLO EN FORMATO JSON:
        {{
            "wake_time": "{start_str}" o "{end_str}",
            "reason": "Breve explicación de por qué (ej: Sueño ligero detectado, Body Battery baja...)"
        }}
        """
        
        # Usamos el assistant "default" (Supervisor) o uno más rápido?
        # Usaremos el chat general, el supervisor ruteará o responderá directo.
        # Mejor: forzar respuesta corta simulando ser 'System'.
        
        # Como assistant.achat espera user_id, lo pasamos.
        response_text = await assistant.achat(
            message=prompt,
            user_id="SYSTEM_SMART_WAKE",
            telegram_chat_id=0, # Dummy
        )
        
        # Intentar parsear JSON
        import json
        import re
        
        # Buscar JSON en la respuesta
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                return data.get("wake_time", start_str), data.get("reason", "Decisión IA")
            except:
                pass
                
        # Fallback si el LLM no da JSON limpio
        logger.warning(f"LLM no devolvió JSON limpio: {response_text}")
        return start_str, "Fallback (LLM error de formato)"

    except Exception as e:
        logger.error(f"Error in smart wake decision: {e}")

    # Fallback seguro: Inicio de ventana
    return start_str, "Fallback por defecto (Error Técnico)"

async def push_wake_time_to_make(assistant: Any) -> str:
    """Ejecuta la decisión y envía a Make."""
    wake_time, reason = await calculate_wake_decision_now(assistant)
    
    logger.info(f"Smart Wake Decisión (AI): {wake_time} ({reason})")
    
    webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    if not webhook_url:
        return "⚠️ Webhook no configurado"
        
    try:
        response = requests.post(
            webhook_url,
            json={
                "wake_time": wake_time,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            },
            timeout=10
        )
        response.raise_for_status()
        return f"Enviado a Make: {wake_time} ({reason})"
    except Exception as e:
        logger.error(f"Error enviando a Make: {e}")
        return f"Error enviando a Make: {e}"
