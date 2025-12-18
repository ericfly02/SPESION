# SPESION - Arquitectura del Sistema Multi-Agente

## Visión General

SPESION es un asistente personal avanzado tipo "Jarvis" diseñado para Eric Gonzalez Duro, 
Ingeniero de Software. Utiliza una arquitectura híbrida con procesamiento local (Ollama) 
para tareas sensibles y cloud (OpenAI/Anthropic) para tareas complejas.

## Diagrama de Arquitectura Principal

```mermaid
flowchart TB
    subgraph Interface [Capa de Interfaz]
        TG[Telegram Bot<br/>python-telegram-bot]
        VOICE[Transcripcion Voz<br/>faster-whisper]
    end

    subgraph Orchestration [Capa de Orquestacion LangGraph]
        SUP[Supervisor Router]
        STATE[(AgentState<br/>TypedDict)]
        ROUTER{Decision<br/>Router}
    end

    subgraph Octagon [El Octagono - 8 Agentes Especializados]
        SCH[Scholar<br/>Investigador]
        COA[Coach<br/>Salud/Deporte]
        TYC[Tycoon<br/>Finanzas]
        COM[Companion<br/>Psicologo]
        TEC[TechLead<br/>Ingenieria]
        CON[Connector<br/>Networking]
        EXE[Executive<br/>Productividad]
        SEN[Sentinel<br/>DevOps/Privacidad]
    end

    subgraph LLMLayer [Capa LLM Hibrida]
        LOCAL[Ollama Local<br/>phi3:mini / llama3:8b]
        CLOUD[Cloud LLMs<br/>GPT-4o / Claude 3.5]
    end

    subgraph Storage [Capa de Persistencia]
        CHROMA[(ChromaDB<br/>Vector Store)]
        SQLITE[(SQLite<br/>Logs/Estado)]
        NOTION[Notion API<br/>Knowledge Base]
    end

    subgraph MCPTools [Herramientas MCP]
        ARXIV[ArXiv API]
        GARMIN[Garmin Connect]
        STRAVA[Strava API]
        GITHUB[GitHub MCP]
        GCAL[Google Calendar]
        YAHOO[Yahoo Finance]
        TAVILY[Tavily Search]
        SANDBOX[Docker Sandbox]
    end

    %% Flujo de entrada
    TG -->|Texto| SUP
    TG -->|Audio| VOICE
    VOICE -->|Transcripcion| SUP

    %% Orquestacion
    SUP --> STATE
    STATE --> ROUTER
    ROUTER --> SCH
    ROUTER --> COA
    ROUTER --> TYC
    ROUTER --> COM
    ROUTER --> TEC
    ROUTER --> CON
    ROUTER --> EXE
    ROUTER --> SEN

    %% Conexiones LLM
    SEN -->|Filtro PII| CLOUD
    COM -->|Privacidad| LOCAL
    COA -->|Datos Salud| LOCAL
    SCH --> CLOUD
    TEC --> CLOUD
    TYC --> CLOUD
    EXE --> LOCAL
    CON --> CLOUD

    %% Herramientas por Agente
    SCH --> ARXIV
    SCH --> TAVILY
    COA --> GARMIN
    COA --> STRAVA
    TYC --> YAHOO
    TEC --> GITHUB
    TEC --> SANDBOX
    EXE --> GCAL
    EXE --> NOTION
    CON --> NOTION
    COM --> CHROMA

    %% Persistencia
    STATE --> SQLITE
    COM --> CHROMA
    SCH --> CHROMA
```

## Flujo de Datos Detallado

```mermaid
sequenceDiagram
    participant U as Usuario
    participant TG as Telegram Bot
    participant W as Whisper Service
    participant SEN as Sentinel
    participant SUP as Supervisor
    participant AG as Agente Especializado
    participant LLM as LLM Factory
    participant RAG as ChromaDB
    participant TOOLS as MCP Tools

    U->>TG: Mensaje/Audio
    alt Audio Message
        TG->>W: Audio file
        W->>TG: Transcripcion
    end
    
    TG->>SEN: Texto sanitizado
    SEN->>SEN: Detectar PII
    SEN->>SUP: Mensaje + privacy_mode
    
    SUP->>RAG: retrieve_context(query)
    RAG->>SUP: Contexto relevante
    
    SUP->>SUP: Clasificar intent
    SUP->>AG: Delegar a agente
    
    AG->>LLM: get_llm(task_type, privacy)
    LLM->>AG: LLM apropiado
    
    AG->>TOOLS: Ejecutar herramientas
    TOOLS->>AG: Resultados
    
    AG->>SUP: Respuesta
    SUP->>TG: Respuesta final
    TG->>U: Mensaje
```

## Arquitectura de Agentes

