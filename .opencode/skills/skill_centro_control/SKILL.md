---
name: skill_centro_control
description: Lanza el Panel Control dashboard local (alias de skill_control)
metadata:
  version: "1.0"
  trigger: /skill_centro_control
---

# Skill Control â€” /skill_centro_control

Lanza el Centro de Control local-first en `http://localhost:8099/dashboard.html`.

## QuÃ© hace
1. Regenera `dashboard.html` con `python scripts/gen-dashboard.py` (lee `~/.local/share/opencode/opencode.db` + `~/.config/opencode/opencode.json` + `git log`)
2. Sirve `Panel Control` en `http://localhost:8099` con `python -m http.server 8099`
3. Abre el navegador automÃ¡ticamente

Uso:
- `/skill_centro_control` â€” regenera y lanza (si ya estÃ¡ en 8099, solo regenera)
- `/skill_centro_control --regen` â€” solo regenera sin servir
- `/skill_centro_control --open` â€” solo abre http://localhost:8099/dashboard.html

## Comandos

```powershell
# regenera
python scripts/gen-dashboard.py
# sirve (desde Panel Control)
python -m http.server 8099
# abre
start http://localhost:8099/dashboard.html
```

El agente al recibir `/skill_centro_control` debe ejecutar en orden:
1. `python scripts/gen-dashboard.py` en `C:\Proyectos\Skills\Panel Control`
2. Verificar puerto 8099 libre, lanzar `python -m http.server 8099` en background si no estÃ¡
3. Responder con URL lista: `http://localhost:8099/dashboard.html` + `dashboard.html` regenerado OK

