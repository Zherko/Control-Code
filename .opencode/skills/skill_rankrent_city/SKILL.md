---
name: skill_rankrent_city
description: Estudio Rank&Rent por ciudad — demanda, keywords, saturación y mercado con AI Overviews. Activa con /skill_rankrent_city "Ciudad"
metadata:
  version: "1.4"
  trigger: /skill_rankrent_city
  committee_review: 2026-09-21
  changelog: "1.4 añade auditoría SEO real (schema/https/PageSpeed/contenido) para saber si los puedes adelantar"
---

# Skill RankRent City — /skill_rankrent_city v1.4

Dices `Villajoyosa` y te devuelve **qué 3 webs montar primero**, con demanda, ticket €, saturación (AIO + Maps + SEO real) y si los puedes adelantar. <2min, 100% trazable.

> Cambios v1.4 21/09/2026: añade auditoría SEO real (schema/https/PageSpeed/contenido/DR) para ver si adelantas al top3. Cambios v1.3: integra Maps Places. v1.1: score normalizado.

## Trigger
```
# Modo A — ciudad sola → Top 3 nichos
/skill_rankrent_city "Villajoyosa"
/skill_rankrent_city "Valencia" --profundidad profunda
/skill_rankrent_city "Gijón" --nichos cerrajero,tejados,clima

# Modo B — negocio + ciudad → evalúa esa idea (nuevo)
/skill_rankrent_city "cerrajero Villajoyosa"
/skill_rankrent_city "clínica dental Valencia"
/skill_rankrent_city "reformas integrales Bilbao" --profundidad profunda
```

## Workflow — 4 fases

### FASE 1: Intake (15s) — detecta modo
- **Si input = solo ciudad** → Modo A (Top 3)
- **Si input = "negocio + ciudad"** → Modo B (evalúa idea). Extrae `negocio` y `ciudad` (ej: "clínica dental Valencia" → negocio=clínica dental, ciudad=Valencia). Si ambiguo → pregunta "¿negocio = X en ciudad Y?"
- Ciudad + provincia (para areaServed). Si no da ciudad → pregunta 1 vez, fallback ciudad mediana 80k + aviso
- Carga `config.yaml`: nichos y pesos. Cache hit 30d por `ciudad+negocio` → tag `[cache 12d]`

### FASE 2: 6 queries paralelas (livecrawl: preferred, timeout 20s, degradación) — ahora con Maps + SEO real
**Modo A (ciudad sola):**
```
Q1 demanda: "{ciudad} fontanero|cerrajero|tejados|desatascos volumen" + Trends
Q2 SERP: live SERP "{keyword} {ciudad}" → top 3 map pack + detecta AI Overview (+-15)
Q2b Maps: Google Places Nearby Search / Text Search "{nicho} {ciudad}" 20km → conteo competidores Maps + media reseñas/rating (fuente compartida con skill_rankrent_prospector)
Q2c SEO: webfetch top3 orgánico → auditoría rápida: schema LocalBusiness? https? PageSpeed? nº palabras? DR aproximado (Moz/Ahrefs free) → gap SEO
Q3 mercado: censo 20km (Habitissimo/Suizgo/Cylex) + densidad + si compran leads
Q4 ticket ES: Lead Smart $→€*0.55 + CPL local; si no → [Disputado]
```
**Modo B (negocio+ciudad):** sustituye Q1-Q2 por negocio específico:
```
Q1 demanda negocio: "{negocio} {ciudad} volumen + keywords long-tail + estacionalidad"
Q2 SERP negocio: live SERP "{negocio} {ciudad}" → top 5 orgánico + map pack + AIO + autoridad (reviews, DR)
Q2b Maps negocio: Google Places Text Search "{negocio} {ciudad}" 20km → conteo + media reseñas/rating + % sin web (misma fuente que prospector)
Q2c SEO negocio: webfetch top3 "{negocio} {ciudad}" → schema? https? PageSpeed? contenido? DR → ¿adelantable? (ej: top3 sin schema y con PageSpeed <60 = fácil)
Q3 mercado negocio: nº competidores negocio en 20km (Q2b) + ticket medio negocio + si pagan leads (Bark/Habitissimo para ese vertical)
Q4 ticket negocio: payout específico vertical (ej: dental €80-200, reformas €50-150) + CPL Google Ads vertical 2026
```
- Si GOOGLE_PLACES_KEY existe → Q2b usa Places API (estable, ~$0.04/nicho, cache 7d compartida con prospector en `.opencode/cache/rankrent/`). Si no → Q2b hace fallback a conteo estimado vía websearch + marca `[Maps-estimado]`.
- Q2c siempre intenta webfetch (coste 0€, timeout 8s por URL). Si falla 1 de 3 → marca `[SEO-parcial]`. Si ≥2 fallan → no bloquea, baja confianza.
- Si 1 query falla → no aborta, marca `[EV-fallido]` y sigue. Si ≥2 fallan → veredicto `Baja`.

