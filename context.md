# Panel Control — Context

> Centro de mando local-first para OpenCode. Última actualización: 2026-09-27 14:40 (Dashboard v9)

## Dónde estamos

Migración completa desde `Default Project` a **`C:\Proyectos\Skills\Panel Control`** — proyecto ya vive ahí. Servido en `http://localhost:8099/dashboard.html`.

- **Fuente de verdad:** `~/.local/share/opencode/opencode.db` (24.7k msgs, 6.85B tokens) + `~/.config/opencode/opencode.json` (26 agentes, 247 skills, 2 MCPs) + `transcripts`/`git` para los nuevos paneles.
- **Artefacto:** `dashboard.html` estático (71KB) generado por un único escritor `scripts/gen-dashboard.py`. Sin servidor, sin telemetría, sin dependencias nuevas.

## Qué ya funciona

### 1. Consumo (pestaña)
- 4 cards: Hoy / 7d / 30d / Total (tokens, coste, msgs).
- Gráfica 7 días fija (no cambia con los tabs); tabs solo filtran las dos tablas inferiores.
- **Por proyecto** y **Por modelo** con `Coste/msg` (`$x.xxxx` 4 decimales) y barra. Columnas alineadas cross-table (`table-layout:fixed`, diff 0.0px verificado con Playwright).
- **Ordenable 3 estados:** clic header → `▼ desc` → `▲ asc` → `default`. Delegado en `document`, con `table._orig` para restaurar.
- **Herramientas & caché** (nuevo, build-time): 3 cards `Cache hit 94.8%` + tabla top tools (`bash 5852`, `read 3470`…) desde `part.type=tool` y `message.tokens.cache`.
- **Git 7d** (nuevo, build-time): `git -C <proyecto> log --since=7 days --numstat` por cada proyecto. Muestra commits y líneas +/-; proyectos no-git → `0`.

### 2. Recursos (pestaña)
- 26 agentes (mode/tools), 2 MCPs (`gsc`, `supadata`), 247 skills con filtro en vivo.

### 3. Tareas (pestaña)
- Goals (1 activo `seo-skill-push`), Crons (0), Calendario mensual estilo **Pomodoro** (`historial.js:76` + `styles.css:286`).
- Navegación ‹ › entre meses, sin pasar del mes actual. Día con gasto = fondo azulado, hoy/selección = invertido, futuro = atenuado.
- **Detalle al pinchar día:** tokens/coste/consultas + dos tablas Proyecto/Modelo de ese día, también ordenables y con columnas alineadas (diff 0.0px).

### Infra
- **Auto-refresh oculto pero marcado:** `<input id="ar" checked style="display:none">` + `setInterval(reload,30s)`. Manual con `Ctrl+F5` / `Ctrl+Shift+R`.
- **Alineación:** `th.num/td.num` con `tabular-nums`, `table-layout:fixed`, columna bar vacía en Por modelo para igualar anchos cross-table.

## Decisiones clave (comité técnico)

Veredicto: *las 3 mejoras solo en `gen-dashboard.py` (build-time), HTML sigue estático*. 
- `opencode.db` no tiene `tool` por mensaje → Tool & cache debe parsear `part`/`transcripts`, no SQL.
- `git log` por proyecto con fallback `0`.
- Auto-refresh solo `location.reload()`, no `fetch(opencode.db)` (file:// lo bloquea).

Ver `agent.md` para contrato del agente y reglas ponytail.

## Estructura

```
Panel Control/
├── agent.md
├── context.md            # este archivo
├── dashboard.html
├── scripts/gen-dashboard.py
└── .opencode/goals| Cron
```

## Cómo regenerar

```powershell
python scripts/gen-dashboard.py
python -m http.server 8099  # desde Panel Control
# http://localhost:8099/dashboard.html
```

## Pendiente / ideas

- Presupuesto mensual y alerta >80% cuota (de `research-ops`).
- `Coste por commit` (unir Git + coste 7d).
- Heatmap horario (de `hourly` ya en payload).
- Exportar CSV del día.

## Historial breve

- 2026-09-26: Dashboard inicial (consumo por día/proyecto/modelo).
- 2026-09-27: + Coste/msg, gráfica 7d fija, compartimentado Consumo/Recursos/Tareas, calendario Pomodoro con detalle, columnas alineadas cross-table, sortable 3 estados, auto-refresh, movido a Panel Control, + Tool & cache y Git 7d.
