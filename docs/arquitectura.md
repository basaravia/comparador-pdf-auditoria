# Comparador de PDFs para Papeles de Trabajo de Auditoría
## Arquitectura y metodología de implementación (Fase 1: DMR local · Fase 2: Azure AI Foundry)

Documento de diseño para ejecutar con Claude Code. Contiene decisiones tomadas y justificadas,
contratos de datos, y paquetes de trabajo con criterios de aceptación.

---

## 0. Resumen de decisiones

| Decisión | Elección | Por qué |
|---|---|---|
| Lenguaje backend | **Python 3.12 + FastAPI** | PyMuPDF hace extracción de bbox + render + anotación en una sola librería; openpyxl para plantillas; ecosistema de embeddings. Node exigiría 3 librerías separadas y perdería el tooling de ML. |
| Frontend | **React + TypeScript + Vite** | PDF.js necesita control fino del canvas y overlays absolutos. |
| ¿Streamlit? | **No** | Ya se conoce su problema de desincronización de estado al refrescar, y no permite el visor con overlays que exige este caso. |
| Cálculo del diff | **Solo en backend** | El navegador únicamente dibuja lo que el backend calculó. Garantiza que el resaltado visual y la tabla nunca discrepen. |
| Ejecución | **Job persistido con checkpoints** | Comparaciones largas deben sobrevivir a un refresco o cambio de pestaña. |
| Capa de modelo | **Un solo `ModelGateway` con providers intercambiables** | Fase 1 → Fase 2 es cambio de configuración, no reescritura. DMR y Foundry hablan la misma API OpenAI. |
| Exportación a plantilla | **Plantillas registradas con contrato de anclas** (ver §7) | La opción de "que el auditor pegue" rompe la trazabilidad; la de "subir cualquier xlsx" es frágil. |
| Naturaleza del producto | **El diff léxico localiza; el análisis semántico es el producto** (ver §4) | La salida alimenta decisiones y levantamiento de riesgos. Un cambio de una palabra o una coma puede pesar más que una reescritura completa. |
| Prioridad de la tabla | **Por cuadrante léxico×semántico, no por volumen de cambio** | El cambio crítico suele ser el más pequeño. |

---

## 1. Arquitectura de componentes

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (React + TS)                                       │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ Visor A | B      │  │ Grilla de revisión               │ │
│  │ PDF.js + overlay │◄─┤ TanStack Table                   │ │
│  │ de bboxes        │  │ estado · comentario · corrección │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
│           ▲ scroll sincronizado · click fila → salta a bbox  │
└───────────┼──────────────────────────────────────────────────┘
            │ REST + SSE (progreso)
┌───────────▼──────────────────────────────────────────────────┐
│  Backend (FastAPI)                                            │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Pipeline de comparación (worker, con checkpoints)       │ │
│  │                                                          │ │
│  │  L0 estructural → L1 alineación → L2 léxico/geométrico   │ │
│  │       → L3 visual (píxel) → L4 agrupación en ChangeUnits │ │
│  │       → L5 análisis con modelo                           │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐ │
│  │ ModelGateway │ │ Exportadores │ │ Repositorio + audit   │ │
│  │ DMR │ Foundry│ │ xlsx│plantilla│ │ log append-only       │ │
│  └──────────────┘ └──────────────┘ └───────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
```

**Almacenamiento**
- Fase 1: SQLite + archivos en disco. SQLAlchemy desde el día uno para que Fase 2 sea migración, no reescritura.
- Fase 2: PostgreSQL + Azure Blob Storage.

---

## 2. Contratos (construir PRIMERO)

Estos tres artefactos se definen y congelan antes de escribir lógica. Son el ancla que evita
que Claude Code derive entre sesiones.

### 2.1 `ChangeUnit` — la unidad de todo el sistema

Una fila de la tabla = un `ChangeUnit`. Todo el pipeline produce o enriquece esto.

```jsonc
{
  "id": "cu_0031",
  "run_id": "run_a91f",

  // --- Localización ---
  "kind": "replace",            // insert | delete | replace | format | visual | move
  "page_a": 12, "page_b": 12,   // 1-indexado; null si no existe en ese lado
  "bbox_a": [[72.0, 310.5, 468.2, 322.1]],   // lista: un cambio puede abarcar varias líneas
  "bbox_b": [[72.0, 310.5, 481.7, 334.8]],
  "page_size_a": [595.3, 841.9], // para escalar en el frontend según el zoom
  "page_size_b": [595.3, 841.9],
  "section_path": "Título II > Capítulo 3 > Art. 35",
  "anchor_confidence": 0.94,     // qué tan seguro es el emparejamiento A↔B

  // --- Contenido ---
  "text_a": "el plazo será de treinta (30) días",
  "text_b": "el plazo será de quince (15) días hábiles",
  "context_a": "…párrafo completo con el fragmento marcado con «del»…",
  "context_b": "…párrafo completo con el fragmento marcado con «ins»…",

  // --- Señales calculadas (sin modelo generativo) ---
  "signals": {
    "delta_lexico": 0.18,         // distancia de edición normalizada
    "delta_semantico": 0.71,      // 1 - similitud coseno de embeddings
    "cuadrante": "critico_oculto",// trivial | parafrasis | critico_oculto | reescritura
    "lexico_critico": ["temporal", "umbral"],   // clases tocadas (§4.3)
    "elevacion_deterministica": true,
    "clase_puntuacion": null      // relativa_especificativa | enumeracion | division_oracion | …
  },

  // --- Análisis del modelo ---
  "analysis": {
    "status": "ok",              // ok | failed | skipped | stale
    "que_cambio": "Reducción del plazo de 30 a 15 días, ahora hábiles.",
    "implicacion": "Endurece el requisito operativo…",
    "direccion": "restrictivo",  // restrictivo | permisivo | equivalente | divergente
    "naturaleza": "plazo",       // obligacion|plazo|umbral|alcance|procedimiento|
                                 // definicion|referencia|sancion
    "efecto_esperado": "El manual debe ajustar el plazo del control C-14…",
    "riesgo_si_no_se_atiende": "Incumplimiento del Art. 35 en la próxima supervisión.",
    "evidencia": {               // grounding: spans literales, verificados (§4.7)
      "span_a": "treinta (30) días",
      "span_b": "quince (15) días hábiles"
    },
    "severidad": "alta",         // alta | media | baja | nula
    "requiere_criterio_humano": false,
    "motivo_abstencion": null,
    "confianza": 0.86,
    "provenance": {
      "provider": "dmr", "model": "qwen3-vl:8b",
      "prompt_version": "analisis_v3", "temperature": 0.0,
      "used_vision": false, "input_hash": "sha256:…",
      "timestamp": "2026-08-14T15:02:11Z", "latency_ms": 2840
    }
  },

  // --- Revisión humana ---
  "review": {
    "estado": "pendiente",       // pendiente | aceptado | corregido | descartado_fp
    "comentario": null,
    "interpretacion_corregida": null,
    "revisor": null, "revisado_en": null
  },

  // --- Salida final al papel de trabajo ---
  "calificacion_analisis": null  // generada por el modelo DESPUÉS de la revisión (§6)
}
```

**Convención de coordenadas — fijar y no negociar:**
puntos PDF, **origen arriba-izquierda**, relativo a la página, página 1-indexada.
PyMuPDF ya entrega así; PDF.js usa la misma orientación en su viewport. Documentarlo en
`CLAUDE.md` porque es el error que cuesta dos días si queda implícito.

### 2.2 `ModelGateway` — la interfaz que hace posible las dos fases

```python
class ModelGateway(Protocol):
    async def chat(self, messages, *, role: str, schema: dict | None = None) -> Response: ...
    async def chat_vision(self, messages, images: list[bytes], *, role: str) -> Response: ...
    async def embed(self, texts: list[str], *, role: str) -> list[list[float]]: ...
