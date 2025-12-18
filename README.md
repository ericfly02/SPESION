# SPESION

**Sistema Personal de Asistencia Inteligente Orquestada por Nodos** - Tu asistente personal tipo "Jarvis" construido con LangGraph.

## Descripción

SPESION es un sistema multi-agente avanzado diseñado para actuar como asistente personal integral. Utiliza una arquitectura híbrida que combina procesamiento local (Ollama) para datos sensibles y cloud (OpenAI/Anthropic) para tareas complejas.

## Arquitectura

El sistema está compuesto por 8 agentes especializados coordinados por un Supervisor:

| Agente | Especialidad | LLM |
|--------|-------------|-----|
| **Scholar** | Investigación, ArXiv, noticias tech | Cloud |
| **Coach** | Fitness, Garmin, Strava, entrenamiento | Local |
| **Tycoon** | Portfolio, inversiones, finanzas | Cloud |
| **Companion** | Journaling, bienestar emocional | Local |
| **TechLead** | Code review, debugging, arquitectura | Cloud |
| **Connector** | Networking, CRM, preparación eventos | Cloud |
| **Executive** | Calendario, tareas, productividad | Local |
| **Sentinel** | Privacidad, seguridad, monitoreo | Local |

Ver [architecture.md](./architecture.md) para diagramas detallados.

## Stack Tecnológico

- **Orquestación**: LangGraph (StateGraph)
- **LLM Local**: Ollama (phi3:mini, llama3:8b)
- **LLM Cloud**: OpenAI GPT-4o / Anthropic Claude 3.5
- **Vector Store**: ChromaDB
- **Base de datos**: SQLite
- **Interfaz**: Telegram Bot (python-telegram-bot)
- **Transcripción**: faster-whisper (local)
- **Contenedores**: Docker + Docker Compose

## Requisitos

- Python 3.11+
- Docker y Docker Compose
- [Ollama](https://ollama.ai) instalado localmente
- Cuenta de Telegram Bot (@BotFather)

## Instalación

### 1. Clonar repositorio

```bash
git clone https://github.com/tuusuario/spesion.git
cd spesion
```

### 2. Configurar entorno

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tus API keys
nano .env
```

Variables mínimas requeridas:
- `TELEGRAM_BOT_TOKEN`: Token de tu bot de Telegram
- `OPENAI_API_KEY` o `ANTHROPIC_API_KEY`: Para LLM cloud

### 4. Instalar modelos de Ollama

```bash
# Modelo ligero (recomendado para CPU)
ollama pull phi3:mini

# Modelo más potente (si tienes más RAM)
ollama pull llama3:8b-instruct-q4_0
```

### 5. Ejecutar

```bash
# Setup inicial
python main.py --setup

# Ejecutar bot de Telegram
python main.py

# O ejecutar CLI interactivo
python main.py --cli
```

## Uso con Docker

```bash
# Construir y ejecutar
cd docker
docker-compose up -d

# Ver logs
docker-compose logs -f spesion

# Parar
docker-compose down
```

## Comandos de Telegram

| Comando | Descripción |
|---------|-------------|
| `/start` | Iniciar conversación |
| `/help` | Ver ayuda |
| `/resumen` | Resumen diario de papers y noticias |
| `/entreno` | Plan de entrenamiento del día |
| `/finance` | Estado del portfolio |
| `/journal` | Iniciar journaling |
| `/agenda` | Calendario y tareas |
| `/audit owner/repo` | Code review de un repo |
| `/status` | Estado del sistema |

## Estructura del Proyecto

```
spesion/
├── src/
│   ├── agents/          # 8 agentes especializados
│   ├── core/            # Graph, State, Config, Prompts
│   ├── tools/           # Herramientas MCP
│   ├── services/        # LLM Factory, Vector Store, Memory
│   └── interfaces/      # Telegram Bot
├── docker/              # Dockerfiles y compose
├── data/                # Persistencia (ChromaDB, SQLite)
├── main.py              # Punto de entrada
├── requirements.txt
└── architecture.md      # Diagramas de arquitectura
```

## APIs Soportadas

- **ArXiv**: Búsqueda de papers
- **Garmin Connect**: Métricas de salud
- **Strava**: Actividades deportivas
- **Notion**: Tasks, Knowledge, CRM
- **GitHub**: Code review
- **Google Calendar**: Agenda
- **Yahoo Finance**: Datos de mercado
- **Tavily/DuckDuckGo**: Búsqueda web

## Hardware Recomendado

El sistema está optimizado para:
- CPU: Intel i5 o superior
- RAM: 16GB mínimo
- GPU: No requerida (usa CPU para Ollama)

## Desarrollo

```bash
# Instalar dependencias de desarrollo
pip install -r requirements.txt
pip install pytest black ruff mypy

# Formatear código
black src/
ruff check src/ --fix

# Ejecutar tests
pytest tests/
```

## Licencia

MIT License - Ver [LICENSE](./LICENSE)

## Autor

Eric Gonzalez Duro

---

*"No es magia, es ingeniería bien hecha."* - SPESION
