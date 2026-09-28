---
name: skill_rankrent_prospector
description: Prospección Rank&Rent — dado negocio+ciudad devuelve contactos validados, mensaje y link directo a WhatsApp Web. Activa con /skill_rankrent_prospector "negocio ciudad"
metadata:
  version: "1.2"
  trigger: /skill_rankrent_prospector
  committee_review: 2026-09-21
  changelog: "1.2 añade auditoría SEO por prospecto (schema/https/palabras) para saber si lo adelantas + fijos también generan wa.me"
---

# Skill RankRent Prospector — /skill_rankrent_prospector v1.2

Dices `cerrajero Benidorm` y te devuelve **15-20 profesionales con teléfono validado (móvil+fijo) + auditoría SEO + mensaje + link `wa.me` listo**. Human-in-the-loop, sin envío automático.

> Veredicto comité 21/09/2026: Places API o proxy pagado por defecto, scoring 0-100, solo `wa.me` manual, libphonenumber obligatorio, store efímero.

## Trigger
```
/skill_rankrent_prospector "cerrajero Benidorm"
/skill_rankrent_prospector "catering Benidorm"
/skill_rankrent_prospector "cerrajero Villajoyosa" --limit 10
```

## Workflow — 4 fases

### FASE 1: Intake (10s)
- Extrae `negocio` y `ciudad` del input. Si falta uno → pregunta 1 vez.
- Normaliza: `negocio_slug`, `ciudad_slug`, `hash = negocio+ciudad` para cache 7d.
- Carga `config.yaml` pesos scoring si existe.

### FASE 2: Búsqueda (livecrawl: preferred, 20s timeout)
Ejecuta 2 queries paralelas (no scraping crudo Google Maps en MVP):
```
Q1: websearch "{negocio} {ciudad} teléfono" + "{negocio} {ciudad} contacto" (numResults 10)
Q2: websearch "{negocio} {ciudad} site:google.com OR site:paginasamarillas.es" o Places API si hay GOOGLE_PLACES_KEY
```
- Si GOOGLE_PLACES_KEY existe → usa `Google Places Text Search + Place Details` (estable, ~$0.05/lead). Si no → usa websearch + webfetch de fichas.
- Extrae por cada prospect: `nombre, telefono_raw, web, rating, reviews, fuente_url`.
- Si Q falla → marca `[EV-fallido]` y sigue. Si 0 resultados → veredicto `Sin datos`.

### FASE 3: Validación + Scoring 0-100 + Auditoría SEO (¿adelantable?)
1. **Normaliza teléfono** con libphonenumber-js: `parsePhoneNumber(telefono_raw, 'ES')`. Guarda MOBILE (6xx/7xx) como `[MOBILE-validado]` y FIJO 96x como `[FIJO-validado]` — ambos generan wa.me (fijo verifica por voz). Solo descarta si `!isValid()`.
2. **Deduplica** por E.164.
3. **Auditoría SEO rápida por prospecto** (webfetch si tiene web, timeout 8s, coste 0€):
   - `https?` (candado), `schema LocalBusiness?` (busca `"@type":"LocalBusiness"` o `schema.org`), `PageSpeed?` (opcional), `nº palabras` aproximado, `DR` estimado si hay.
   - Marca `web_pobre = !https || !schema || palabras <400 || PageSpeed <60`
4. **Scoring oportunidad Rank&Rent** (función pura):
```
sin_web: +40
web_pobre (sin https / sin schema / <400 palabras / PS<60): +30
<20 reseñas: +15
rating 3.8-4.4: +10
top3 saturado (franquicia +100 reseñas): -20
SEO adelantable (prospecto sin schema y con PageSpeed <65): +10 extra
Oportunidad = suma capped 0-100
```
- Ordena por oportunidad DESC. Top 5 = `ALTA` para contactar primero. Muestra en tabla `SEO: sin web / pobre (schema:NO, PS:52) / ok`.

### FASE 4: Mensaje + wa.me (funciones puras)
**MessageBuilder (plantilla por defecto Javier — sin nombre, sin critique web):**
```
Hola, soy Javier de Potencia tu proyecto. Estamos recibiendo consultas de {negocio} en {ciudad} y estamos buscando un profesional de la zona para derivárselas. ¿Te interesaría que te lleguen a ti sin compromiso? Si te encaja responde SI y te apunto, si no responde NO y no te molesto más. Gracias!
```
- Variables: `{negocio}`, `{ciudad}`. No usa `{nombre}` ni menciona web desactualizada.
- `encodeURIComponent(mensaje)` obligatorio. Editable 1-click en output.
- Configurable en `.opencode/skills/skill_rankrent_prospector/config.yaml` → `sender: "Javier de Potencia tu proyecto"`

