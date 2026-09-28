---
name: skill_centro_control
description: Lanza el Panel Control dashboard local (alias de skill_control - canonico 3000)
metadata:
  version: "1.1"
  trigger: /skill_centro_control
---

# Skill Control — /skill_centro_control (alias)

Alias de `/skill_control` — mismo comportamiento, mismo localhost canonico.

Lanza el Centro de Control local-first en `http://localhost:3000/dashboard.html` (**canonico**, `http://localhost:8099` redirige).

## Que hace
1. Regenera `dashboard.html` con `python scripts/gen-dashboard.py`
2. Sirve `Panel Control` en `http://localhost:3000` con `python scripts/serve.py` (proxy CORS Supadata)
3. Abre el navegador automaticamente en `http://localhost:3000/dashboard.html`

Uso:
- `/skill_centro_control` — regenera y lanza (si ya esta en 3000, solo regenera)
- `/skill_centro_control --regen` — solo regenera sin servir
- `/skill_centro_control --open` — solo abre http://localhost:3000/dashboard.html

## Comandos

```powershell
# regenera
python scripts/gen-dashboard.py
# sirve - CANONICO 3000
python scripts/serve.py
# abre
start http://localhost:3000/dashboard.html
```

El agente al recibir `/skill_centro_control` debe ejecutar en orden:
1. `python scripts/gen-dashboard.py` en `C:\Proyectos\Skills\Panel Control`
2. Verificar puerto **3000** libre, lanzar `python scripts/serve.py` en background si no esta
3. Responder con URL lista: `http://localhost:3000/dashboard.html` + `dashboard.html` regenerado OK
4. **Siempre el mismo localhost** (`3000`) — no usar puertos alternativos
