---
name: skill_resumen
description: Use when user says /skill_resumen, resume lo anterior, or asks for a short summary of the last response in a few lines.
metadata:
  version: "1.0"
  trigger: /skill_resumen
---

# Skill Resumen — /skill_resumen

Resume la última respuesta del asistente en 3 o 4 líneas.

## Receta de salida

El output ES esto, en orden:

1. 3 o 4 líneas, una idea principal por línea.
2. Lenguaje simple y directo.
3. Solo ideas que aparecen en la última respuesta, sin añadir nada.

Prohibido: ejemplos nuevos, analogías ajenas, detalles que la respuesta no dio.
