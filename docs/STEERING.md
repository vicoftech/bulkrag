# Bulkrag — Project Steering

Documento de referencia para alinear decisiones de producto, arquitectura e implementación del extractor masivo de PDFs para RAG.

---

## 1. Producto

### Problema

Los sistemas RAG de ASAP necesitan texto extraído de PDFs regulatorios almacenados en S3 para indexación y búsqueda semántica. El corpus actual supera **330,000 documentos** (~188 GB) distribuidos en dos tenants:

| Tenant | PDFs (prod) | Tamaño | Contenido |
|---|---|---|---|
| `tenant_anmat` | ~261,000 | ~172 GB | Disposiciones, avisos y documentos ANMAT |
| `tenant_boletin` | ~77,000 | ~17 GB | Secciones del Boletín Oficial |

Extraer ese volumen con servicios managed como **Amazon Textract** es costoso y difícil de predecir. Se necesita un pipeline **batch**, **económico** y **controlable** que convierta PDFs con texto digital en archivos `.txt` listos para el pipeline RAG.

### Solución

**Bulkrag** es un POC de extracción masiva que:

1. Lee listas de PDFs desde S3 (manifests JSON).
2. Procesa en paralelo con **pdfplumber** dentro de contenedores **ECS Fargate**.
3. Escribe texto extraído, logs por archivo y summaries de batch en S3.
4. Permite estimar **tiempo**, **costo** y **calidad** antes de escalar a producción.

### Usuarios / consumidores

- **Pipeline RAG**: consume `batch-poc/output/{key}.txt`.
- **Operaciones / data**: revisa `batch-poc/logs/` y `batch-poc/results/` para auditoría.
- **Equipo de plataforma**: despliega infra vía Terraform + GitHub Actions.

### Criterios de éxito del POC

| Criterio | Target |
|---|---|
| Extracción exitosa (texto digital) | > 90% |
| Estabilidad batch | Sin intervención manual |
| Costo vs Textract | Significativamente menor a escala |
| Predecibilidad | Métricas de tiempo/costo por archivo y por tenant |

### Decisiones de producto vigentes

- **Límite de tamaño**: PDFs > **30 MB** se descartan (`SKIPPED_TOO_LARGE`) para evitar OOM en Fargate.
- **PDFs escaneados**: se marcan `EMPTY_TEXT` (sin OCR en este POC).
- **Muestreo**: para estimaciones realistas usar muestra **estratificada por cuartiles de tamaño**, no los primeros N del listado S3.

---

## 2. Stack tecnológico

| Capa | Tecnología |
|---|---|
| Extracción | Python 3.12, pdfplumber, boto3 |
| Paralelismo | `ProcessPoolExecutor` (1 worker ≈ 1 vCPU) |
| Contenedor | Docker → ECR `rag-ecs-extractor` |
| Orquestación | ECS Fargate (on-demand; Spot pendiente) |
| Storage | S3 (`rag-documents-{env}-{account}`) |
| IaC | Terraform ≥ 1.8, AWS provider ~> 5.0 |
| CI/CD | GitHub Actions + OIDC (`bulkrag-github-actions-dev`) |
| State | S3 `bulkrag-terraform-state-*` + DynamoDB locks |
| Logs | CloudWatch `/ecs/rag-extractor-poc-{env}` |
| Script operativo | `ecs-extractor/scripts/run_poc_batches.py` |

### Configuración Fargate (dev)

| Parámetro | Valor |
|---|---|
| vCPU | 4 (4096) |
| RAM | 8 GB (8192) |
| Workers paralelos | 4 (`WORKER_COUNT`) |
| Tamaño máximo PDF | 30 MB (`MAX_FILE_SIZE_MB`) |

---

## 3. Arquitectura

### Diagrama de flujo

```
┌─────────────────────────────────────────────────────────────────┐
│  Operador / CI                                                   │
│  run_poc_batches.py                                              │
│    → lista PDFs en S3 por prefix                                 │
│    → escribe manifest: batch-poc/manifests/tanda_N.json          │
│    → lanza ECS Task Fargate                                      │
│    → espera + imprime reporte                                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  ECS Fargate Task (rag-extractor-poc-dev)                        │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │ Worker 1   │ │ Worker 2   │ │ Worker 3   │ │ Worker 4   │   │
│  │ proceso    │ │ proceso    │ │ proceso    │ │ proceso    │   │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘   │
│        │              │              │              │           │
│        └──────────────┴──────────────┴──────────────┘           │
│  Por cada PDF:                                                   │
│    head_object → ¿> 30 MB? → SKIPPED_TOO_LARGE                  │
│    get_object  → pdfplumber → OK | EMPTY_TEXT | ERROR           │
│    put_object  → output + log                                    │
│  Al finalizar → batch-poc/results/tanda_N_summary.json          │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  S3 — rag-documents-dev-615216531593                             │
│  tenant_{anmat,boletin}/...        ← PDFs fuente                 │
│  batch-poc/manifests/              ← listas de trabajo           │
│  batch-poc/output/{key}.txt       ← texto extraído             │
│  batch-poc/logs/{key}.json         ← log por archivo             │
│  batch-poc/results/*_summary.json ← métricas de batch            │
└─────────────────────────────────────────────────────────────────┘
```

