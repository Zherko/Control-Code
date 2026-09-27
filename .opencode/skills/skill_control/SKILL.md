---
name: skill_control
description: Lanza el Panel Control dashboard local (genera y sirve en http://localhost:8099/dashboard.html)
metadata:
  version: "1.0"
  trigger: /skill_control
---

# Skill Control — /skill_control

Lanza el Centro de Control local-first en `http://localhost:8099/dashboard.html`.

## Qué hace
1. Regenera `dashboard.html` con `python scripts/gen-dashboard.py` (lee `~/.local/share/opencode/opencode.db` + `~/.config/opencode/opencode.json` + `git log`)
2. Sirve `Panel Control` en `http://localhost:8099` con `python -m http.server 8099`
3. Abre el navegador automáticamente

Uso:
- `/skill_control` — regenera y lanza (si ya está en 8099, solo regenera)
- `/skill_control --regen` — solo regenera sin servir
- `/skill_control --open` — solo abre http://localhost:8099/dashboard.html

## Comandos

```powershell
# regenera
python scripts/gen-dashboard.py
# sirve (desde Panel Control)
python -m http.server 8099
# abre
start http://localhost:8099/dashboard.html
```

El agente al recibir `/skill_control` debe ejecutar en orden:
1. `python scripts/gen-dashboard.py` en `C:\Proyectos\Skills\Panel Control`
2. Verificar puerto 8099 libre, lanzar `python -m http.server 8099` en background si no está
3. Responder con URL lista: `http://localhost:8099/dashboard.html` + `dashboard.html` regenerado OK
