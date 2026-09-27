# Control-Code — Panel Control

Centro de mando **local-first** para OpenCode. Dashboard estático que visualiza consumo, recursos y tareas desde tu máquina. Sin servidor, sin telemetría, sin dependencias nuevas.

> Generado por un único escritor `scripts/gen-dashboard.py` → `dashboard.html` (71KB). Servido en `http://localhost:8099/dashboard.html`.

![Dashboard](https://img.shields.io/badge/dashboard-est%C3%A1tico-58a6ff) ![Local-first](https://img.shields.io/badge/local--first-opencode.db-3fb950) ![Python](https://img.shields.io/badge/python-3.x-blue)

## Qué hace

### Consumo
- **4 cards:** Hoy / 7d / 30d / Total (tokens, coste, msgs).
- **Gráfica 7 días** fija + tablas **Por proyecto** y **Por modelo** con `Coste/msg` y barra. Columnas alineadas cross-table.
- **Ordenable 3 estados:** clic en header → `▼ desc` → `▲ asc` → `default`.
- **Herramientas & caché** (build-time): hit rate + top tools (`bash`, `read`…) desde `part.type=tool`.
- **Git 7d** (build-time): `git log --since=7 days --numstat` por proyecto.

### Recursos
- 26 agentes, 2 MCPs (`gsc`, `supadata`), 247 skills con filtro en vivo — desde `~/.config/opencode/opencode.json`.

### Tareas
- Goals, crons y **calendario Pomodoro** mensual. Pincha un día → detalle tokens/coste/proyecto/modelo.

## Fuente de verdad

| Fuente | Qué aporta |
|--------|------------|
| `~/.local/share/opencode/opencode.db` | 24k+ msgs, tokens/coste (tabla `message`) |
| `~/.config/opencode/opencode.json` | Agentes, skills, MCPs |
| `transcripts/` + `git log` | Tools/caché y actividad Git |

`opencode.db` **no** tiene columna `tool` → tools se parsean de `part.data.type=tool`, no por SQL.

## Uso rápido

```powershell
# 1. Generar
python scripts/gen-dashboard.py
# OK -> dashboard.html | consumo total=6.85B | agentes=26 skills=247

# 2. Servir
python -m http.server 8099
# http://localhost:8099/dashboard.html
```

Auto-refresh oculto cada 30s (`location.reload()`). Manual: `Ctrl+F5`.

## Estructura

```
Panel Control/
├── README.md
├── agent.md              # contrato del agente (single writer, local-first)
├── context.md            # estado actual y decisiones del comité
├── dashboard.html        # artefacto generado — no editar a mano
├── scripts/
│   └── gen-dashboard.py  # único escritor: DB + transcripts + git → HTML
└── .opencode/
    ├── goals/active|archive/*.md
    └── cron/jobs.json
```

## Reglas clave

1. **Single writer:** solo `gen-dashboard.py` toca la DB. El HTML es render.
2. **Local-first:** paths vía `os.path.expanduser("~/.local/...")`.
3. **Degradación elegante:** sin `transcripts/` → sin desglose tools; sin git → `0`.
4. **Sin backend:** sin FastAPI/Prometheus/WebSocket.

Ver `agent.md` para el contrato completo y `context.md` para el historial.

## Requisitos

- Python 3.x (solo stdlib: `sqlite3`, `json`, `subprocess`)
- `opencode.db` y `opencode.json` en las rutas estándar

## Licencia

MIT
