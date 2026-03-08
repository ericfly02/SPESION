"""Garmin MCP - Integración con Garmin Connect.

SPESION 3.0 Optimizations:
- Graceful re-login on session expiry (Garmin tokens expire)
- New tool: get_garmin_weekly_summary
- New tool: check_garmin_connection
- Better error messages for MFA / 2FA issues
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Cliente Garmin global (lazy initialization)
_garmin_client = None


def _get_garmin_client(force_relogin: bool = False):
    """Obtiene el cliente de Garmin (lazy init con re-login automático)."""
    global _garmin_client

    if _garmin_client is not None and not force_relogin:
        return _garmin_client

    try:
        from garminconnect import Garmin
        from src.core.config import settings

        if not settings.garmin.email or not settings.garmin.password:
            logger.warning("Garmin credentials not configured (GARMIN_EMAIL / GARMIN_PASSWORD)")
            return None

        _garmin_client = Garmin(
            settings.garmin.email,
            settings.garmin.password.get_secret_value(),
        )
        _garmin_client.login()
        logger.info("Connected to Garmin Connect")
        return _garmin_client

    except ImportError:
        logger.error("garminconnect not installed. Run: pip install garminconnect")
        return None
    except Exception as e:
        msg = str(e).lower()
        if "mfa" in msg or "2fa" in msg or "multi" in msg or "factor" in msg:
            logger.error(
                "Garmin requires MFA. Use garminconnect >= 0.2 and authenticate "
                "interactively once with: python -m garminconnect (follow prompts)."
            )
        elif "invalid" in msg or "credentials" in msg or "login" in msg:
            logger.error(f"Garmin login failed — check GARMIN_EMAIL and GARMIN_PASSWORD: {e}")
        else:
            logger.error(f"Garmin connection error: {e}")
        return None


def _garmin_call(fn, *args, **kwargs):
    """Execute a Garmin API call; retry once with re-login on session errors."""
    global _garmin_client
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if any(k in msg for k in ("expired", "unauthorized", "401", "session")):
            logger.info("Garmin session expired, attempting re-login...")
            _garmin_client = None
            client = _get_garmin_client(force_relogin=True)
            if client:
                return fn(*args, **kwargs)
        raise


def _normalize_date(date_str: str | None) -> str:
    """Normaliza fechas humanas a YYYY-MM-DD.

    Acepta:
    - None -> hoy
    - 'hoy'/'today'
    - 'ayer'/'yesterday'
    - 'mañana'/'tomorrow'
    - formatos parseables (e.g. 2026-01-04, 04/01/2026, 4 Jan 2026)
    """
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")

    raw = str(date_str).strip()
    if not raw:
        return datetime.now().strftime("%Y-%m-%d")

    low = raw.lower()
    if low in {"hoy", "today"}:
        return datetime.now().strftime("%Y-%m-%d")
    if low in {"ayer", "yesterday"}:
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    if low in {"mañana", "manana", "tomorrow"}:
        return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Si ya viene en ISO, devolverlo tal cual
    if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
        # Validación rápida
        try:
            datetime.strptime(raw, "%Y-%m-%d")
            return raw
        except Exception:
            pass

    # Intentar parsear formatos comunes (dd/mm/yyyy, etc.)
    try:
        from dateutil import parser as date_parser

        dt = date_parser.parse(raw, dayfirst=True, fuzzy=True)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Último recurso: hoy
        return datetime.now().strftime("%Y-%m-%d")


@tool
def get_garmin_stats(date: str | None = None) -> dict[str, Any]:
    """Obtiene estadísticas de Garmin para una fecha.
    
    Args:
        date: Fecha en formato YYYY-MM-DD (default: hoy)
        
    Returns:
        Dict con métricas: HRV, sueño, Body Battery, pasos, etc.
    """
    client = _get_garmin_client()
    if client is None:
        return {"error": "Garmin no disponible"}
    
    try:
        target_date = _normalize_date(date)
        
        # Obtener múltiples métricas
        stats = {}
        
        # Stats generales del día
        try:
            user_stats = client.get_stats(target_date)
            stats["steps"] = user_stats.get("totalSteps", 0)
            stats["calories"] = user_stats.get("totalKilocalories", 0)
            stats["active_minutes"] = user_stats.get("moderateIntensityMinutes", 0)
            stats["distance_km"] = round(user_stats.get("totalDistanceMeters", 0) / 1000, 2)
        except Exception as e:
            logger.warning(f"Error obteniendo stats: {e}")
        
        # HRV
        try:
            hrv_data = client.get_hrv_data(target_date)
            if hrv_data and "hrvSummary" in hrv_data:
                stats["hrv"] = hrv_data["hrvSummary"].get("lastNightAvg", 0)
                stats["hrv_status"] = hrv_data["hrvSummary"].get("status", "unknown")
        except Exception as e:
            logger.warning(f"Error obteniendo HRV: {e}")
        
        # Sueño
        try:
            sleep_data = client.get_sleep_data(target_date)
            if sleep_data:
                stats["sleep_hours"] = round(
                    sleep_data.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0) / 3600, 1
                )
                stats["sleep_score"] = sleep_data.get("dailySleepDTO", {}).get(
                    "sleepScores", {}
                ).get("overall", {}).get("value", 0)
        except Exception as e:
            logger.warning(f"Error obteniendo sueño: {e}")
        
        # Body Battery
        try:
            bb_data = client.get_body_battery(target_date)
            if bb_data:
                # Obtener el último valor del día
                charged = bb_data[-1].get("charged", 0) if bb_data else 0
                drained = bb_data[-1].get("drained", 0) if bb_data else 0
                stats["body_battery"] = max(0, min(100, charged - drained))
        except Exception as e:
            logger.warning(f"Error obteniendo Body Battery: {e}")
        
        # Resting Heart Rate
        try:
            hr_data = client.get_rhr_day(target_date)
            if hr_data:
                stats["resting_hr"] = hr_data.get("restingHeartRate", 0)
        except Exception as e:
            logger.warning(f"Error obteniendo RHR: {e}")
        
        stats["date"] = target_date
        return stats
        
    except Exception as e:
        logger.error(f"Error obteniendo stats de Garmin: {e}")
        return {"error": str(e)}


@tool
def get_garmin_activities(
    days: int = 7,
    activity_type: str | None = None,
) -> list[dict[str, Any]]:
    """Obtiene actividades recientes de Garmin.
    
    Args:
        days: Número de días hacia atrás
        activity_type: Filtrar por tipo ('running', 'cycling', etc.)
        
    Returns:
        Lista de actividades
    """
    client = _get_garmin_client()
    if client is None:
        return [{"error": "Garmin no disponible"}]
    
    try:
        limit = max(1, days * 3)  # Asegurar límite positivo
        activities = client.get_activities(0, limit)
        
        results = []
        cutoff = datetime.now() - timedelta(days=days)
        
        for act in activities:
            act_date = datetime.fromisoformat(
                act.get("startTimeLocal", "").replace("Z", "+00:00")
            )
            
            if act_date.replace(tzinfo=None) < cutoff:
                continue
            
            if activity_type and activity_type.lower() not in act.get(
                "activityType", {}
            ).get("typeKey", "").lower():
                continue
            
            results.append({
                "name": act.get("activityName", ""),
                "type": act.get("activityType", {}).get("typeKey", ""),
                "date": act.get("startTimeLocal", ""),
                "duration_min": round(act.get("duration", 0) / 60, 1),
                "distance_km": round(act.get("distance", 0) / 1000, 2),
                "calories": act.get("calories", 0),
                "avg_hr": act.get("averageHR", 0),
                "max_hr": act.get("maxHR", 0),
                "avg_pace": _format_pace(act.get("averageSpeed", 0)),
            })
        
        return results[:10]  # Limitar a 10
        
    except Exception as e:
        logger.error(f"Error obteniendo actividades: {e}")
        return [{"error": str(e)}]


@tool  
def get_training_status() -> dict[str, Any]:
    """Obtiene el estado de entrenamiento actual.
    
    Returns:
        Dict con training load, training status, VO2max, etc.
    """
    client = _get_garmin_client()
    if client is None:
        return {"error": "Garmin no disponible"}
    
    try:
        # Obtener métricas de entrenamiento
        today = datetime.now().strftime("%Y-%m-%d")
        
        result = {
            "date": today,
        }
        
        # Training Status
        try:
            training = client.get_training_status(today)
            if training:
                result["training_load"] = training.get("trainingLoadBalance", 0)
                result["training_status"] = training.get("trainingStatus", "unknown")
                result["vo2max"] = training.get("vo2MaxPreciseValue", 0)
        except Exception:
            pass
        
        # Weekly training load
        try:
            weekly = client.get_weekly_stress(today)
            if weekly:
                result["weekly_stress"] = weekly
        except Exception:
            pass
        
        return result
        
    except Exception as e:
        logger.error(f"Error obteniendo training status: {e}")
        return {"error": str(e)}


def _format_pace(speed_mps: float) -> str:
    """Convierte velocidad m/s a pace min/km."""
    if speed_mps <= 0:
        return "N/A"
    pace_sec_per_km = 1000 / speed_mps
    minutes = int(pace_sec_per_km // 60)
    seconds = int(pace_sec_per_km % 60)
    return f"{minutes}:{seconds:02d}/km"


def _get_mock_garmin_stats() -> dict[str, Any]:
    """Datos mock para testing sin Garmin real."""
    return {
        "steps": 8500,
        "calories": 2100,
        "hrv": 58,
        "sleep_hours": 7.2,
        "sleep_score": 78,
        "body_battery": 72,
        "resting_hr": 52,
        "active_minutes": 45,
        "distance_km": 6.3,
        "_note": "Datos de ejemplo (Garmin no conectado)",
    }


def create_garmin_tools() -> list:
    """Crea las herramientas de Garmin (SPESION 3.0).

    Returns:
        Lista de herramientas
    """
    return [
        get_garmin_stats,
        get_garmin_activities,
        get_training_status,
        get_garmin_weekly_summary,
        check_garmin_connection,
    ]


@tool
def get_garmin_weekly_summary() -> dict[str, Any]:
    """Obtiene un resumen semanal de actividad y salud de Garmin.

    Returns:
        Dict con métricas agregadas de la semana: pasos, sueño, HRV, actividades, carga
    """
    client = _get_garmin_client()
    if client is None:
        return {"error": "Garmin no disponible"}

    today = datetime.now()
    summary: dict[str, Any] = {
        "week_start": (today - timedelta(days=7)).strftime("%Y-%m-%d"),
        "week_end": today.strftime("%Y-%m-%d"),
        "days": [],
        "totals": {},
    }

    total_steps = 0
    total_sleep = 0.0
    total_calories = 0
    hrv_values = []
    days_collected = 0

    for offset in range(7, 0, -1):
        date_str = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        day_data: dict[str, Any] = {"date": date_str}

        try:
            stats = _garmin_call(client.get_stats, date_str)
            if stats:
                day_data["steps"] = stats.get("totalSteps", 0)
                day_data["calories"] = stats.get("totalKilocalories", 0)
                total_steps += day_data["steps"]
                total_calories += day_data["calories"]
        except Exception:
            pass

        try:
            sleep = _garmin_call(client.get_sleep_data, date_str)
            if sleep:
                hours = sleep.get("dailySleepDTO", {}).get("sleepTimeSeconds", 0) / 3600
                day_data["sleep_hours"] = round(hours, 1)
                total_sleep += hours
        except Exception:
            pass

        try:
            hrv = _garmin_call(client.get_hrv_data, date_str)
            if hrv and "hrvSummary" in hrv:
                val = hrv["hrvSummary"].get("lastNightAvg", 0)
                if val:
                    day_data["hrv"] = val
                    hrv_values.append(val)
        except Exception:
            pass

        summary["days"].append(day_data)
        days_collected += 1

    summary["totals"] = {
        "total_steps": total_steps,
        "avg_daily_steps": round(total_steps / max(1, days_collected)),
        "total_sleep_hours": round(total_sleep, 1),
        "avg_sleep_hours": round(total_sleep / max(1, days_collected), 1),
        "avg_hrv": round(sum(hrv_values) / len(hrv_values), 1) if hrv_values else None,
        "total_calories": total_calories,
    }
    return summary


@tool
def check_garmin_connection() -> dict[str, Any]:
    """Verifica la conectividad con Garmin Connect.

    Returns:
        Dict con estado de la conexión y datos básicos del perfil
    """
    client = _get_garmin_client()
    if client is None:
        return {
            "connected": False,
            "error": "Cannot connect to Garmin. Check GARMIN_EMAIL and GARMIN_PASSWORD in .env",
        }

    try:
        profile = _garmin_call(client.get_user_profile)
        return {
            "connected": True,
            "display_name": profile.get("displayName", ""),
            "full_name": profile.get("fullName", ""),
            "user_id": profile.get("userId", ""),
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}
