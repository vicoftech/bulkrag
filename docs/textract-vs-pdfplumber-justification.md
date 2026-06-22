# Justificación técnica: Textract OCR vs ECS Fargate + pdfplumber

Documento de referencia para evaluar la estrategia de extracción de texto de PDFs regulatorios (ANMAT, Boletín Oficial) en el pipeline RAG.

---

## 1. Contexto

El corpus objetivo supera **330,000 PDFs** (~188 GB) almacenados en S3, provenientes de fuentes regulatorias confiables:

| Tenant | PDFs (prod) | Tamaño | Origen |
|---|---|---|---|
| `tenant_anmat` | ~261,000 | ~172 GB | Disposiciones y avisos ANMAT |
| `tenant_boletin` | ~77,000 | ~17 GB | Secciones del Boletín Oficial |

En abril de 2026 se ejecutó una extracción masiva con **Amazon Textract** (OCR asíncrono), con un costo de **USD 1,255.46**. En paralelo, el POC **bulkrag** validó una alternativa basada en **ECS Fargate + pdfplumber**, con un costo extrapolado de **menos de USD 10** para el mismo volumen de archivos con texto digital.

Este documento justifica por qué Textract OCR no era la herramienta adecuada para este caso de uso y por qué la alternativa propuesta es técnicamente y económicamente superior.

---

## 2. Qué se utilizó con Textract

### Datos de billing (cuenta prod `asap_main`, abril 2026)

| Métrica | Valor |
|---|---|
| Servicio | Amazon Textract |
| Variante | **DetectDocumentText — Async** (`USE1-AsyncTextPagesProcessed`) |
| Páginas procesadas | **837,973** |
| Costo total | **USD 1,255.46** |
| Tarifa efectiva | USD 1.50 / 1,000 páginas |
| Período de ejecución | 15–24 abril 2026 (pico: 16 abr, USD 749.68) |

No se utilizaron variantes más costosas (`AnalyzeDocument`, `AnalyzeExpense`, etc.). El gasto corresponde exclusivamente a **OCR página por página** vía API asíncrona.

### Equivalencia en documentos

```
837,973 páginas ÷ ~6.5 páginas/archivo ≈ 130,000 documentos
```

Esto coincide con el volumen estimado del proyecto (~130K archivos BORA/ANMAT).

---

## 3. Por qué Textract OCR no tenía sentido en este caso

### 3.1 Naturaleza de los documentos

Los PDFs de ANMAT y Boletín Oficial son emitidos por organismos estatales y publicados en formatos electrónicos oficiales. En su gran mayoría contienen **texto digital embebido** (no son escaneos de papel). Esto fue validado en el POC:

| Muestra estratificada (500 PDFs) | Resultado |
|---|---|
| Boletín | **100%** extracción exitosa (`OK`) |
| ANMAT | **87.4%** `OK`, 12% `EMPTY_TEXT`, 0.6% `SKIPPED` (>30 MB) |

**Textract OCR está diseñado para convertir imágenes en texto.** Cuando el PDF ya contiene texto digital, OCR:

- Reinterpreta visualmente lo que ya está codificado en el archivo.
- No mejora la calidad del texto extraído.
- Cobra por cada página procesada independientemente de si el texto ya existía.

### 3.2 Modelo de costo incompatible con el volumen

| Enfoque | Unidad de cobro | Costo por aviso de 1 página | Costo por disposición de 50 páginas |
|---|---|---|---|
| Textract OCR | Por página | USD 0.0015 | USD 0.075 |
| pdfplumber + Fargate | Por segundo de CPU | ~USD 0.000009 | ~USD 0.00002 |

Textract escala linealmente con **páginas**. pdfplumber escala con **tiempo de CPU**, que para PDFs digitales chicos es de milisegundos.

### 3.3 OCR masivo innecesario

La factura de abril demuestra que se enviaron **todas las páginas de todos los documentos** a OCR, incluyendo aquellos con texto digital legible. Esto equivale a pagar por un servicio de reconocimiento óptico de caracteres cuando bastaba con **leer el contenido ya presente en el PDF**.

### 3.4 Resumen: cuándo sí y cuándo no usar Textract

| Escenario | Textract OCR | pdfplumber |
|---|---|---|
| PDF escaneado (imagen) | **Sí** | No (devuelve `EMPTY_TEXT`) |
| PDF digital con texto embebido | **No** (desperdicio) | **Sí** |
| PDF de fuente confiable y legible | **No** | **Sí** |
| Necesidad de extraer tablas estructuradas | Considerar `AnalyzeDocument` | Limitado |
| Volumen masivo (>100K docs) | Costo prohibitivo | Costo marginal |

---

## 4. Resultados del POC: ECS Fargate + pdfplumber

### Configuración

| Parámetro | Valor |
|---|---|
| Compute | ECS Fargate — 4 vCPU / 8 GB |
| Paralelismo | 4 workers (`ProcessPoolExecutor`) |
| Herramienta | pdfplumber (Python) |
| Límite de tamaño | 30 MB (archivos mayores se descartan) |

### Benchmarks con muestra estratificada (500 PDFs por tenant)

