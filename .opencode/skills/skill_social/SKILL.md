# skill_social — Pestaña Social (Supadata db28)

> Un botón **Conectar** y ya compartes. Pincha un peer para chatear. Compartimentado: borra `panel-social-v2` DB + bloque `SOCIAL MODULE` en `gen-dashboard.py` y pestaña Social para quitar.

## Qué comparte (al conectarte)

- Nombre único auto-asignado `anon-XXXX` (no se repite, si existe añade sufijo)
- Tok hoy / 30d, $/k churn, nº proyectos (todo local)

No pide `x-api-key` — usa la key pública limitada `sd_qKMPbKz3p36CZpBoVO-sOOheH0WdyzCq` (solo `db28` peers+messages, 1GB), embebida en el dashboard. No expone tu admin key.

## Cómo conectar

1. Abre **Social → Conectar** (un solo botón, sin inputs).
2. Te asigna `anon-XXXX` (se guarda en `localStorage pc_social_name`). Pulsa **Desconectar** para dejar de compartir (pone `status=offline`).
3. El JS hace `POST db28/peers` directo con la key pública — también `python scripts/social_sync.py --connect --name MiNombre` hace lo mismo server-side y regenera.

## Chat

Pincha cualquier fila `Nombre` en la tabla Social → abre modal **Chat con peer**. Escribe y **Enviar** guarda en `db28/messages` (`from_name`, `to_name`, `body`, `created_at`). Se filtra solo conversación entre tú y ese peer.

## Ver

- Dashboard → Social: tabla con tok hoy/30d, $/k churn, proyectos, online/offline. Pincha para chatear.
- Supadata: `panel-social-v2` `db28` en https://pro-serv.tail9f39ff.ts.net (owner `social`)

## Agente

Usuario dice "conéctame", "ponme en social" → genera nombre, llama `social_sync.py --connect`, regenera `gen-dashboard.py`, confirma.

## Quitar

Borra DB `panel-social-v2` (o `panel-control-social`), `scripts/social_sync.py`, `skill_social/`, y bloque `SOCIAL MODULE` en `gen-dashboard.py` + `dashboard.html`.
