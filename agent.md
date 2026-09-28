# Panel Control — Agent v10

> Centro de mando **local-first** para OpenCode. Un solo escritor `scripts/gen-dashboard.py` genera `dashboard.html` estático desde `opencode.db` + `opencode.json` + `git log`. Sin servidor, sin telemetría, estilo oscuro OpenCode. Ponytail full: la solución más corta que funciona.

## Identidad
Eres el agente del **Panel Control** (`C:\Proyectos\Skills\Panel Control`). Mantienes un **artefacto**: el HTML nunca lee la DB en runtime. Eres perezoso: stdlib antes que dependencia, borrar antes que añadir, un `gen-dashboard.py` que hace todo.

## Propósito
Dashboard en `http://localhost:3000/dashboard.html` (`8099` también) con 6 vistas:

- **Inicio:** 4 cards Consumo + 4 eficiencia (`$/k churn equipo`, `coste 30d`, `churn add+del`, `rework del/add`), `Evolución $/k churn` (30d diario / 90d semanal), `Por autor 30d`, `Coaching Sigue/Vigila/Corta` + `Analizar margen`.
- **Consumo:** 4 cards + `Actividad diaria 7d` fija + `Por proyecto` (`$/k churn` **real** por proyecto) + `Por modelo (est.)` + `Por agente familia (est.)` (`$/k churn` estimado por **tokens**). Tabs `Hoy/7d/30d/Total` y orden 3 estados `▼/▲/default` persistido.
- **Plataforma:** `Herramientas & caché` (build-time `part.type=tool` + `tokens.cache`) + `Git 7d` (`log --numstat --since=7 days`).
- **Recursos:** 26 agentes, 2 MCPs (`gsc`, `supadata`), 253 skills con filtro en vivo desde `~/.config/opencode/opencode.json`.
- **Tareas:** Goals, Crons, **Pendientes** (cuaderno agentes `Nombre::fecha::asunto`), calendario Pomodoro mensual con detalle por día.
- **Social:** `Supadata db27 panel-control-social` (owner `admin`) — `peers` + `messages`, **solo Google** (`Continuar con Google` GIS, avatar+nombre, filtra `anon-*`), tabla peers + chat al pinchar. `GOOGLE_CLIENT_ID` centralizado `.opencode/google_client_id.txt` (3000 autorizado).

## Métricas núcleo — qué miden y por qué

- **Churn `add+del`** (no `add-del` neto). Neto se hunde al reescribir (quitas+pones se cancela), churn cuenta lo tocado. `git log --numstat` por proyecto/rango → `PROJ_CHURN`. Equipo `total_churn_30 = sum(day_churn_30)` donde `day_churn = sum add+del del día`.
- **`$/k churn`** = `coste / (churn/1000)` menor es mejor. Por proyecto es **real** (coste y churn del mismo proyecto). Por modelo/familia es **estimado** porque git no guarda modelo/agente: `churn_estimado = churn_día * tokens_modelo_día / tokens_total_día` (reparto diario por **tokens**).
- **`Rework del/add`** = `del / add *100` en 30d. `<20%` ideal, `>30%` es re-picado. Antes bug 90d inflado a `98.9%` por `Ainversión 7.3M`; ahora 30d real `~31%`.

## Estructura que debe seguir el proyecto
```
Panel Control/
├── agent.md                 # este archivo — contrato
├── context.md               # estado vivo y decisiones
├── README.md                # uso, métricas y troubleshooting
├── dashboard.html           # artefacto generado — no editar a mano
├── favicon*.png / apple-touch-icon.png
├── scripts/
│   ├── gen-dashboard.py     # único escritor: DB + git + Supadata → HTML
│   ├── watch.py             # realtime local (opcional): watch opencode.db → regen
│   └── social_sync.py       # push peers a db27 (compartimentado)
├── data/                    # opcional caches git.json/tool_cache.json — gitignored
└── .opencode/
    ├── pending_tasks.json   # cuaderno pendientes (compartimentado)
    ├── skills/skill_pending|skill_social|skill_control|skill_centro_control/
    ├── goals/active|archive/*.md
    └── cron/jobs.json + runs/*.json
```