```mermaid
classDiagram
    class BaseAgent {
        <<abstract>>
        +name: str
        +description: str
        +llm: BaseLLM
        +tools: list[Tool]
        +system_prompt: str
        +invoke(state: AgentState) AgentState
        +get_tools() list[Tool]
    }

    class ScholarAgent {
        +search_arxiv()
        +summarize_paper()
        +get_news()
    }

    class CoachAgent {
        +get_garmin_data()
        +get_strava_activities()
        +analyze_recovery()
        +suggest_workout()
    }

    class TycoonAgent {
        +get_portfolio()
        +analyze_allocation()
        +suggest_rebalance()
        +track_expenses()
    }

    class CompanionAgent {
        +journal_entry()
        +analyze_mood()
        +retrieve_memories()
        +emotional_support()
    }

    class TechLeadAgent {
        +code_review()
        +execute_code()
        +architecture_advice()
        +debug_help()
    }

    class ConnectorAgent {
        +manage_contacts()
        +prepare_icebreaker()
        +simulate_negotiation()
    }

    class ExecutiveAgent {
        +manage_calendar()
        +prioritize_tasks()
        +energy_management()
    }

    class SentinelAgent {
        +sanitize_pii()
        +monitor_system()
        +audit_logs()
    }

    BaseAgent <|-- ScholarAgent
    BaseAgent <|-- CoachAgent
    BaseAgent <|-- TycoonAgent
    BaseAgent <|-- CompanionAgent
    BaseAgent <|-- TechLeadAgent
    BaseAgent <|-- ConnectorAgent
    BaseAgent <|-- ExecutiveAgent
    BaseAgent <|-- SentinelAgent
```

## Grafo LangGraph

```mermaid
stateDiagram-v2
    [*] --> Sentinel: Entrada
    Sentinel --> Supervisor: Mensaje sanitizado
    
    Supervisor --> Scholar: intent=research
    Supervisor --> Coach: intent=health
    Supervisor --> Tycoon: intent=finance
    Supervisor --> Companion: intent=emotional
    Supervisor --> TechLead: intent=coding
    Supervisor --> Connector: intent=networking
    Supervisor --> Executive: intent=productivity
    
    Scholar --> Supervisor: Resultado
    Coach --> Supervisor: Resultado + energy_level
    Tycoon --> Supervisor: Resultado
    Companion --> Supervisor: Resultado + user_mood
    TechLead --> Supervisor: Resultado
    Connector --> Supervisor: Resultado
    Executive --> Supervisor: Resultado
    
    Supervisor --> [*]: Respuesta final
```

## Decisión LLM Local vs Cloud

```mermaid
flowchart TD
    START[Nuevo Request] --> PII{Contiene PII?}
    PII -->|Si| LOCAL[Usar Ollama Local]
    PII -->|No| TASK{Tipo de Tarea?}
    
    TASK -->|Journal/Emocional| LOCAL
    TASK -->|Datos Salud| LOCAL
    TASK -->|Chat Casual| LOCAL
    
    TASK -->|Analisis Papers| CLOUD[Usar OpenAI/Anthropic]
    TASK -->|Codigo Complejo| CLOUD
    TASK -->|Razonamiento Financiero| CLOUD
    TASK -->|Investigacion Web| CLOUD
    
    LOCAL --> RESPONSE[Generar Respuesta]
    CLOUD --> RESPONSE
```

## Estructura de Bases de Datos

### ChromaDB Collections
- `memories`: Memorias a largo plazo del Companion
- `papers`: Resúmenes de papers de ArXiv
- `knowledge`: Notas y conocimiento general
- `conversations`: Historial de conversaciones relevantes

### SQLite Tables
- `conversation_logs`: Historial completo de mensajes
- `agent_metrics`: Métricas de uso por agente
- `transactions`: Logs de operaciones financieras
- `system_events`: Eventos del sistema y errores

## Comandos Telegram

| Comando | Agente | Descripción |
|---------|--------|-------------|
| `/start` | Supervisor | Iniciar conversación |
| `/resumen` | Scholar | Resumen diario de papers/noticias |
| `/entreno` | Coach | Plan de entrenamiento del día |
| `/finance` | Tycoon | Estado del portfolio |
| `/audit` | TechLead | Code review de un repo |
| `/journal` | Companion | Iniciar entrada de diario |
| `/agenda` | Executive | Tareas y calendario del día |
| `/status` | Sentinel | Estado del sistema |

## Variables de Entorno Requeridas

```env
# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Telegram
TELEGRAM_BOT_TOKEN=...

# APIs Externas
NOTION_API_KEY=...
GARMIN_EMAIL=...
GARMIN_PASSWORD=...
STRAVA_CLIENT_ID=...
STRAVA_CLIENT_SECRET=...
GITHUB_TOKEN=...
GOOGLE_CALENDAR_CREDENTIALS=...
TAVILY_API_KEY=...

# Storage
CHROMA_PERSIST_DIR=./data/chroma
SQLITE_DB_PATH=./data/spesion.db
```

## Consideraciones de Hardware

- **CPU**: Intel i5-8259U (4 cores, 8 threads)
- **RAM**: 16GB
- **GPU**: Integrada (Intel Iris Plus 655)

### Optimizaciones:
1. Usar modelos cuantizados para Ollama (phi3:mini, llama3:8b-q4)
2. Limitar contexto de ChromaDB a 5 documentos por query
3. Batch processing para tareas no urgentes
4. Caché de respuestas frecuentes en SQLite

