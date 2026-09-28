---
name: skill_control
description: Lanza el Panel Control dashboard local (genera y sirve en http://localhost:3000/dashboard.html - canonico para Google OAuth)
metadata:
  version: "1.1"
  trigger: /skill_control
---

# Skill Control — /skill_control

Lanza el Centro de Control local-first en `http://localhost:3000/dashboard.html` (**canónico**, autorizado en Google OAuth; `http://localhost:8099` redirige a `/dashboard.html` y también sirve).

## Qué hace
1. Regenera `dashboard.html` con `python scripts/gen-dashboard.py` (lee `~/.local/share/opencode/opencode.db` + `~/.config/opencode/opencode.json` + `git log` + Supadata `db27` peers)
2. Sirve `Panel Control` en `http://localhost:3000` con `python scripts/serve.py` (puerto **3000** canónico para GIS, estático + proxy `/v1/*` -> Supadata `https://pro-serv.tail9f39ff.ts.net` para CORS)
3. Abre el navegador automáticamente en `http://localhost:3000/dashboard.html`

Uso:
- `/skill_control` — regenera y lanza (si ya está en 3000, solo regenera)
- `/skill_control --regen` — solo regenera sin servir
- `/skill_control --open` — solo abre http://localhost:3000/dashboard.html

## Comandos

```powershell
# regenera
python scripts/gen-dashboard.py
# sirve (desde Panel Control) - con proxy CORS - CANONICO 3000
python scripts/serve.py
# abre
start http://localhost:3000/dashboard.html
```

El agente al recibir `/skill_control` debe ejecutar en orden:
1. `python scripts/gen-dashboard.py` en `C:\Proyectos\Skills\Panel Control`
2. Verificar puerto **3000** libre, lanzar `python scripts/serve.py` en background si no está (reemplaza http.server para CORS Supadata; `3000` es canónico, `8099` legado)
3. Responder con URL lista: `http://localhost:3000/dashboard.html` + `dashboard.html` regenerado OK
4. **Siempre usar el mismo localhost** (`3000`) — no crear puertos alternativos sin actualizar `GOOGLE_CLIENT_ID` orígenes
