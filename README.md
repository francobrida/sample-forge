# sample-forge

Genera efectos de sonido, foley y voces habladas con la API de ElevenLabs y los convierte en una **librería de samples buscable**, lista para arrastrar a Ableton.

> **Sobre la IA:** el código lo escribió Claude Code (un asistente de programación con IA) bajo mi dirección. Yo definí el problema y el diseño, y pruebo y reviso el resultado. Aún no lo probé con la API real de ElevenLabs: los tests usan una API simulada.

Problema que resuelve: un productor pierde tiempo buscando foley y one-shots, y las herramientas de generación entregan un mp3 suelto, sin saber qué nota es, cuánto dura ni cuánto costó.

## Qué hace

- **Genera** SFX/foley (`sound-generation`) y voz hablada (`text-to-speech`), con varias tomas por prompt.
- **Analiza** cada toma: recorta silencios, normaliza a −1 dBFS, mide duración, pico y RMS, y **detecta la nota** (útil para meter un "ahh" hablado en tonalidad).
- **Guarda** en SQLite con búsqueda de texto completo: `search riser --note A --max-dur 3`.
- **Exporta** WAV de 24 bit con nombres como `Riser_A4_2.4s_ab12.wav`. Ableton no lee los tags de los WAV, así que la información va en el nombre.
- **Controla el gasto**: caché por hash (el mismo pedido no vuelve a llamar a la API), estimación antes de generar, tope mensual de créditos y reintentos con backoff ante `429`.
- **API + web** (FastAPI, una sola página HTML) con cola de jobs y 2 workers.

## Uso

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set ELEVEN_API_KEY=tu_clave              # plan gratis alcanza
```

```bash
python -m sample_forge gen sfx "heavy wooden door slam, big hall" -d 2 -n 3
python -m sample_forge gen vox "yeah!" --dry-run          # solo estima el costo
python -m sample_forge search door --max-dur 3
python -m sample_forge export "C:\Samples\forge" riser --note A
python -m sample_forge serve                              # web en http://127.0.0.1:8000
```

Variables opcionales: `SF_MONTHLY_CREDITS` (tope, 8000 por defecto), `SF_DATA` (carpeta de datos), `SF_VOICE` (voice id por defecto), `SF_API_KEY` (si se define, la API exige el header `x-api-key`).

## Diseño

```
cli / web ──► api.py (jobs, auth) ──► core.Forge ──► eleven.py   (HTTP + reintentos)
                                          │       └─► analyze.py (decode, trim, pitch)
                                          └────────► db.py       (SQLite + FTS5, ledger de créditos)
```

Decisiones:

- **Caché por hash** de `(tipo, prompt, parámetros, nº de toma)`. Las tomas llevan índice, así que `-n 4` da cuatro distintas y repetir el comando no gasta nada.
- **Sin SDK ni librosa**: `httpx` y `numpy`. La detección de tono es autocorrelación con interpolación parabólica y corrección de errores de octava.
- **Mp3 → WAV local**: el WAV/PCM de 44,1 kHz de ElevenLabs es de plan Pro, el mp3 funciona en el gratis.
- **La API valida todo en el borde** (pydantic), los ids se comprueban con regex antes de tocar el disco y la búsqueda solo admite términos `\w`, así que no se cuela sintaxis FTS.

## Tests

```bash
.venv\Scripts\python -m pytest
```

El análisis se prueba con tonos sintéticos de frecuencia conocida (un La 440 tiene que dar `A4`), y ElevenLabs va simulado: los tests no gastan créditos.

## Límites

- Los costos en créditos (`core.py`) son **estimaciones**; la fuente de verdad es tu panel de ElevenLabs.
- La detección de nota funciona con sonidos tonales; el ruido y la percusión devuelven `—`.
- Los jobs viven en memoria: se pierden al reiniciar el servidor.
- Sin autenticación por usuario: pensado para uso local (escucha solo en `127.0.0.1`).
- El plan gratuito de ElevenLabs exige atribución y es no comercial.
