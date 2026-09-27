# skill_pending — Cuaderno de pendientes para agentes

> Cuaderno compartido donde agentes apuntan tareas pendientes por proyecto. Compartimentado: si no gusta, borra `.opencode/pending_tasks.json` + este skill + bloque `PENDING MODULE` en `gen-dashboard.py` y `dashboard.html`.

## Cuándo usar

- El usuario dice "apúntalo en pendientes", "anótalo", "deja pendiente Panel Control::2026-09-27:: asunto".
- El agente detecta algo que no puede resolver ahora (deuda, bloqueo, TODO).

## Formato obligatorio

**Título:** `Nombre proyecto::fecha::asunto`

- `Nombre proyecto`: carpeta corta (`Panel Control`, `Enjambre`, etc.)
- `fecha`: `YYYY-MM-DD` (cuándo se apunta)
- `asunto`: 1 línea, máx 80 chars

**Descripción:** 1-4 líneas con el detalle de lo pendiente. Sin repetir el título.

## Dónde se guarda

`.opencode/pending_tasks.json` — array JSON. Cada entrada:

```json
{"project":"Panel Control","date":"2026-09-27","subject":"Revisar churn 90d","desc":"El total_churn_30 no cuadra con git log desde 90d, revisar rango","status":"open","created":"2026-09-27T21:30:00"}
```

## Cómo apuntar (agente)

1. Lee `.opencode/pending_tasks.json` (si no existe, crea `[]`).
2. Haz `append` con `project/date/subject/desc/status="open"/created=now ISO`.
3. Escribe el fichero. No borres otras entradas.
4. Ejecuta `python scripts/gen-dashboard.py` para que aparezca en Tareas → Pendientes.
5. Confirma al usuario: `Apuntado Panel Control::2026-09-27:: asunto`.

## Cómo cerrar

Cuando se resuelva, pon `status="done"` (no borres la fila, queda histórica).

## Ver

- Dashboard: pestaña **Tareas → Pendientes** (lee `pending_tasks.json` en build-time).
- Fichero: `.opencode/pending_tasks.json` directamente.

## Ejemplo

Usuario: "apunta que hay que blindar el fetch de softRefresh"

Agente añade:
`Panel Control::2026-09-27:: blindar fetch softRefresh` → desc: `softRefresh parsea D/EVO con regex frágil, añadir try/catch por clave`