**LinkGenerator:**
```
waLink = `https://wa.me/${e164_sin_plus}?text=${encodeURIComponent(mensaje)}`
webLink = `https://web.whatsapp.com/send?phone=${e164_sin_plus}&text=...` (fallback)
```

**Output obligatorio:**
```markdown
## Prospección Rank&Rent: {negocio} en {ciudad} — {fecha} [fuente: websearch/places]
> ⚠️ Generador de borradores. No envía automático. Confirma base legítima LSSI art.21 antes de enviar. Solo 1-1 human-in-the-loop.

| # | Nombre | Tel (E164) | Web | Oportunidad | Mensaje | WhatsApp |
|---|---|---|---|---|---|---|
| 1 | Cerrajeros Benidorm 24h | +34612345678 | — | 85 ALTA | Hola Cerrajeros... | [Abrir wa.me](https://wa.me/34612345678?text=...) [Copiar] |

### Mensaje recomendado (editable)
> Hola {nombre}, soy...

### CSV
nombre,telefono,e164,oportunidad,wa_link,fuente

### Reglas + Reversión
- Móviles y fijos validados (fijo también con WhatsApp por voz). Solo descarta inválidos.
- SEO: si `web_pobre` → oportunidad +30 y marca `Adelantable`. Es tu argumento de venta: "sin web optimizada = me adelantas fácil".
- Si >30% inválidos → nicho poco whatsapp-able, usa email fallback.
- Si reporte spam >0.5% → pausa y revisa plantilla.
```

## Reglas anti-alucinación (bloqueantes)
- Cero teléfonos inventados: cada teléfono con `fuente_url + fecha consulta`. Si no verificado → `[No verificado]`.
- Marca `[MOBILE-validado]` solo si libphonenumber `isValid && MOBILE`.
- Nunca envíes automático. Skill solo genera links.
- Cache 7d por `hash(negocio+ciudad)` en `.opencode/cache/rankrent/` compartida con `skill_rankrent_city` (Q2b). Si una skill ya consultó Maps, la otra reutiliza.
- Disclaimer LSSI/RGPD siempre.

## Checklist entrega
- [ ] 2 queries intentadas
- [ ] Teléfonos validados libphonenumber (MOBILE+FIJO), auditoría SEO por prospecto (schema/https/palabras)
- [ ] Scoring 0-100 con gap SEO aplicado
- [ ] Mensaje + wa.me por cada teléfono válido (encode correcto)
- [ ] Tabla + CSV + fuentes + disclaimer + columna SEO

## FASE 5: Si da OK — Derivación automática de leads (post-consentimiento)
Cuando prospecto responde `SI`, se activa tracking. Objetivo: derivar con mínima intervención y que ambos sepáis que es lead tuyo.

**Arquitectura mínima (ponytail):**
```
[Web Rank&Rent] 
  ├─ (A) Llamada → Nº virtual Zadarma/DIDWW (ej: 865600123 Benidorm) con whisper + desvío
  └─ (B) Formulario → Webhook n8n/Make → Google Sheet + WhatsApp/Email al profesional + a ti
```

**A) Llamadas (más valor en cerrajero):**
- Compra 1 nº fijo por ciudad (2€/mes Zadarma). Configura: `Llamada entrante → whisper "Lead de Potencia tu proyecto para cerrajero Benidorm" → desvío al móvil del profesional OK`.
- El profesional oye antes de descolgar que es tuyo. Tú ves CDR en panel + webhook a Sheet: `fecha, origen, duración, grabación`.
- Si deja de pagar → cambias desvío en 2 clicks. Cero código en web (solo cambias el `tel:`).
- Log automático: Zadarma → webhook → fila en `leads_{ciudad}.csv` / Google Sheet.

**B) Formularios/WhatsApp (más automático que llamada):**
- `Fluent Forms / CF7 / Elementor Form` → webhook `https://n8n.tu-dominio/webhook/lead-{negocio}-{ciudad}`
- n8n: `recibe {nombre, tel, mensaje, url_origen} → append Google Sheet "Leads Benidorm" → envía WhatsApp Cloud API/Telegram/Email al profesional ("Nuevo lead derivado por Potencia tu proyecto: Juan 612... quiere cerrajero urgente en Rincón de Loix") → envía copia a ti → responde al lead "Gracias, un profesional de la zona te contactará en <10min"`.
- El profesional sabe que es tuyo por el prefijo. Tú sabes todo por el Sheet. Sin intervención manual.
- Coste: n8n self-hosted gratis, Sheet gratis, WhatsApp Cloud 0€ hasta 1000 conv/mes.

**C) Identificación para ambos:**
- Prefijo automático en cada lead: `[Potencia tu proyecto - Cerrajero Benidorm]`
- Dashboard mínimo: Google Sheet compartido (solo lectura) o Metabase. 1 pestaña por ciudad.

**Regla:** Solo derivar a `estado=AUTORIZADO` en `prospectos.csv`. Si estado != SI → lead va a tu buzón, no al profesional.

## Leads huérfanos — protocolo legal ES
No derives leads sin SI. Opciones: 1) tu buzón, 2) tú como centralita 2-3 leads gratis a prospectos validados, 3) pay-per-call solo con consentimiento.