| Métrica | Boletín | ANMAT |
|---|---|---|
| Size promedio | 0.21 MB | 0.77 MB |
| Tasa de éxito (`OK`) | 100% | 87.4% |
| Wall time (500 PDFs) | 49 s | 188 s |
| Costo del batch | USD 0.005 | USD 0.012 |

### Extrapolación al corpus completo

| Tenant | PDFs | Costo Fargate estimado | Tiempo estimado |
|---|---|---|---|
| Boletín | 77,237 | **USD 0.71** | ~2.1 h |
| ANMAT | 261,090 | **USD 6.06** | ~27.2 h |
| **Total** | **~338,000** | **~USD 6.77** | ~29 h |

Para **130,000 archivos** (subconjunto del proyecto): **~USD 2.60**.

---

## 5. Comparación directa

| Dimensión | Textract OCR (abr 2026) | ECS + pdfplumber (POC) |
|---|---|---|
| **Costo real / estimado** | USD 1,255.46 | USD 2.60 – 6.77 |
| **Ratio de costo** | 1× | **~185–480× más barato** |
| **Método** | OCR página por página | Lectura de texto digital |
| **Páginas facturadas** | 837,973 | 0 (no aplica) |
| **Tiempo** | ~9 días (con throttling) | ~29 h (1 task, 4 workers) |
| **Cobertura texto digital** | Sí (pero pagando OCR) | Sí (nativo) |
| **Cobertura escaneos** | Sí | No (`EMPTY_TEXT`) |
| **Control** | API managed, límites de throughput | Infra propia, escalable |
| **Predictibilidad de costo** | Por página (variable) | Por segundo de CPU (fijo) |

---

## 6. Estrategia recomendada: pipeline híbrido

Textract no debe descartarse por completo, pero su uso debe ser **selectivo**, no masivo.

```
                    ┌─────────────────────────┐
                    │   PDF en S3 (fuente)    │
                    └───────────┬─────────────┘
                                │
                    ┌───────────▼─────────────┐
                    │  ¿Tamaño > 30 MB?       │
                    └──┬──────────────────┬───┘
                      Sí                 No
                       │                  │
              ┌────────▼────────┐  ┌──────▼──────────────┐
              │ Cola OCR        │  │ ECS + pdfplumber    │
              │ (Textract async) │  │ (texto digital)     │
              └────────┬────────┘  └──┬──────────────┬───┘
                       │              │              │
                       │         ┌────▼────┐   ┌─────▼──────┐
                       │         │   OK    │   │ EMPTY_TEXT │
                       │         └────┬────┘   └─────┬──────┘
                       │              │              │
                       │              │       ┌──────▼──────┐
                       │              │       │ Cola OCR    │
                       │              │       │ (Textract)  │
                       │              │       └──────┬──────┘
                       │              │              │
                    ┌──▼──────────────▼──────────────▼───┐
                    │     Texto extraído → S3 output     │
                    │     (batch-poc/output/{key}.txt)   │
                    └────────────────────────────────────┘
```

### Costo estimado del pipeline híbrido (130K archivos)

| Etapa | Archivos | Páginas est. | Costo |
|---|---|---|---|
| pdfplumber (texto digital, ~87%) | ~113,000 | — | ~USD 2 |
| Textract OCR (`EMPTY_TEXT` + >30 MB, ~13%) | ~17,000 | ~102,000 | ~USD 153 |
| **Total** | 130,000 | ~102,000 | **~USD 155** |

**Ahorro vs OCR masivo:** USD 1,255 → USD 155 = **~88% de reducción**, manteniendo cobertura completa.

---

## 7. Conclusión

La decisión original de utilizar Textract OCR de forma masiva sobre el corpus completo fue **técnicamente innecesaria y económicamente ineficiente** para este caso de uso:

1. **Los documentos son de fuentes confiables** (ANMAT, Boletín Oficial) con texto digital embebido en más del 87% de los casos.
2. **Textract cobra por página OCR** independientemente de si el texto ya existe en el PDF, generando un costo de **USD 1,255** para ~838K páginas que no requerían reconocimiento óptico.
3. **pdfplumber extrae el mismo texto** en milisegundos por archivo, con un costo de compute de **menos de USD 10** para todo el corpus.
4. **Textract sigue siendo válido** como herramienta complementaria para el ~13% de documentos escaneados o sin texto digital, reduciendo el costo total estimado a **~USD 155** en lugar de USD 1,255.

La recomendación es adoptar **ECS Fargate + pdfplumber como pipeline principal** y reservar Textract OCR exclusivamente para documentos que pdfplumber no pueda procesar (`EMPTY_TEXT`, archivos escaneados, PDFs >30 MB).

---

## Anexo: fuentes de datos

| Dato | Fuente |
|---|---|
| Billing Textract abril 2026 | AWS Cost Explorer, cuenta `asap_main` (913123310997) |
| Benchmarks Fargate | POC bulkrag, muestra estratificada 500 PDFs/tenant |
| Corpus prod | S3 `rag-documents-prod-913123310997` |
| Tarifas Fargate | USD 0.04048/vCPU-h + USD 0.004445/GB-h (us-east-1, on-demand) |
| Tarifas Textract | USD 1.50/1,000 páginas (DetectDocumentText Async, tier 1) |
