# Panel Control — Agent

> Centro de mando local-first para OpenCode. Genera `dashboard.html` estático desde `opencode.db` + `transcripts/`. Sin servidor, sin telemetría, estilo oscuro OpenCode.

## Identidad
Eres el agente del **Panel Control**. Mantienes un dashboard que es un artefacto: un solo `python scripts/gen-dashboard.py` genera todo. El HTML nunca lee la DB en runtime. Eres perezoso: la solución más corta que funciona, sin añadir dependencias.

## Propósito
- **Consumo:** tokens/coste por día, semana, mes, proyecto y modelo (ya existe). No inventes datos: lee solo `~/.local/share/opencode/opencode.db` (tabla `message` con `tokens`/`cost`).
- **Recursos:** inventario de 26 agentes, 247 skills, 2 MCPs desde `~/.config/opencode/opencode.json`.
- **Tareas:** goals, crons y calendario mensual estilo Pomodoro (interactivo, con detalle por día).
- **Próximo:** Tool & cache panel, Git panel y auto-refresh toggle — ver Implementación mínima abajo (veredicto del comité).

## Estructura que debe seguir el proyecto
```
Panel Control/
├── agent.md                 # este archivo — contrato del agente
├── SKILL.md                 # (futuro) skill instalable opcional
├── dashboard.html           # artefacto generado — no editar a mano
├── scripts/
│   └── gen-dashboard.py     # único escritor: lee DB + transcripts + git → HTML
├── data/                    # (opcional) caches intermedios tool_cache.json, git.json — gitignored
├── .opencode/
│   ├── goals/active|archive/*.md
│   └── cron/jobs.json + runs/*.json
└── README.md                # cómo regenerar y servir
```

## Reglas (ponytail)
1. **Single writer:** Solo `gen-dashboard.py` toca la DB y los transcripts. El HTML es render.
2. **Local-first:** `DB_PATH = Path(__file__).resolve().parents[1] / ".local/..."` o `os.expanduser("~/.local/share/opencode/opencode.db")` — path robusto tras el move a `C:\Proyectos\Skills\Panel Control`.
3. **Degradación elegante:** si `transcripts/` no existe → Tool & cache muestra "cache total" sin desglose. Si `git rev-parse` falla → Git panel muestra "no git".
4. **Sin backend:** nada de FastAPI, Prometheus, WebSocket. El auto-refresh es `softRefresh()` vía `fetch('dashboard.html')` + `JSON.parse` de `D/EVO/PROJ_CHURN` y re-render, **nunca `location.reload()`** (evita parpadeo). Preserva `localStorage` (`pc_view/pc_range/pc_sorts_v2/pc_evo/pc_analisis/pc_scroll`), orden de tablas, gráficas y analizador abierto. Fallback a `location.reload()` solo si `protocol==='file:'`.
5. **Estilo:** hereda `styles.css` oscuro OpenCode. Nuevos paneles usan `.card` / `.panel` existentes. Nada de librerías externas. Tablas con `col` y `padding` fijos para no solaparse; analizador con `table-layout:fixed`.
6. **Sin inventar:** si `jobs.json` está vacío → muestra "0 crons — crea uno con /skill_cron", no fake data.

## Implementación mínima (veredicto comité) — no implementar sin leer esto
- **Tool & cache panel (build-time, ~20 líneas Python):** parsea `transcripts/**/*.jsonl`, agrega `tool_calls[].name` con `tokens.cacheRead + cacheCreation`. No intentes `SELECT tool FROM opencode.db` — esa columna no existe. Renderiza tabla pre-calculada en HTML.
- **Git panel (~15 líneas):** `subprocess.check_output(["git","-C", proyecto ,"log","--since=7 days","--oneline"])` por cada proyecto listado en Consumo. Contar commits. Fallback a `0` si no es git.
- **Auto-refresh (~30 líneas JS):** `softRefresh()` hace `fetch('dashboard.html?v='+Date.now())` → parsea `var D/EVO/PROJ_CHURN` → `D=JSON.parse` → `render()/renderEvo()` + reemplaza `.grid` estáticos. Preserva `pc_scroll` y `pc_analisis` (reabre analizador con datos frescos). No `location.reload()` salvo `file:`.

## Blindaje anti-parpadeo (obligatorio para lo nuevo)
- Todo estado que el usuario pueda configurar (orden columnas, pestaña, rango, `30/90d`, analizador abierto, scroll) **debe persistir en `localStorage` (`pc_*`)** y **restaurarse tras `softRefresh`**.
- Nuevas tablas: usar `tableKey()` (`view|headers` o `tbody.id`) + `localStorage pc_sorts_v2`, y limpiar `table._orig=null` en cada `render()` para no arrastrar filas viejas.
- Nuevos paneles/cards estáticos: incluirlos en `softRefresh` (reemplazo de `.grid` via `DOMParser`) para que se actualicen sin `reload`.
- Prohibido `location.reload()` en el intervalo; solo `softRefresh()`.

## Comandos
- Regenerar: `python scripts/gen-dashboard.py`
- Servir: `python -m http.server 8099` → http://localhost:8099/dashboard.html
- Ver crons: `/skill_cron list`  ·  Ver goals: contenido en `.opencode/goals/`
- Lanzar: `/skill_control`

## No hacer
- No añadas servidor, framework, ni dependencias nuevas sin aprobación.
- No leas la DB desde el browser (sqlite-wasm).
- No ejecutes `gen-dashboard.py` cada 30s desde JS — solo reload. La regeneración la hace el usuario o un cron del SO.

---
*Creado 2026-09-27 tras comité técnico (Root Cause, Solution Explorer, Benchmark, Architect, Integration) — veredicto: build-time, HTML estático, islas JS.*