```

Configuración por **roles lógicos**, no por nombres de modelo:

```yaml
# models.yaml — Fase 1
provider: dmr
base_url: http://localhost:12434/engines/llama.cpp/v1
roles:
  analista_texto:   { model: "ai/gemma3:12B-Q4_K_M" }
  analista_vision:  { model: "ai/qwen3-vl:8B" }
  embedder:         { model: "ai/embeddinggemma" }
concurrency: 4
```

```yaml
# models.yaml — Fase 2
provider: azure_foundry
base_url: https://<recurso>.services.ai.azure.com/openai/v1
auth: entra_id            # DefaultAzureCredential; nunca api_key en producción
roles:
  analista_texto:   { deployment: "gpt-5-mini-prod" }   # nombre de DEPLOYMENT, no de modelo
  analista_vision:  { deployment: "gpt-5-vision-prod" }
  embedder:         { deployment: "text-embedding-3-large" }
concurrency: 8
rate_limit: { tpm: 200000, backoff: exponential }
```

**Regla dura:** ninguna parte del pipeline importa `openai` ni `httpx` directamente.
Todo pasa por el gateway. Sin esto, la Fase 2 se convierte en una cacería de llamadas sueltas.

Un tercer provider `FakeProvider` (respuestas fijas) permite que toda la suite de tests corra
sin GPU ni red.

### 2.3 OpenAPI del backend

Generar `openapi.json` desde FastAPI y derivar los tipos TS del frontend
(`openapi-typescript`). Un solo origen de verdad para el contrato HTTP.

---

## 3. Motor de diff — cinco capas

El problema real no es detectar diferencias: es **no ahogar al auditor en falsos positivos**.
Agregar una frase al inicio corre todo el documento hacia abajo; un diff palabra-a-palabra
ingenuo marca el resto del documento entero como modificado. Las capas L1 y L4 existen
específicamente para eso.

### L0 — Estructural (rápido, corta temprano)
Hash SHA-256, número de páginas, metadatos, fuentes embebidas. Si son idénticos, termina.

### L1 — Alineación por anclas *(la capa crítica)*
1. Extraer bloques con `page.get_text("dict")` → bloques/líneas/spans con bbox.
2. Calcular **dos hashes por bloque**:
   - `hash_laxo` — normaliza espacios, guiones de corte de línea, ligaduras, guiones suaves,
     comillas tipográficas, mayúsculas **y puntuación**. Sirve solo para *alinear*.
   - `hash_estricto` — normaliza únicamente artefactos de codificación (ligaduras, guiones
     suaves, espacios duros). **Conserva toda la puntuación, tildes y capitalización.**
3. Encontrar la subsecuencia común más larga de bloques con `hash_laxo` idéntico → **anclas**.
4. **Reverificar cada ancla con `hash_estricto`.** Si difieren, el bloque *no* es idéntico:
   se emite un `ChangeUnit` de clase `puntuacion` / `tipografico` que entra al análisis
   semántico como cualquier otro cambio. Sigue sirviendo como ancla geométrica.
5. Diffear **solo dentro de los huecos entre anclas**.

> ⚠️ **Este paso 4 no es opcional.** Sin él, la normalización que hace posible la alineación
> también borra los cambios de puntuación — que en texto normativo cambian el sentido. Un
> ancla es un punto de referencia posicional, nunca una afirmación de que el contenido es igual.

Efecto: un documento reflowado con 3 cambios reales produce 3 huecos, no 400 diferencias.

Para huecos donde los bloques no calzan exactamente, emparejar por similitud coseno
(embeddings del rol `embedder`) con umbral, y marcar `anchor_confidence`.

### L2 — Léxico y geométrico
Dentro de cada hueco: `page.get_text("words", sort=True)` → lista de
`(x0,y0,x1,y1,palabra,…)`. `difflib.SequenceMatcher.get_opcodes()` sobre el stream de palabras.
Cada opcode `replace|delete|insert` se mapea de vuelta a los bbox de sus índices.

Adicionalmente comparar los `spans` emparejados (fuente, tamaño, flags de negrita/cursiva)
para detectar `kind: "format"` — texto igual, presentación distinta.

### L3 — Visual (píxel)
`page.get_pixmap(dpi=150)` de ambos lados → diferencia de imágenes → **componentes conexos**
sobre la máscara de diferencia (no la máscara cruda) para obtener regiones rectangulares.
Descartar regiones que ya estén cubiertas por un cambio de L2. Lo que sobrevive es cambio
visual puro: tablas redibujadas, logos, firmas, gráficos, sellos.

> Normalizar tamaño de página antes de comparar. Si A es A4 y B es Carta, escalar o marcar
> el run como "geometría incompatible" en vez de producir basura.

### L4 — Agrupación en `ChangeUnit`
Opcodes consecutivos dentro del mismo bloque y a menos de N palabras de distancia colapsan en
una sola unidad. Aquí es donde 400 diferencias crudas se vuelven ~30 filas revisables.

Asignar `section_path`: construir el árbol de encabezados del documento (outline del PDF si
existe; si no, heurística de tamaño/peso de fuente, con el nodo VLM de inferencia de estructura
como respaldo) con rangos de página+Y, y buscar el nodo más interno que contiene el bbox.

Clasificar `kind: "move"` cuando un bloque desaparece en A y aparece idéntico en otra posición
de B. Estos se ocultan por defecto en la UI: son ruido de renumeración, no cambios.

### L5 — Análisis con modelo
Ver §4.

---

## 4. Análisis semántico y evaluación de riesgo

> Esta sección parte de una premisa que condiciona todo lo demás: **la salida de este sistema
> se usa para tomar decisiones y levantar riesgos.** Eso descarta tratar el cambio semántico
> como un enriquecimiento opcional sobre el diff léxico. Es el producto; el diff léxico es solo
> el mecanismo de localización.

### 4.1 Los dos ejes son independientes

La clasificación ingenua ordena los cambios por "cuánto texto cambió". Eso es exactamente lo
que falla en texto normativo, porque magnitud léxica y magnitud semántica son **ortogonales**:

|  | **Léxico bajo** | **Léxico alto** |
|---|---|---|
| **Semántico bajo** | Tipográfico — ruido | **Paráfrasis** — ruido voluminoso que entierra la señal |
| **Semántico alto** | ⚠️ **Cambio crítico oculto** — máxima prioridad | Reescritura sustantiva — evidente, fácil de detectar |

Las dos diagonales son las peligrosas y por razones opuestas:

- **Léxico bajo + semántico alto** es el que hunde el proyecto si no se detecta.
  `"treinta (30) días"` → `"treinta (30) días hábiles"`: una palabra, ~50% más de plazo real.
  `"deberá"` → `"podrá"`: una palabra, obligación convertida en facultad.
  `"y"` → `"o"`: una letra, requisitos acumulativos convertidos en alternativos.
- **Léxico alto + semántico bajo** es la reescritura editorial que no cambia nada. No es
  peligrosa por sí misma: es peligrosa porque genera cien filas que agotan al auditor y hacen
  que la fila crítica pase de largo.

El `ChangeUnit` reporta **ambos ejes por separado** (`delta_lexico`, `delta_semantico`) y el
cuadrante resultante. Ordenar la tabla por cuadrante, no por cantidad de texto cambiado.

### 4.2 Dirección del cambio — lo que una evaluación de riesgo realmente necesita

Saber *que* algo cambió no basta para levantar un riesgo. Hace falta saber **hacia dónde**.
Evaluación de implicación bidireccional (NLI) entre el fragmento A y el B:

| A ⊨ B | B ⊨ A | Dirección | Lectura para el auditor |
|---|---|---|---|
| ✓ | ✓ | `equivalente` | Paráfrasis. Se despriorizacon evidencia, no por descarte ciego. |
| ✓ | ✗ | `permisivo` | La norma **se relajó**. El manual podría haber quedado sobre-restrictivo. |
| ✗ | ✓ | `restrictivo` | La norma **se endureció**. Riesgo directo de brecha de cumplimiento. |
| ✗ | ✗ | `divergente` | Cambio de alcance. Requiere criterio humano casi siempre. |

Implementación: modelo NLI multilingüe (mDeBERTa / XLM-R fine-tuneado en XNLI) como señal
barata y determinista, **o** el LLM con salida estructurada pidiendo explícitamente ambas
direcciones. En Fase 1 conviene el LLM (una llamada menos que mantener); en Fase 2 vale medir
si el NLI dedicado tiene mejor recall a menor costo.

`direccion` se mapea directamente sobre la **valoración en doble vía** del Comparador Normativo:
`restrictivo` alimenta la vía de brechas; `permisivo` alimenta la vía de sobre-cobertura.

### 4.3 Léxico normativo crítico — detectores deterministas

Hay cambios cuya consecuencia es tan grande que **no pueden depender de que el modelo los note**.
Se detectan con reglas y elevan la prioridad automáticamente, sin importar qué diga la
similitud semántica. Defensa en profundidad: la regla atrapa lo que el modelo omite, el modelo
atrapa lo que la regla no anticipó.

Lista configurable por dominio (`config/lexico_critico.yaml`), como mínimo:

| Clase | Términos | Por qué |
|---|---|---|
| **Deóntico** | deberá · podrá · debe · puede · está obligado · tendrá la facultad · se abstendrá | Obligación ↔ facultad |
| **Conjunción lógica** | y · o · y/o · así como · ni | Acumulativo ↔ alternativo |
| **Negación y excepción** | no · sin · salvo · excepto · salvo que · siempre que · a menos que | Invierte o acota el alcance |
| **Cuantificador** | todo · todos · cualquier · algún · ningún · al menos · máximo · hasta | Define universo de aplicación |
| **Temporal** | días hábiles ↔ días calendario · plazos · a partir de ↔ hasta · inmediato | Cambia la exigencia operativa real |
| **Umbral** | cifras, porcentajes, montos, rangos | Cambia el punto de disparo del control |
| **Alcance** | incluye · excluye · comprende · aplica a · no aplica | Redefine sujetos obligados |
| **Referencia cruzada** | Art. N · numeral · literal · inciso | Reapunta la obligación a otro texto |
| **Sanción** | sancionable · multa · infracción · grave / leve | Cambia la consecuencia |

Cualquier `ChangeUnit` que toque una de estas clases obtiene `elevacion_deterministica: true` y
nunca puede ser auto-despriorizado por similitud semántica alta.

### 4.4 Puntuación como clase de primer orden

La puntuación cambia el sentido jurídico y merece su propio prompt de análisis. El prompt
genérico responde "se agregó una coma" y se detiene ahí — inútil. Detectores específicos:

- **Coma en cláusula relativa** (especificativa ↔ explicativa).
  `"los bancos que cumplan X"` restringe a un subconjunto;
  `"los bancos, que cumplan X,"` aplica a todos. Diferencia enorme en sujetos obligados.
- **Punto y coma ↔ coma en enumeraciones.** Cambia si los ítems son obligaciones separadas o
  una sola compuesta.
- **División o unión de oraciones.** Mueve el alcance de un calificador o una excepción.
- **Dos puntos introduciendo lista** taxativa ↔ enunciativa.
- **Paréntesis** convertidos en texto corrido o viceversa.

Estos van al rol `analista_texto` con `prompts/puntuacion_v1.md`, cuyo trabajo es exclusivamente
razonar sobre alcance y ámbito de aplicación, no describir el cambio.

### 4.5 Embeddings: pueden despriorizar, nunca descartar

Los embeddings de oración están entrenados para similitud **temática**, y son malos
precisamente en lo que aquí importa: `"deberá notificar"` y `"podrá notificar"` producen
vectores casi idénticos (coseno ≈ 0.98) porque hablan de lo mismo. Regla asimétrica, escrita
en `CLAUDE.md`:

- Similitud alta + delta léxico alto → **candidato a paráfrasis**, se despriorización pero
  igual se analiza y se muestra.
- Similitud alta + delta léxico bajo → **va al modelo sin excepción**. Aquí el coseno no
  aporta información y su valor alto es engañoso.
- Ningún umbral de coseno puede, por sí solo, eliminar una fila del reporte.

### 4.6 Ventana de contexto
No se envían las palabras cambiadas aisladas. Se envía:

- el **párrafo contenedor completo** de A y de B,
- ± 1 párrafo adyacente,
- el `section_path`,
- **los artículos referenciados** por el fragmento, si el cambio toca una referencia cruzada,
- el fragmento exacto que cambió, **marcado inline** con centinelas (`«del»…«/del»`,
  `«ins»…«/ins»`) para que el modelo sepa qué se movió sin perder el significado alrededor.

Si el párrafo excede un presupuesto de tokens, recortar por oraciones desde los extremos,
nunca por caracteres.

### 4.7 Anclaje de la afirmación (*grounding*)

El modelo debe citar el **fragmento textual exacto** que sustenta su juicio, no parafrasearlo.
Si afirma "el plazo se redujo", devuelve el span literal que lo prueba. Dos beneficios: reduce
alucinación, y el auditor verifica en dos segundos en vez de releer el párrafo. Se valida
programáticamente que el span citado exista literalmente en `context_a` o `context_b`; si no
existe, el análisis se marca `failed`, no se publica.

### 4.8 Abstención calibrada

El sistema debe poder decir **"esto requiere criterio humano"** en vez de producir siempre una
respuesta segura. Campo `requiere_criterio_humano: bool` con motivo. Se activa cuando:
dirección `divergente`, confianza bajo umbral, el cambio toca una referencia cruzada no
resuelta, o el fragmento depende de contexto fuera del documento.

Para una herramienta de soporte a decisiones en un banco regulado, la abstención calibrada vale
más que la confianza aparente. Un "no sé" honesto se revisa; una interpretación segura y
equivocada se aprueba.

### 4.9 Cuándo usar visión (regla de costo, no optimización posterior)
Un VLM de 8B sobre cada cambio en local es inviable en tiempo. Escalar a visión **solo** si:

1. el cambio es visual puro (L3) sin delta de texto,
2. el bbox intersecta una región detectada como tabla o figura,
3. el auditor lo pide explícitamente con "reanalizar con visión".

Cuando se escala: recortar la región del bbox + margen en ambas páginas, renderizar a PNG,
y enviar el par al rol `analista_vision`.

### 4.10 Salida estructurada
Pedir JSON estricto con esquema. Validar con Pydantic. `temperature=0` y semilla si el provider
la soporta — un papel de trabajo tiene que ser reproducible.

### 4.11 Contrato de fallo *(no negociable)*
Si la llamada al modelo falla, se agota el reintento, el JSON no valida, o el span citado no
existe literalmente en el contexto: `analysis.status = "failed"` con el error. **Nunca** se
escribe un análisis vacío o con el texto del error como si fuera contenido. La UI muestra esas
filas en estado distinto y reintentables. La exportación bloquea o marca en rojo si hay filas
`failed`.

### 4.12 Principio de gobierno

**El sistema propone; el auditor decide.** Ninguna fila se cierra automáticamente, ninguna se
elimina del reporte por criterio del modelo, y ningún riesgo se levanta sin aceptación humana
explícita. La despriorización es un orden de presentación, nunca una exclusión. Esto no es
prudencia genérica: es lo que permite defender la herramienta ante el regulador como apoyo al
juicio del auditor y no como sustituto de él.

---

## 5. Visor de comparación

- Dos paneles PDF.js lado a lado, scroll sincronizado por página (con toggle para desacoplar).
- Los bboxes se pintan como `<div>` absolutos sobre la capa del canvas, escalados por
  `viewport.scale`. Colores: rojo = eliminado (panel A), verde = insertado (panel B),
  ámbar = modificado (ambos), azul = visual, gris = movimiento.
- Click en un bbox → selecciona la fila de la tabla. Click en una fila → salta a la página y
  hace scroll al bbox en ambos paneles.
- Barra de filtros: por severidad, por tipo, por estado de revisión, por sección.
- Modo "solo cambios": lista de páginas que contienen al menos un `ChangeUnit`.

Librerías: `react-pdf` para el render; los overlays se implementan a mano (una capa de divs
posicionados) — `react-pdf-highlighter` sirve como referencia de implementación pero acopla
un modelo de anotación que aquí no hace falta.

---

## 6. Revisión humana y re-análisis

Cuatro acciones por fila:

| Acción | Efecto |
|---|---|
| **Aceptar** | El análisis del modelo se toma como válido. Dispara generación de `calificacion_analisis`. |
| **Corregir** | El auditor escribe la interpretación correcta. Se re-ejecuta el análisis con la corrección inyectada como contexto autoritativo. Se conservan ambas versiones. |
| **Descartar (FP)** | La fila se marca como falso positivo, sale del reporte pero queda en el log. |
| **Comentar** | Observación libre, no altera el análisis. |

**Generación de `calificacion_analisis`:** es el campo que el modelo produce *después* de la
decisión humana, no antes. Prompt separado (`calificacion_v1`) que recibe:
el cambio, el análisis original, la corrección del auditor si existe, y la rúbrica de
calificación definida en la plantilla. Al corregir, el análisis anterior se marca `stale` y se
regenera solo esa fila — nunca todo el run.

**Log de auditoría append-only:** `(run_id, change_id, acción, usuario, timestamp, antes, después)`.
Cumple dos funciones: evidencia de trazabilidad para el regulador, y dataset etiquetado para
mejora continua del prompt.

---

## 7. Exportación — análisis de la decisión

**La pregunta planteada:** ¿inyectar en una plantilla cargada, o solo descargar el reporte para
que el auditor lo pegue?

### Evaluación

**Opción A — el auditor pega manualmente.** Costo de desarrollo cero. Pero: se pierden los
metadatos de cabecera (referencia PT, entidad, período, preparado por, revisado por), el
formato deriva entre auditores, y sobre todo se rompe el vínculo trazable entre el papel de
trabajo y la corrida que lo produjo (modelo, versión de prompt, fecha). En una revisión
regulatoria eso es exactamente lo que se pide.

**Opción B — subir cualquier xlsx y escribir dentro.** Frágil. El round-trip de openpyxl sobre
un libro arbitrario puede perder gráficos, imágenes y ciertos formatos condicionales; `.xlsm`
requiere `keep_vba=True`; las celdas combinadas solo aceptan escritura en el ancla superior
izquierda; y `insert_rows` **no actualiza las referencias de las fórmulas que estén debajo**.
Además no hay forma de saber dónde va la tabla.

**Opción C — plantillas registradas con contrato de anclas. ← Recomendada**

La plantilla se **registra una vez** en la aplicación (versionada), no se sube en cada
exportación. Declara sus puntos de inserción mediante **nombres definidos de Excel**:

| Nombre definido | Función |
|---|---|
| `PT_ENTIDAD`, `PT_PERIODO`, `PT_REFERENCIA`, `PT_PREPARADO_POR` | Celdas de cabecera |
| `PT_TABLA_ANCLA` | Fila donde empieza la tabla |
| `PT_FILA_MODELO` | Una fila de ejemplo, con el formato exacto, que se clona por cada cambio |
| `PT_COL_<CAMPO>` | Mapeo columna → campo del `ChangeUnit` |

**Al registrar**, la app valida: existen todas las anclas, el mapeo de columnas resuelve contra
el esquema, y **no hay fórmulas que referencien filas por debajo del ancla** (si las hay,
advierte, porque insertar filas las romperá). Un registro que no valida se rechaza con el error
concreto — no se escribe nunca sobre una plantilla no validada.

**Al exportar**, `insert_rows` + clonado explícito del estilo de `PT_FILA_MODELO`
(openpyxl no copia estilos a las filas insertadas; hay que copiar `_style` celda por celda).

### Decisión: implementar los tres botones, con esta prioridad

1. **`Exportar tabla (XLSX)`** — libro limpio generado desde cero. Siempre funciona, sin
   dependencias externas. Se construye primero (WP-9).
2. **`Exportar papel de trabajo`** — inyección en plantilla registrada. Es el entregable real.
   Se construye al final de Fase 1 (WP-10).
3. **`Exportar PDF anotado`** — A y B con los resaltados incrustados vía PyMuPDF. Es el anexo
   de evidencia que el papel de trabajo referencia. Barato de construir (PyMuPDF ya está) y
   cierra el ciclo probatorio: la tabla cita página y sección, el PDF anotado la respalda.

La Opción A no se descarta: queda cubierta por el botón 1, que el auditor puede pegar donde
quiera. Pero no debe ser el único camino.

---

## 8. FASE 1 — Local con DMR

Objetivo: el ciclo completo funcionando en la máquina del desarrollador, sin nube.

### WP-0 · Contratos y andamiaje
- Repo, `CLAUDE.md`, `docker-compose` (backend, frontend, DMR).
- `schemas/change_unit.schema.json` → Pydantic + tipos TS generados.
- `ModelGateway` con `DMRProvider` y `FakeProvider`.
- **Generador de fixtures**: script que produce pares de PDF sintéticos con cambios en
  posiciones conocidas (reportlab), más `ground_truth.json`.
- ✅ *Aceptación:* `pytest` verde con `FakeProvider`; los fixtures existen.

> Construir el generador de fixtures **antes** del motor de diff. Sin ground truth no hay forma
> de saber si un refactor mejoró o empeoró la detección.

### WP-1 · Rebanada vertical mínima
Un PDF de una página con un cambio, de punta a punta: subir → diff → bbox → una fila en tabla →
exportar xlsx. Feo pero completo.
- ✅ *Aceptación:* el resaltado se ve en pantalla y el xlsx se descarga.

Esta es la disciplina más importante del plan: **ver un resaltado en pantalla antes de construir
el motor de diff completo.**

### WP-2 · Motor de diff (L0–L4)
Alineación por anclas, diff léxico, capa visual, agrupación.
- ✅ *Aceptación:* precisión ≥0.95 y recall ≥0.95 contra los fixtures; en un documento
  reflowado sin cambios de fondo, ≤5 `ChangeUnit`.

### WP-3 · Detección de secciones
Árbol de encabezados + asignación de `section_path`.
- ✅ *Aceptación:* ≥90% de los cambios reciben la sección correcta en un corpus de 3 normativas reales.

### WP-4 · Jobs persistidos
API basada en jobs, worker asíncrono, checkpoints por etapa, SSE de progreso, reattach por
`run_id` en la URL.
- ✅ *Aceptación:* refrescar el navegador a mitad de una corrida no pierde el proceso.

### WP-5 · Visor
Paneles A|B, overlays, scroll sincronizado, navegación bidireccional tabla↔bbox.
- ✅ *Aceptación:* click en fila salta al bbox en ambos paneles con el zoom actual.

### WP-6 · Señales semánticas deterministas
Delta léxico, delta semántico (embeddings), cuadrante, detectores de léxico crítico (§4.3),
detectores de puntuación (§4.4). **Sin modelo generativo** — todo esto es reproducible y barato.
- ✅ *Aceptación:* sobre el corpus dorado, recall = 1.0 en cambios de léxico crítico
  (deóntico, conjunción, negación, temporal, umbral). Cero excepciones: si falla uno, se
  ajusta el diccionario antes de avanzar.

### WP-6b · Capa de análisis con modelo (L5)
Ventana de contexto, prompts versionados (`analisis_v1`, `puntuacion_v1`), dirección
bidireccional, grounding verificado, abstención calibrada, escalado a visión según regla,
contrato de fallo.
- ✅ *Aceptación:* un modelo caído produce filas `failed` visibles y reintentables, jamás
  contenido falso; un span citado que no existe literalmente en el contexto marca `failed`.

### WP-7 · Grilla de revisión
Estados, comentarios, correcciones, descarte de FP, filtros.
- ✅ *Aceptación:* corregir una fila regenera solo esa fila.

### WP-8 · Calificación post-revisión
Prompt de calificación, rúbrica configurable, regeneración selectiva, versionado del análisis.

### WP-9 · Exportación rápida XLSX
Libro generado desde cero con `xlsxwriter`.

### WP-10 · Motor de plantillas
Registro, validación de anclas, inyección con clonado de estilos, PDF anotado.
- ✅ *Aceptación:* una plantilla real de papel de trabajo se llena conservando formato,
  cabecera y columna de calificación.

---

## 9. FASE 2 — Azure AI Foundry

Objetivo: mismo producto, modelos gestionados, postura apta para un banco regulado.

### WP-11 · Provider de Foundry

Foundry usa **deployments como alias de modelo**: se invoca por nombre de deployment, no por
nombre de modelo. El endpoint `/openai/v1` funciona con el SDK estándar de OpenAI cambiando
solo `base_url`, lo que hace que el provider sea prácticamente el mismo código que DMR más
autenticación.

**Puntos que rompen si no se prevén:**

1. **Autenticación.** Usar Entra ID (`DefaultAzureCredential` + managed identity), no API key.
   Una key da acceso total al recurso y hay que rotarla a mano — cumplimiento lo va a objetar.
   El gateway debe aceptar un *token provider* invocable, no un string.
2. **Filtros de contenido.** Azure aplica filtrado que DMR no tiene, y el texto normativo o
   legal ocasionalmente lo dispara. El error tiene forma distinta a un fallo de red: hay que
   normalizarlo y mostrarlo como tal. Si ocurre de forma sistemática, la excepción de filtro se
   solicita con justificación documentada y tarda semanas — detectarlo temprano, no en producción.
3. **Cuotas TPM/RPM.** DMR no tiene límite; Foundry sí. El gobernador de concurrencia y el
   backoff exponencial viven **en el gateway**, no en el pipeline.
4. **Versión de API fijada.** Anclar `api-version` explícitamente y probar los cambios en
   staging; las respuestas cambian entre versiones.
5. **Retirada del SDK beta de inferencia.** El SDK `azure-ai-inference` en beta se retira el
   26-ago-2026. Escribir contra el endpoint OpenAI/v1 con el SDK estándar desde el inicio.

### WP-12 · Validación de paridad *(el entregable de más valor de esta fase)*
Correr el corpus dorado con Fase 1 y Fase 2, y medir la desviación:
concordancia de severidad, de `tipo_cambio`, distancia semántica entre análisis, latencia, costo.

Esto no es una prueba de QA: es **evidencia de validación de modelo**. Es el documento que
justifica ante el regulador que el cambio de proveedor no alteró el criterio del papel de
trabajo. Guardarlo como artefacto versionado, no como un notebook.

### WP-13 · Hardening
- PostgreSQL + Blob Storage (misma capa SQLAlchemy).
- Autenticación de usuarios (Entra ID) y roles: preparador / revisor.
- Log de auditoría inmutable con retención definida.
- Cifrado en reposo, private endpoints, sin datos en logs.

### WP-14 · Despliegue
Container Apps o AKS, CI con la suite de fixtures como gate, secretos en Key Vault,
observabilidad (latencia y costo por rol de modelo).

---

## 9b. Evaluación y calibración *(no es QA — es validación de modelo)*

Si la herramienta levanta riesgos, su tasa de error tiene que estar medida y documentada. Sin
esto no es defendible ante una revisión regulatoria.

### Corpus dorado
Además de los fixtures sintéticos, un corpus de **pares reales** de normativa (versión anterior
vs. vigente de SBS/BCE/SEPS/UAF) con cada cambio etiquetado por un auditor:
`direccion`, `naturaleza`, `severidad`, `es_falso_positivo`. Cien a doscientos cambios
etiquetados bastan para calibrar; se amplía con las correcciones que los auditores hagan en
producción (el log de §6 ya es ese dataset).

### Las dos métricas no son simétricas

| Métrica | Objetivo | Por qué |
|---|---|---|
| **Recall en cambios críticos** | ≈ 1.0 | Un cambio sustantivo omitido se convierte en un hallazgo del regulador. Es un fallo que no se recupera. |
| **Precisión general** | ≥ 0.7 aceptable | El ruido cansa al auditor, pero es recuperable: descarta la fila y sigue. |

**Los umbrales se calibran a favor del recall.** Explícitamente: se prefiere mostrar de más y
que el humano descarte, antes que filtrar de más y que algo pase. Documentar la decisión y su
justificación en el repo — es una decisión de riesgo, no un parámetro técnico.

### Métricas por clase
Reportar recall desagregado por clase de léxico crítico. Un recall global de 0.94 puede esconder
un 0.60 en cambios deónticos, que es justo la clase que no se puede fallar.

### Concordancia con el auditor
Medir acuerdo modelo↔humano sobre `direccion` y `severidad` (kappa de Cohen). Es la métrica que
responde la pregunta que hará el regulador: *¿qué tan de acuerdo está esta herramienta con el
criterio profesional?* Se recalcula en cada cambio de prompt o de modelo, y en la validación de
paridad Fase 1 ↔ Fase 2 (WP-12).

---

## 10. Metodología para Claude Code

### `CLAUDE.md` en la raíz — invariantes que se repiten en cada sesión

```markdown
# Invariantes del proyecto