## Reglas (ponytail full)
1. **Single writer:** Solo `gen-dashboard.py` toca `opencode.db`/`opencode.json`/`git`. El HTML es render. `dashboard.html` nunca hace `sqlite-wasm`.
2. **Local-first:** `os.path.expanduser("~/.local/share/opencode/opencode.db")` y `~/.config/opencode/opencode.json`. Paths robustos tras move a `C:\Proyectos\Skills\Panel Control`.
3. **Degradación elegante:** sin `transcripts` → sin desglose tools (solo totales). Sin `.git` → `PROJ_CHURN=0` y `—`. Sin Supadata → `peers no disponibles` sin romper build.
4. **Sin backend:** nada de FastAPI/Prometheus/WebSocket. Realtime local es `watch.py` (poll/watchdog) + `softRefresh()` adaptativo `HEAD Last-Modified` 15s visible, pausa si `hidden`/`modal` abierto. Nunca `setInterval(location.reload())`.
5. **Estilo:** hereda tema oscuro OpenCode. Nuevos paneles usan `.card/.panel/.num/bar`. Tablas `table-layout:fixed` + `col` fijas, `tabular-nums`. No librerías externas.
6. **Sin inventar:** `jobs.json` vacío → `0 crons — crea uno con /skill_cron`. `pending_tasks.json` vacío → `sin pendientes`. No fake data.
7. **Módulos compartimentados:** cada feature aisalada en bloque `// MODULE START/END` (PENDING, SOCIAL, REALTIME). Quitar = borrar bloque + HTML + fichero sin tocar el resto.

## Módulos compartimentados
- **PENDING:** `.opencode/pending_tasks.json` formato `{"project","date":"YYYY-MM-DD","subject","desc","status":"open|done"}` + `.opencode/skills/skill_pending/SKILL.md` (título obligatorio `Nombre proyecto::fecha::asunto`). Tabla en Tareas con `thead/tbody` y filtro por `td` para no romper sort.
- **SOCIAL:** `SUPADATA_URL=https://pro-serv.tail9f39ff.ts.net` + `SOCIAL_KEY=sd_a0L7oRG_cK4oMCvIr-NTgWAM5eZ3oDvY` owner `admin` → `db27 panel-control-social` tablas `peers`/`messages`. `social_self` = `tok_today/30d, cost_today/30d, churn_30d, proyectos`. `social_sync.py --connect` hace `POST /v1/databases/db27/rows onConflict=google_sub|name` (solo Google, `anon-*` filtrado). UI: `Continuar con Google` (GIS) + `Desconectar`, muestra avatar/nombre real, pinchar fila abre `chatModal` `messages` filtrado `me↔peer`. `GOOGLE_CLIENT_ID` centralizado `.opencode/google_client_id.txt` (autorizado `localhost:3000`/`127.0.0.1:3000`). Otros equipos: `python scripts/serve.py` + Google en su `localhost:3000`.

## Realtime local saludable
- **watch.py:** `watchdog` si está, si no `poll 2s` sobre `opencode.db` + `opencode.json` + `pending_tasks.json` + `.git/HEAD`. Solo regenera si `mtime/size` cambia + debounce `2s` + throttle `1/5s`. Corre con `python scripts/watch.py` (WindowStyle Hidden).
- **softRefresh adaptativo:** `fetch HEAD` → `Last-Modified/ETag` si no cambió no descarga. Si cambió `fetch dashboard.html?v=...` → `JSON.parse D/EVO/PROJ_CHURN/MODEL_CHURN/AGENT_CHURN` → `render()/renderEvo()` + reemplazo `.grid` vía `DOMParser`. Preserva `localStorage pc_view/pc_range/pc_sorts_v2/pc_evo/pc_analisis/pc_scroll`, orden tablas, análisis abierto y `scrollY`. Pausa si `document.hidden` o modal `info/chat` abierto. `Ctrl+F5 / Ctrl+Shift+R` fuerza. `file:` hace `location.reload()`.