### Estados por archivo

| Status | Significado |
|---|---|
| `OK` | Texto extraído y escrito en `output/` |
| `EMPTY_TEXT` | PDF sin texto digital (probable escaneo) |
| `SKIPPED_TOO_LARGE` | PDF supera 30 MB; no se descarga ni procesa |
| `ERROR` | Excepción durante descarga o extracción |

### Cuentas AWS

| Cuenta | Profile | Rol |
|---|---|---|
| `615216531593` | `asap_dev` | Infra ECS, bucket dev, CI/CD |
| `913123310997` | `asap_main` | Bucket prod fuente de PDFs |

### Repositorio

- **GitHub**: `vicoftech/bulkrag`
- **Branch activo**: `development`
- **Estructura clave**:
  ```
  ecs-extractor/extractor/     ← container
  ecs-extractor/scripts/       ← orquestador local
  terraform/modules/         ← ecs_extractor, github_oidc
  terraform/envs/{dev,prod}/   ← entornos
  docs/                        ← documentación
  test_{anmat,boletin}/        ← muestras y reportes locales
  ```

---

## 4. Resultados del POC (jun 2026)

### Corpus prod

| Tenant | PDFs | Avg size |
|---|---|---|
| ANMAT | 261,090 | 0.67 MB |
| Boletín | 77,237 | 0.22 MB |

### Benchmarks en dev (4 vCPU / 8 GB / 4 workers)

| Muestra | Archivos | Avg size | Wall time | Costo batch | Extrap. corpus |
|---|---|---|---|---|---|
| Boletín estratificada | 500 | 0.21 MB | ~49 s | ~$0.005 | ~$0.71 / ~2.1 h |
| ANMAT estratificada | 500 | 0.77 MB | ~500 s* | ~$0.028* | pendiente re-run |

\* ANMAT falló por OOM en PDFs > 30 MB con 4 workers; motivó el límite de tamaño.

### Lecciones aprendidas

1. **Paralelismo**: 4 procesos por task reduce wall time ~4× vs secuencial.
2. **Una task por batch**: evita duplicar cold start de Fargate (~60–90 s).
3. **Muestra representativa**: estratificación por tamaño es crítica; los primeros 100 del listado S3 no representan el corpus.
4. **Outliers de tamaño**: ANMAT tiene disposiciones de hasta ~108 MB; requieren límite, OCR separado o más RAM.
5. **Costo Fargate**: ~$0.00005–0.0002 USD/archivo para PDFs típicos (< 1 MB).

---

## 5. Roadmap sugerido

| Fase | Objetivo |
|---|---|
| **POC actual** | Validar pdfplumber, costo y throughput en dev |
| **Re-run ANMAT** | Muestra estratificada con límite 30 MB desplegado |
| **Producción** | Step Functions / SQS para orquestar miles de tasks |
| **OCR** | Rama separada para `EMPTY_TEXT` y PDFs > 30 MB (Textract o Tesseract) |
| **Fargate Spot** | Reducir costo ~70% en batches no críticos |
| **Indexación RAG** | Conectar `output/` al pipeline de embeddings existente |

---

## 6. Comandos operativos

```bash
# Correr batch
AWS_PROFILE=asap_dev AWS_DEFAULT_REGION=us-east-1 \
  python3 ecs-extractor/scripts/run_poc_batches.py \
  --bucket rag-documents-dev-615216531593 \
  --prefix tenant_boletin/sample-stratified/ \
  --cluster rag-extractor-poc-dev \
  --task-family rag-extractor-poc-dev \
  --subnets subnet-05adff7c61ea0ac0a subnet-06e71711cc39c6112 \
  --security-group sg-0eb719c176f522272 \
  --total 500

# Ver logs ECS
aws logs tail /ecs/rag-extractor-poc-dev --follow --profile asap_dev
```

---

## 7. Referencias

- `docs/rag-ecs-extractor-poc.mdc` — spec detallada del POC
- `docs/terraform-remote-state.md` — backend Terraform
- `docs/github-secrets-dev.md` — secrets CI/CD
- `test_anmat/extraction_report_stratified_500.json` — reporte boletín/anmat
- `test_boletin/extraction_report_stratified_500.json` — reporte boletín