1. Coordenadas: puntos PDF, origen arriba-izquierda, página 1-indexada.
   Toda bbox lleva page_size para escalar en el frontend.
2. Ninguna llamada a modelo fuera de ModelGateway. Prohibido importar
   `openai` o `httpx` fuera de `gateway/`.
3. Un fallo de modelo NUNCA produce contenido. status="failed", visible y reintentable.
4. El diff se calcula solo en backend. El frontend dibuja, no calcula.
5. Todo cambio al esquema de ChangeUnit regenera los tipos TS en el mismo commit.
6. Todo análisis registra provenance (provider, modelo, prompt_version, hash).
7. Los tests corren con FakeProvider. Ningún test requiere GPU ni red.
8. Un ancla es una referencia posicional, NO una afirmación de que el contenido
   es igual. Toda ancla se reverifica con hash_estricto (puntuación incluida).
9. Ningún umbral de similitud puede eliminar una fila del reporte. Los embeddings
   despriorizan; nunca descartan.
10. Un cambio que toca léxico crítico (deóntico, conjunción, negación, temporal,
    umbral) nunca se despriorización automáticamente.
11. El modelo cita spans literales. Si el span no existe en el contexto,
    el análisis es `failed`.
12. El sistema propone; el auditor decide. Nada se cierra automáticamente.
```

### Prácticas de ejecución

**Contract-first.** Los tres contratos de §2 se commitean antes que cualquier lógica. Cada
tarea posterior los referencia explícitamente en el prompt.

**Fixtures antes que motor.** WP-0 incluye el generador de PDFs sintéticos. Un motor de diff sin
ground truth es imposible de refactorizar con confianza.

**Rebanada vertical antes que profundidad.** WP-1 completo antes de WP-2. La tentación de
construir el motor perfecto antes de ver un pixel en pantalla es el modo de fallo más común
en este tipo de proyecto.

**Un WP = un PR.** Cada paquete con su criterio de aceptación escrito en el prompt inicial.
Terminar la sesión cuando el criterio se cumple, no cuando "parece que funciona".

**Paralelización.** Con los contratos congelados, WP-5 (visor) y WP-2 (motor) pueden avanzar en
sesiones separadas sin bloquearse. WP-9 y WP-10 también.

**Prompts versionados en el repo.** `prompts/analisis_v3.md`, `prompts/calificacion_v1.md`.
Nunca embebidos en el código: son artefactos auditables y su versión va en cada fila del reporte.

---

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Avalancha de falsos positivos por reflow | Alineación por anclas (L1) + clasificación `move` oculta por defecto |
| PDFs escaneados sin capa de texto | Detectar ausencia de texto y rechazar explícitamente, o pasar por OCR (Qwen-VL / olmOCR) marcando el run como "derivado de OCR" — con la advertencia de que el error de OCR se propaga al diff |
| VLM local demasiado lento | Regla de escalado selectivo desde el diseño (§4), no como optimización posterior |
| Plantilla con fórmulas o macros | Validación en el registro; `keep_vba=True` para `.xlsm`; rechazo con error concreto si hay fórmulas bajo el ancla |
| Deriva entre Fase 1 y Fase 2 | WP-12 como gate, no como verificación opcional |
| Filtro de contenido de Azure sobre texto normativo | Detectar en WP-12, no en producción; tramitar excepción con anticipación |
| No reproducibilidad del papel de trabajo | `temperature=0` + provenance completa por fila + prompts versionados |
| **Cambio de puntuación invisible por la normalización de anclas** | Doble hash en L1 con reverificación estricta (§3, L1 paso 4) |
| **Cambio deóntico de una palabra pasa desapercibido** | Detectores deterministas de léxico crítico (§4.3) + recall = 1.0 como criterio de aceptación de WP-6 |
| **Coseno alto interpretado como "sin cambio"** | Regla asimétrica: los embeddings despriorizan, nunca descartan (§4.5) |
| **Paráfrasis masiva entierra la fila crítica** | Clasificación por cuadrante (§4.1) y orden de la tabla por cuadrante, no por volumen de texto |
| Modelo produce interpretación segura y equivocada | Grounding verificado (§4.7) + abstención calibrada (§4.8) + aceptación humana obligatoria |

---

## 12. Nota de integración

Este comparador cubre exactamente el módulo pendiente de **normativa actual vs. anterior** del
proyecto Comparador Normativo. Vale la pena decidir desde el inicio si vive como servicio
independiente con su propia API (recomendado: el ciclo de vida y el usuario son distintos) o
como módulo dentro de aquel. Si es independiente, el `ChangeUnit` es el contrato de
interoperabilidad entre ambos, y la detección de secciones (WP-3) es código compartible con el
parser de Docling que ya existe.
