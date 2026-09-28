---
name: skill_rankrent_city
description: Estudio Rank&Rent por ciudad — demanda, keywords, saturación y mercado. Activa con /skill_rankrent_city "Ciudad"
metadata:
  version: "1.0"
  trigger: /skill_rankrent_city
---

# Skill RankRent City — /skill_rankrent_city

Dices `Madrid` y te devuelve **qué 3 webs montar primero en esa ciudad**, con demanda, keywords, saturación y si merece la pena, en <2min.

## Trigger

```
/skill_rankrent_city "Gijón"
/skill_rankrent_city "Valencia" --profundidad profunda
```

## Workflow — 4 fases (ponytail: lo mínimo que responde)

### FASE 1: Intake
- Ciudad + provincia/CCAA (para áreaServed)
- Si no da ciudad → pregunta 1 vez, si dice "decide tú" → usa ciudad mediana 80k ejemplo

### FASE 2: 4 queries ortogonales (paralelo, livecrawl: preferred)
```
Q1 demanda: "fontanero OR cerrajero OR tejados OR desatascos {ciudad} volumen búsquedas 2026"
Q2 competencia: "site:google.es \"{ciudad}\" fontanero cerrajero — saturación SERP local"
Q3 mercado: "{ciudad} empresas fontanería cerrajería tejados censo competencia lead value"
Q4 validación: "{ciudad} precio lead pay per call 2026 AI Overviews local"
```
Añade 1 fetch a Lead Smart / 99calls si hay payout ZIP comparable.

### FASE 3: Score 0-10 por nicho (5 nichos fijos)
Nichos base: fontanería urgencia, cerrajero 24h, tejados/impermeabilización, desatascos/fosa, climatización/HVAC

Para cada nicho:
- **Demanda** = volumen relativo (Google Trends + keyword ideas)
- **Ticket** = $ Lead Smart median ($38-201) + CPL 99calls
- **Saturación** = ¿top 3 map pack son webs cutres 2018 sin schema vs franquicias fuertes?
- **Oportunidad = (Demanda*0.3 + Ticket*0.4 - Saturación*0.3)** → rank 1-5

### FASE 4: Síntesis — output obligatorio
```markdown
## Estudio Rank&Rent: {Ciudad} — {fecha}
### Top 3 webs para montar (orden oportunidad)
| # | Nicho | Keyword principal | Vol estimado | Lead value | Saturación | Oportunidad | Veredicto |
| 1 | Cerrajero 24h | cerrajero 24h Gijón | Alto | $37.5 med | Baja (webs 2014) | 8.2 | MONTAR |
### Estructura web recomendada (12 páginas)
- Home 1500w + Service 5×800w + Location 3×800w + schema LocalBusiness
### Mercado: ¿merece la pena?
- Nº empresas en 20km: X, ticket medio €Y, competencia: débil/fuerte, break-even: 4-7 leads/mes = €250 renta → 1 cliente
### Qué hacer con leads pre-alquiler (ver FAQ)
```

## Regla anti-alucinación
- Cero volúmenes inventados: si no hay Keyword Planner, usa "Alto/Medio/Bajo" + fuente Trends
- Cada dato lleva [EV-XXX] con URL + fecha consulta
- Si saturación incierta → marca "Disputado" y sugiere validar SERP manual

## Leads huérfanos — protocolo integrado
Si pregunta por leads sin inquilino, responde siempre:
1. Tracking a tu buzón grabado (probar valor)
2. Vender a red pay-per-call (Lead Smart $38-201/lead) mientras buscas inquilino fijo
3. No dejar sonar sin respuesta → penaliza NAP y reseñas
