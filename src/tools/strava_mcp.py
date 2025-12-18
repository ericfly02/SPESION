"""Strava MCP - Integración con Strava API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# Token de acceso global (lazy initialization)
_strava_access_token: str | None = None
_token_expires_at: datetime | None = None


def _get_strava_token() -> str | None:
    """Obtiene un token de acceso válido de Strava."""
    global _strava_access_token, _token_expires_at
    
    # Verificar si el token actual es válido
    if _strava_access_token and _token_expires_at:
        if datetime.now() < _token_expires_at - timedelta(minutes=5):
            return _strava_access_token
    
    # Renovar token
    try:
        import httpx
        from src.core.config import settings
        
        if not settings.strava.client_id or not settings.strava.refresh_token:
            logger.warning("Credenciales de Strava no configuradas")
            return None
        
        response = httpx.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": settings.strava.client_id,
                "client_secret": settings.strava.client_secret.get_secret_value(),
                "refresh_token": settings.strava.refresh_token.get_secret_value(),
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        data = response.json()
        
        _strava_access_token = data["access_token"]
        _token_expires_at = datetime.fromtimestamp(data["expires_at"])
        
        logger.info("Token de Strava renovado")
        return _strava_access_token
        
    except Exception as e:
        logger.error(f"Error renovando token de Strava: {e}")
        return None


def _strava_request(endpoint: str, params: dict | None = None) -> dict | list | None:
    """Realiza una petición a la API de Strava."""
    token = _get_strava_token()
    if not token:
        return None
    
    try:
        import httpx
        
        response = httpx.get(
            f"https://www.strava.com/api/v3{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"Error en petición Strava: {e}")
        return None


@tool
def get_strava_activities(
    days: int = 7,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    """Obtiene actividades recientes de Strava.
    
    Args:
        days: Número de días hacia atrás
        per_page: Número de actividades a obtener
        
    Returns:
        Lista de actividades con detalles
    """
    after = int((datetime.now() - timedelta(days=days)).timestamp())
    
    data = _strava_request(
        "/athlete/activities",
        params={"after": after, "per_page": per_page},
    )
    
    if data is None:
        return [{"error": "Strava no disponible", "mock_data": _get_mock_activities()}]
    
    results = []
    for act in data:
        results.append({
            "name": act.get("name", ""),
            "type": act.get("type", ""),
            "date": act.get("start_date_local", ""),
            "distance_km": round(act.get("distance", 0) / 1000, 2),
            "duration_min": round(act.get("moving_time", 0) / 60, 1),
            "elevation_m": act.get("total_elevation_gain", 0),
            "avg_speed_kmh": round(act.get("average_speed", 0) * 3.6, 1),
            "avg_hr": act.get("average_heartrate", 0),
            "max_hr": act.get("max_heartrate", 0),
            "suffer_score": act.get("suffer_score", 0),
            "kudos": act.get("kudos_count", 0),
            "id": act.get("id"),
        })
    
    return results


@tool
def get_strava_stats() -> dict[str, Any]:
    """Obtiene estadísticas generales del atleta.
    
    Returns:
        Dict con totales de running, cycling, etc.
    """
    # Primero obtener el ID del atleta
    athlete = _strava_request("/athlete")
    if athlete is None:
        return {"error": "Strava no disponible"}
    
    athlete_id = athlete.get("id")
    if not athlete_id:
        return {"error": "No se pudo obtener ID de atleta"}
    
    stats = _strava_request(f"/athletes/{athlete_id}/stats")
    if stats is None:
        return {"error": "No se pudieron obtener estadísticas"}
    
    # Formatear resultados
    return {
        "running": {
            "ytd_runs": stats.get("ytd_run_totals", {}).get("count", 0),
            "ytd_distance_km": round(
                stats.get("ytd_run_totals", {}).get("distance", 0) / 1000, 1
            ),
            "ytd_time_hours": round(
                stats.get("ytd_run_totals", {}).get("moving_time", 0) / 3600, 1
            ),
            "all_time_runs": stats.get("all_run_totals", {}).get("count", 0),
            "all_time_km": round(
                stats.get("all_run_totals", {}).get("distance", 0) / 1000, 1
            ),
        },
        "cycling": {
            "ytd_rides": stats.get("ytd_ride_totals", {}).get("count", 0),
            "ytd_distance_km": round(
                stats.get("ytd_ride_totals", {}).get("distance", 0) / 1000, 1
            ),
        },
        "recent_run_totals": {
            "count": stats.get("recent_run_totals", {}).get("count", 0),
            "distance_km": round(
                stats.get("recent_run_totals", {}).get("distance", 0) / 1000, 1
            ),
        },
    }


@tool
def get_activity_details(activity_id: int) -> dict[str, Any]:
    """Obtiene detalles completos de una actividad.
    
    Args:
        activity_id: ID de la actividad en Strava
        
    Returns:
        Dict con detalles completos
    """
    data = _strava_request(f"/activities/{activity_id}")
    if data is None:
        return {"error": "Actividad no encontrada"}
    
    return {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "type": data.get("type", ""),
        "date": data.get("start_date_local", ""),
        "distance_km": round(data.get("distance", 0) / 1000, 2),
        "duration_min": round(data.get("moving_time", 0) / 60, 1),
        "elapsed_min": round(data.get("elapsed_time", 0) / 60, 1),
        "elevation_m": data.get("total_elevation_gain", 0),
        "avg_speed_kmh": round(data.get("average_speed", 0) * 3.6, 1),
        "max_speed_kmh": round(data.get("max_speed", 0) * 3.6, 1),
        "avg_hr": data.get("average_heartrate", 0),
        "max_hr": data.get("max_heartrate", 0),
        "calories": data.get("calories", 0),
        "suffer_score": data.get("suffer_score", 0),
        "average_cadence": data.get("average_cadence", 0),
        "splits_km": [
            {
                "km": i + 1,
                "pace": _format_pace_from_speed(s.get("average_speed", 0)),
                "elevation": s.get("elevation_difference", 0),
            }
            for i, s in enumerate(data.get("splits_metric", []))
        ],
    }


def _format_pace_from_speed(speed_mps: float) -> str:
    """Convierte velocidad m/s a pace min/km."""
    if speed_mps <= 0:
        return "N/A"
    pace_sec = 1000 / speed_mps
    minutes = int(pace_sec // 60)
    seconds = int(pace_sec % 60)
    return f"{minutes}:{seconds:02d}"


def _get_mock_activities() -> list[dict[str, Any]]:
    """Datos mock para testing."""
    return [
        {
            "name": "Morning Run",
            "type": "Run",
            "date": datetime.now().isoformat(),
            "distance_km": 8.5,
            "duration_min": 42,
            "avg_hr": 152,
            "_note": "Datos de ejemplo",
        }
    ]


def create_strava_tools() -> list:
    """Crea las herramientas de Strava.
    
    Returns:
        Lista de herramientas
    """
    return [
        get_strava_activities,
        get_strava_stats,
        get_activity_details,
    ]

