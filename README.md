# Control-Code — Panel Control

Centro de mando **local-first** para OpenCode. Dashboard **estático** que agrega consumo, eficiencia, git y recursos desde tu máquina. Un escritor `scripts/gen-dashboard.py` → `dashboard.html` (~180KB). Sin servidor, sin telemetría, sin dependencias nuevas. Servido en `http://localhost:8099/dashboard.html`.

![dashboard](https://img.shields.io/badge/dashboard-estático-58a6ff) ![local-first](https://img.shields.io/badge/local--first-opencode.db-3fb950) ![realtime](https://img.shields.io/badge/realtime-watch%2BHEAD-8b5cf6) ![python](https://img.shields.io/badge/python-3.x%20stdlib-blue)

## Demo — qué verás
- **Inicio:** `Eficiencia equipo $/k churn` + `Rework 30d` + `Evolución $/k` (30d diario / 90d semanal) + `Por autor 30d` + coaching.
- **Consumo:** `Por proyecto $/k churn` (real git) + `Por modelo/familia $/k (est.)` por tokens — ya no idénticos.
- **Tareas:** calendario Pomodoro + **Pendientes** `Nombre::fecha::asunto` + Goals/Crons.
- **Social:** peers conectados vía Supadata `db27` + chat privado al pinchar.

## Qué hace

### Inicio
- **4+4 cards:** Consumo `Hoy/7d/30d/Total` y eficiencia `Equipo $/k churn`, `Coste 30d`, `Churn 30d add+del`, `Rework 30d del/add`.
- **Evolución eficiencia** SVG `220px` fijo sin scroll, tooltip `$/k`. `30d` diario + `90d` semanal agregado.
- **Por autor 30d** churn/rework/commits/días, ordenado por eficiencia. `Sigue así / Vigila / Corta` + `Analizar margen` (peor `$/k` 30d).

### Consumo
- **Actividad diaria 7d** fija (no cambia con tabs) — pulso diario.
- **Por proyecto** `Tokens/Coste/Coste/msg/Msgs/$/k churn` (real `PROJ_CHURN` por proyecto×rango) + barra. **Por modelo** y **Por agente familia** `$/k (est.)` reparto diario por **tokens** (fix v10: antes por coste daba mismo `0.70/k`).
- **Ordenable 3 estados** `▼ desc → ▲ asc → default` con `tableKey()` + `pc_sorts_v2` persistido.

### Plataforma
- **Herramientas & caché** build-time: `Cache hit %` + `Tokens cache` desde `part.type=tool` + `message.tokens.cache` (hit `>90%` bueno). Top `bash/read/edit`.
- **Git 7d** `git log --since=7 days --numstat` por proyecto (`commits`, `+`/`-`).

### Recursos
- `26 agentes` (mode/tools) + `2 MCPs` (`gsc`, `supadata`) + `253 skills` con filtro en vivo desde `~/.config/opencode/opencode.json`.

### Tareas
- Goals (`1 activo seo-skill-push`), Crons (`0`), **Pendientes** (cuaderno agentes) y **calendario Pomodoro** mensual. Pinchar día → detalle `tokens/coste/proyecto/modelo` de ese día. `localStorage pc_*` para rango/vista/orden/evo/analisis/scroll.

### Social
- `Supadata db27 panel-control-social` (owner `admin`) tablas `peers`/`messages`. Solo botón `⚡ Conectar` genera `anon-XXXX` único (si existe añade sufijo), `Desconectar` pone `offline`. Pinchar peer abre chat privado. `social_sync.py --connect --name X` también conecta desde CLI. Todo `admin` directo como pidió el usuario (`SOCIAL_KEY` embebida).

## Métricas en 30 segundos

| Métrica | Qué es | Por qué churn no neto |
|---------|--------|----------------------|
| **Churn `add+del`** | líneas tocadas (quitas+pones) vía `git log --numstat` 30d `~171K` | `neto = add-del` se hunde al reescribir (sustituyes y `neto→0` aunque trabajes). Churn no se degrada. |
| **`$/k churn`** | `coste / (churn/1000)` menor es mejor | Por proyecto **real**. Por modelo/familia **estimado por tokens** `churn_día * tokens_familia/tokens_total` (no por coste, que forzaba mismo valor). |
| **`Rework del/add`** | `del / add *100` | `31.1%` hoy (del 40K/add 130K) — `<20%` ideal. Bug previo `98.9%` mostraba 90d histórico `Ainversión 7.3M` como 30d. |

## Fuente de verdad

| Fuente | Qué aporta |
|--------|------------|
| `~/.local/share/opencode/opencode.db` | 24k+ msgs, `message.tokens`/`cost`, `session`/`project`, `part.data.type=tool` (6.85B tokens) |
| `~/.config/opencode/opencode.json` | 26 agentes, 253 skills, 2 MCPs |
| `git log --numstat --since=30/90 days` | `day_churn`, `PROJ_CHURN`, `author_churn_daily` (90d `~7.5M` histórico) |
| `~/.config/opencode/opencode.json:457` | `SUPADATA_API_KEY=sd_a0L...` + `SUPADATA_URL` para Social |

> `opencode.db` no tiene columna `tool` — tools se agregan de `part.type=tool`, no por `SELECT tool`.

## Uso rápido

```powershell
# Vía skills (recomendado) — genera + sirve 8099
/skill_control            # alias /skill_centro_control también vale

# Manual
python scripts/gen-dashboard.py
# OK -> dashboard.html | consumo total=7.40B | agentes=26 skills=253 ...

python -m http.server 8099
# http://localhost:8099/dashboard.html

# Realtime local (opcional, deja en background)
python scripts/watch.py
# mira opencode.db/opencode.json/pending_tasks.json/.git/HEAD, regen solo si cambia (debounce 2s)

# Social CLI
python scripts/social_sync.py --connect --name TuNombre
```

**Auto-refresh:** `softRefresh()` adaptativo `HEAD Last-Modified/ETag` cada `15s` visible, pausa si `document.hidden` o modal `info/chat` abierto, `Ctrl+F5` fuerza. Nunca `location.reload()` salvo `file:`. Estado `localStorage pc_view/pc_range/pc_sorts_v2/pc_evo/pc_analisis/pc_scroll/pc_social_*`.

## Estructura

```
Panel Control/
├── agent.md                 # contrato del agente (single writer, blindaje)
├── context.md               # estado vivo y decisiones
├── README.md                # este archivo
├── dashboard.html           # artefacto generado — no editar a mano
├── favicon*.png / apple-touch-icon.png
├── scripts/
│   ├── gen-dashboard.py     # único escritor: DB + git + Supadata → HTML
│   ├── watch.py             # realtime local (watchdog o poll)
│   └── social_sync.py       # push peers a db27
└── .opencode/
    ├── pending_tasks.json   # cuaderno pendientes (compartimentado)
    ├── skills/skill_pending|skill_social|skill_control|skill_centro_control/
    ├── goals/active|archive/*.md
    └── cron/jobs.json
```

## Módulos opcionales — quitar sin romper

Cada feature vive en bloque `// MODULE START/END` aislado:

- **Pendientes:** fichero `pending_tasks.json` formato `{"project","date":"YYYY-MM-DD","subject","desc","status"}` + skill `skill_pending` (título obligatorio `Nombre proyecto::fecha::asunto` 80ch + `desc` 1-4 líneas). Tabla `thead/tbody` con filtro por `td[colspan]` para no romper sort. Borra `pending_tasks.json` + skill + bloque PENDING para quitar.
- **Social:** `db27 panel-control-social` owner `admin` tablas `peers(id,name,tok_today/30d,cost_today/30d,churn_30d,projects,updated_at,status)` + `messages(from_name,to_name,body,created_at)`. Todo `admin` (`SOCIAL_KEY=sd_a0L...`). Borra `db27` + `social_sync.py` + bloque SOCIAL para quitar.
- **Realtime:** `watch.py` + `softRefresh` HEAD. Borra `watch.py` y vuelve a `setInterval 30s` si quieres.

## Troubleshooting

- **No ves peers:** es snapshot build-time + live `fetch db27/peers`. Si Supadata cae, muestra `peers no disponibles` sin romper.
- **`0 commits` en Git 7d:** proyecto no es repo git o fuera de `[:14]` paths más activos.
- **Rework alto `~31%`:** normal si re-picaste `Enjambre 93%`/`Potencia 71%` — revisa `Por autor 30d` y `Analizar margen` para el peor `$/k`.

## Requisitos

- Python 3.x stdlib (`sqlite3`, `json`, `subprocess`, `urllib`) — nada de pip.
- `opencode.db` y `opencode.json` en rutas estándar. Git instalado para `log --numstat`.

## Licencia

MIT — local-first, sin telemetría.
