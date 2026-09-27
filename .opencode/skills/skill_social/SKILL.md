# skill_social — Pestaña Social (Supadata)

> Compartes consumo con otros conectados y ves su ranking. Compartimentado: borra `panel-control-social` DB + bloque `SOCIAL MODULE` en `gen-dashboard.py` y pestaña Social para quitar.

## Qué comparte (al conectarte)

- Nombre único (no repetible) — lo eliges, si existe te añade sufijo
- Tokens hoy / 30d, coste, $/k churn, nº proyectos (todo local, sin API)

## Cómo conectar (usuario o agente)

1. Abre **Social → Conectar** en el dashboard, escribe tu nombre (sugerido `anon-XXXX`) o deja el que te asigna.
2. Pulsa **Conectar y compartir** — guarda `pc_social_name` y `pc_social_connected` en `localStorage`.
3. Ejecuta (agente o tú): `python scripts/social_sync.py --connect`  (lee tu nombre de `localStorage` vía gen-dashboard o pásalo `--name MiNombre`)
   - Si ya estabas conectado, hace upsert en `panel-control-social/peers` (Supadata `db27`) con `onConflict: ["name"]`.
   - Usa la key de `~/.config/opencode/opencode.json` (`SUPADATA_API_KEY`), nunca se sube al HTML.
4. Regenera: `python scripts/gen-dashboard.py` — la pestaña Social ya muestra a todos los conectados (snapshot build-time + live fetch si pegas tu key).

## Desconectar

Pulsa **Desconectar** en Social o `python scripts/social_sync.py --disconnect --name MiNombre` (pone `status=offline`, no borra fila).

## Ver

- Dashboard → Social: tabla con nombre, tok hoy/30d, $/k churn, proyectos, estado
- Supadata: `panel-control-social/peers` en https://pro-serv.tail9f39ff.ts.net

## Agente

Cuando el usuario diga "conéctame al social", "compárteme", lee `pending` y usa este skill: genera nombre, llama a `social_sync.py --connect`, regenera dashboard y confirma.

## Quitar

Borra DB `panel-control-social` en Supadata, `scripts/social_sync.py`, `skill_social/`, y bloque `SOCIAL MODULE` en `gen-dashboard.py`.
