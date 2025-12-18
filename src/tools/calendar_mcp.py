"""Google Calendar MCP - Integración con Google Calendar API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _get_calendar_service():
    """Obtiene el servicio de Google Calendar."""
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        import pickle
        from pathlib import Path
        
        from src.core.config import settings
        
        if not settings.google.credentials_path:
            logger.warning("Credenciales de Google no configuradas")
            return None
        
        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        creds = None
        token_path = Path("./data/google_token.pickle")
        
        # Cargar token existente
        if token_path.exists():
            with open(token_path, "rb") as token:
                creds = pickle.load(token)
        
        # Renovar si expiró
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        # Si no hay credenciales válidas, necesitamos autenticar
        if not creds or not creds.valid:
            if not settings.google.credentials_path.exists():
                logger.error("Archivo de credenciales de Google no encontrado")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(settings.google.credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
            
            # Guardar token
            token_path.parent.mkdir(parents=True, exist_ok=True)
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
        
        return build("calendar", "v3", credentials=creds)
        
    except ImportError:
        logger.error(
            "google-api-python-client no instalado. "
            "pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
        )
        return None
    except Exception as e:
        logger.error(f"Error conectando a Google Calendar: {e}")
        return None


@tool
def get_calendar_events(
    days: int = 7,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Obtiene eventos del calendario.
    
    Args:
        days: Número de días hacia adelante
        max_results: Número máximo de eventos
        
    Returns:
        Lista de eventos
    """
    service = _get_calendar_service()
    if service is None:
        return [{"error": "Google Calendar no disponible", "mock_data": _get_mock_events()}]
    
    try:
        from src.core.config import settings
        
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days)).isoformat() + "Z"
        
        events_result = service.events().list(
            calendarId=settings.google.calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = []
        for event in events_result.get("items", []):
            start = event.get("start", {})
            end = event.get("end", {})
            
            events.append({
                "id": event.get("id"),
                "title": event.get("summary", "Sin título"),
                "description": event.get("description", "")[:200],
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "location": event.get("location", ""),
                "attendees": [
                    a.get("email") for a in event.get("attendees", [])
                ][:5],
                "meeting_link": event.get("hangoutLink", ""),
                "status": event.get("status", ""),
            })
        
        return events
        
    except Exception as e:
        logger.error(f"Error obteniendo eventos: {e}")
        return [{"error": str(e)}]


@tool
def get_today_agenda() -> dict[str, Any]:
    """Obtiene la agenda de hoy.
    
    Returns:
        Dict con eventos de hoy y resumen
    """
    service = _get_calendar_service()
    if service is None:
        return {"error": "Google Calendar no disponible"}
    
    try:
        from src.core.config import settings
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        
        events_result = service.events().list(
            calendarId=settings.google.calendar_id,
            timeMin=today.isoformat() + "Z",
            timeMax=tomorrow.isoformat() + "Z",
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = []
        total_meeting_hours = 0
        
        for event in events_result.get("items", []):
            start = event.get("start", {})
            end = event.get("end", {})
            
            start_time = start.get("dateTime")
            end_time = end.get("dateTime")
            
            if start_time and end_time:
                start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                duration = (end_dt - start_dt).total_seconds() / 3600
                total_meeting_hours += duration
            else:
                duration = 0
            
            events.append({
                "title": event.get("summary", "Sin título"),
                "start": start_time or start.get("date"),
                "end": end_time or end.get("date"),
                "duration_hours": round(duration, 1),
                "has_video_call": bool(event.get("hangoutLink")),
            })
        
        # Calcular tiempo libre
        work_hours = 8
        free_hours = max(0, work_hours - total_meeting_hours)
        
        return {
            "date": today.strftime("%Y-%m-%d"),
            "events": events,
            "total_events": len(events),
            "meeting_hours": round(total_meeting_hours, 1),
            "free_hours": round(free_hours, 1),
            "is_heavy_day": total_meeting_hours > 5,
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo agenda: {e}")
        return {"error": str(e)}


@tool
def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
) -> dict[str, Any]:
    """Crea un evento en el calendario.
    
    Args:
        title: Título del evento
        start_time: Hora de inicio (ISO format)
        end_time: Hora de fin (ISO format)
        description: Descripción opcional
        location: Ubicación opcional
        attendees: Lista de emails de asistentes
        
    Returns:
        Dict con el evento creado
    """
    service = _get_calendar_service()
    if service is None:
        return {"error": "Google Calendar no disponible"}
    
    try:
        from src.core.config import settings
        
        event = {
            "summary": title,
            "start": {"dateTime": start_time, "timeZone": "Europe/Madrid"},
            "end": {"dateTime": end_time, "timeZone": "Europe/Madrid"},
        }
        
        if description:
            event["description"] = description
        
        if location:
            event["location"] = location
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        created = service.events().insert(
            calendarId=settings.google.calendar_id,
            body=event,
        ).execute()
        
        return {
            "id": created.get("id"),
            "title": title,
            "start": start_time,
            "end": end_time,
            "url": created.get("htmlLink"),
            "created": True,
        }
        
    except Exception as e:
        logger.error(f"Error creando evento: {e}")
        return {"error": str(e)}


@tool
def find_free_slots(
    duration_minutes: int = 60,
    days_ahead: int = 7,
    work_start: int = 9,
    work_end: int = 18,
) -> list[dict[str, str]]:
    """Encuentra slots libres en el calendario.
    
    Args:
        duration_minutes: Duración mínima del slot
        days_ahead: Días hacia adelante a buscar
        work_start: Hora de inicio de jornada
        work_end: Hora de fin de jornada
        
    Returns:
        Lista de slots libres
    """
    service = _get_calendar_service()
    if service is None:
        return [{"error": "Google Calendar no disponible"}]
    
    try:
        from src.core.config import settings
        
        now = datetime.now()
        events = get_calendar_events(days=days_ahead, max_results=100)
        
        if isinstance(events, list) and events and "error" in events[0]:
            return events
        
        # Encontrar slots libres (simplificado)
        free_slots = []
        
        for day_offset in range(days_ahead):
            day = now + timedelta(days=day_offset)
            day_start = day.replace(hour=work_start, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=work_end, minute=0, second=0, microsecond=0)
            
            if day_start < now:
                day_start = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            
            if day_start >= day_end:
                continue
            
            # Obtener eventos del día
            day_events = [
                e for e in events
                if isinstance(e, dict) and "start" in e 
                and e["start"] and day.strftime("%Y-%m-%d") in str(e["start"])
            ]
            
            # Ordenar por hora de inicio
            day_events.sort(key=lambda x: x.get("start", ""))
            
            current_time = day_start
            
            for event in day_events:
                event_start = event.get("start", "")
                if "T" in str(event_start):
                    event_start_dt = datetime.fromisoformat(
                        event_start.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                    
                    if event_start_dt > current_time:
                        gap_minutes = (event_start_dt - current_time).total_seconds() / 60
                        if gap_minutes >= duration_minutes:
                            free_slots.append({
                                "date": day.strftime("%Y-%m-%d"),
                                "start": current_time.strftime("%H:%M"),
                                "end": event_start_dt.strftime("%H:%M"),
                                "duration_minutes": int(gap_minutes),
                            })
                    
                    event_end = event.get("end", "")
                    if "T" in str(event_end):
                        current_time = datetime.fromisoformat(
                            event_end.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
            
            # Slot después del último evento
            if current_time < day_end:
                gap_minutes = (day_end - current_time).total_seconds() / 60
                if gap_minutes >= duration_minutes:
                    free_slots.append({
                        "date": day.strftime("%Y-%m-%d"),
                        "start": current_time.strftime("%H:%M"),
                        "end": day_end.strftime("%H:%M"),
                        "duration_minutes": int(gap_minutes),
                    })
        
        return free_slots[:10]  # Limitar a 10 slots
        
    except Exception as e:
        logger.error(f"Error buscando slots libres: {e}")
        return [{"error": str(e)}]


def _get_mock_events() -> list[dict[str, Any]]:
    """Datos mock para testing."""
    now = datetime.now()
    return [
        {
            "title": "Daily Standup",
            "start": (now + timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=1, minutes=30)).isoformat(),
            "_note": "Datos de ejemplo",
        },
        {
            "title": "Code Review",
            "start": (now + timedelta(hours=3)).isoformat(),
            "end": (now + timedelta(hours=4)).isoformat(),
        },
    ]


def create_calendar_tools() -> list:
    """Crea las herramientas de Calendar.
    
    Returns:
        Lista de herramientas
    """
    return [
        get_calendar_events,
        get_today_agenda,
        create_calendar_event,
        find_free_slots,
    ]