## Métricas con trampa — fixes v10
- **Bug `AGENT_CHURN`/`MODEL_CHURN` idénticos `0.70/k`:** se repartía por **coste** `churn_día * coste_familia/coste_total` → `eff = coste/(churn/1000) = total_coste/(total_churn/1000)` igual para todos el mismo día. **Fix:** reparto por **tokens** `churn_día * tokens_familia/tokens_total` → `eff = coste/tokens * total_tokens/(churn/1000)` ya diferencia (`Hoy build 0.60/k vs Enjambre 0.62/k`, cabecera ` (est.)` y tooltip aclara).
- **Bug `Rework 30d 98.9%`:** calculaba `sum(author_del 90d)/sum(author_add 90d)` (Ainversión 7.3M 99.9% dominaba) etiquetado como 30d. **Fix:** `author_add_30/del_30` filtrados por `d30_set` → `31.1% 40667/130623`, por autor también en 30d (`zherko 42.8%` no `6172%`).

## Implementación mínima (veredicto comité + fixes)
- **Tool & cache (build-time, ~20 líneas):** `SELECT data FROM part WHERE type='tool' LIMIT 20000` → `Counter(tool)` + `SELECT data FROM message WHERE role='assistant'` → `tokens.cache read/write + input/output`. Pre-render `cache_html/tool_rows`.
- **Git 7d/30d (~15 líneas):** `git -C <proyecto> log --since=7 days --numstat --pretty=format:` → `a+d` por proyecto×rango → `PROJ_CHURN`. Fallback `0` si no git.
- **Inicio churn 90d:** `git log --all --since=90 days --pretty=format:%aN%x1f%ct --numstat` → `author_churn_daily/day_churn/day_authors` + `author_add/del` (+ `_30` filtrado). `total_churn_30 = sum(day_churn 30d)`.

## Blindaje anti-parpadeo (obligatorio)
- Todo estado configurable (`pc_view/pc_range/pc_sorts_v2/pc_evo/pc_analisis/pc_scroll/pc_social_name/pc_social_connected`) persiste en `localStorage` y se restaura tras `softRefresh` (`render()`, `renderEvo()`, `tableKey()` + `table._orig=null`, `restoreSorts()`).
- Nuevas tablas: `tableKey()` (`view|headers` o `tbody.id`) + `pc_sorts_v2`. Nuevos grids: reemplazar vía `DOMParser` dentro de `softRefresh`.
- Prohibido `location.reload()` en intervalo; solo `softRefresh()`.

## Comandos
- Regenerar: `python scripts/gen-dashboard.py` → `OK -> dashboard.html | consumo total=7.4B ...`
- Servir: `python scripts/serve.py` → `http://localhost:3000/dashboard.html` (también `http://localhost:3000/` redirige)
- Realtime local: `python scripts/watch.py` (deja en background)
- Social push: `python scripts/social_sync.py --connect` (solo Google, anon estable si no hay Google)
- Lanzar: `/skill_control` (alias `/skill_centro_control`) — genera + sirve 3000

## No hacer
- No añadas servidor, framework ni dependencias nuevas sin aprobación.
- No leas la DB desde el browser (sqlite-wasm) ni regeneres cada 30s desde JS.
- No hardcodees orquestadores: familia genérica vía `session.parent_id` + `enjambre_sessions` (cualquier hijo de Enjambre → familia Enjambre).

---
*Creado 2026-09-27 comité técnico (Root Cause, Solution Explorer, Benchmark, Architect, Integration) — actualizado v10 2026-09-28 tras fixes Rework 30d y $/k por tokens + Social/Realtime.*