### FASE 3: Score normalizado 0-100 (configurable)
```yaml
# config.yaml (no tocar SKILL.md para ajustar nichos/pesos)
nichos: [cerrajero_24h, impermeabilizacion_tejados, climatizacion, desatascos, fontaneria_urgencia]
pesos: {demanda: 0.30, ticket_eur: 0.35, saturacion: 0.35, aio_penalty: 0.15}
# + ajuste estacional: HVAC -30% nov-mar, tejados -20% jun-ago
```
- Normaliza cada variable 0-100 antes de ponderar (evita comparar volumen 10k vs ticket 40€ sin escala)
- `Oportunidad = Demanda*0.30 + Ticket€*0.35 - Saturación*0.35 - AIO*0.15`
- Saturación reproducible con Maps + SERP + SEO: 0=Top3 webs 2014 sin schema + <8 competidores Maps con <10 reseñas + PageSpeed <60 y sin contenidos, 50=mixto, 100=franquicias DR60+ con 100+ reviews + LSA + >25 competidores Maps con media >50 reseñas y webs con schema/DR alto. Usa Q2b (conteo Maps + media reseñas) + Q2c (gap SEO) + captura SERP + fecha. Si Q2b falla → usa heurística antigua y marca `[Maps-estimado]`. Si Q2c falla → marca `[SEO-parcial]` y no penaliza.
- **Adelantable (nuevo):** SÍ si Q2c muestra top3 sin schema LocalBusiness Y (PageSpeed <65 O <600 palabras O DR <15). NO si top3 con schema + 1200 palabras + DR 40+. Se muestra en output como `SEO: Adelantable / Medio / Duro` con evidencia `schema:NO, PS:52, palabras:340 [webfetch fecha]`.

### FASE 4: Síntesis — output obligatorio
**Modo A (ciudad):**
```markdown
## Estudio Rank&Rent: {Ciudad} — {fecha} [cache?]
> ⚠️ Informativo, no asesoramiento financiero.
### Top 3 webs para montar
| # | Nicho | Keyword | Vol | Ticket € [EV] | Saturación (+AIO) | SEO top3 | Oportunidad | Veredicto |
| 1 | Cerrajero 24h | cerrajero 24h {ciudad} | Alto [Trends] | €22 [Lead Smart $37.5→€22 ES, Disputado] | 25/100 | Adelantable (schema:NO, PS:48) | 78 | MONTAR |
### Gap SEO + Estructura web (12 págs) + Mercado + Fuentes + Reversión + Leads
```

**Modo B (negocio+ciudad) — evalúa idea:**
```markdown
## Evaluación Rank&Rent: {Negocio} en {Ciudad} — {fecha}
> ⚠️ Informativo. Score 0-100, veredicto MONTAR / TEST / EVITAR.

### Veredicto idea: **TEST 62/100** — Media (ejemplo)
| Dimensión | Score | Evidencia |
| Demanda | 70 | Vol Alto [Trends], 4.2k búsq/mes {negocio} {ciudad}, estacionalidad verano |
| Ticket € | 55 | €45 med [Habitissimo], Lead Smart ref $38→€22 Disputado |
| Saturación | 68 | Top3 DR 55 + 120 reviews + AIO presente → alta |
| Oportunidad | **62** | =Dem*0.30+Tick*0.35-Sat*0.35-AIO*0.15 |

### ¿Merece la pena vs alternativas en {Ciudad}?
Top 2 alternativas con mejor oportunidad: 1) Cerrajero 78, 2) Tejados 74 → tu idea rinde -16pts → considera pivot

### Estructura web específica para {negocio}
Home {negocio} {ciudad} + 5 services long-tail + 3 barrios + schema + GBP

### Fuentes [EV] + Criterios de reversión
Si LSA entra o AIO pasa a 2 resultados → saturación +30
```

## Reglas anti-alucinación (bloqueantes)
- Cero volúmenes inventados: `Alto/Medio/Bajo` si Keyword Planner <10, con `[Trends]`
- Cada cifra con `URL + fecha pub + fecha consulta + tipo + [EV-XXX]`; si falta → `[No verificado — fetch fallido]`
- Saturación y conteo con fuente Maps: cada Q2b con `n=XX, media reseñas YY, rating ZZ [EV-Places fecha]` o `[Maps-estimado]` si fallback
- Si ticket ES sin fuente local → marca `Disputado` y baja confianza a Media
- Cache TTL 30d por `ciudad+nichos` + TTL 7d para Q2b Places compartida con prospector en `.opencode/cache/rankrent/` para no repetir fetches

## Leads huérfanos — protocolo legal ES
No derives sin respuesta. Opciones: 1) tu buzón grabado (aviso), 2) tú como centralita 2-3 leads gratis a prospectos, 3) red pay-per-call ES solo si T&C lo permiten y con consentimiento. Reventa sin base = RGPD riesgo.

## Checklist entrega
- [ ] 6 queries intentadas (4 + Q2b Maps + Q2c SEO), log fallidos
- [ ] SERP captura + AIO detectado + Q2b conteo Maps (n + media reseñas) + Q2c auditoría SEO top3 (schema/PS/palabras/DR)
- [ ] Score 0-100 normalizado con saturación Maps-real + Adelantable (SEO gap)
- [ ] Ticket € con factor ES + Disputado si falta
- [ ] Disclaimer + reversión escrita
- [ ] Modo detectado (A Top3 vs B evalúa idea) explícito en título + fuentes Maps/SEO indicadas
