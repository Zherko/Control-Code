# skill_social — Pestaña Social (Supadata db27 admin)

> Un botón **Conectar** y ya compartes. Pincha un peer para chatear. Todo en `admin` como pediste — `panel-control-social` `db27` (peers+messages). Compartimentado: borra DB + bloque `SOCIAL MODULE` para quitar.

## Qué comparte (al conectarte)

- Nombre único auto-asignado `anon-XXXX` (no se repite, si existe añade sufijo)
- Tok hoy / 30d, $/k churn, nº proyectos (todo local)

Usa tu key `admin` `sd_a0L7o...` directa (ya que todo es tuyo) embebida en el dashboard.

## Cómo conectar

1. Abre **Social → Conectar** (un solo botón).
2. Te asigna `anon-XXXX` (se guarda en `localStorage pc_social_name`). **Desconectar** pone `status=offline`.
3. JS hace `POST db27/peers` directo con admin key — también `python scripts/social_sync.py --connect --name MiNombre`.

## Chat

Pincha cualquier fila `Nombre` → modal **Chat con peer**. Escribe y **Enviar** guarda en `db27/messages` (`from_name`, `to_name`, `body`, `created_at`). Se filtra solo conversación entre tú y ese peer.

## Ver

- Dashboard → Social: tabla con tok hoy/30d, $/k churn, proyectos, online/offline. Pincha para chatear.
- Supadata: `panel-control-social` `db27` en https://pro-serv.tail9f39ff.ts.net (owner `admin`)

## Agente

Usuario dice "conéctame" → genera nombre, llama `social_sync.py --connect`, regenera, confirma.

## Quitar

Borra DB `panel-control-social`, `scripts/social_sync.py`, `skill_social/`, y bloque `SOCIAL MODULE` en `gen-dashboard.py` + `dashboard.html`.
