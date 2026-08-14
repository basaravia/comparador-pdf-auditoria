/**
 * Generado desde schemas/change_unit.schema.json — NO EDITAR A MANO.
 * Fuente de verdad: backend/src/comparador/schemas/change_unit.py
 * Regenerar con: node frontend/scripts/generate-types.mjs
 */

export type Id = string
export type RunId = string
export type Kind = 'insert' | 'delete' | 'replace' | 'format' | 'visual' | 'move'
export type PageA = number | null
export type PageB = number | null
export type BboxA = [number, number, number, number][]
export type BboxB = [number, number, number, number][]
export type PageSizeA = [number, number] | null
export type PageSizeB = [number, number] | null
export type SectionPath = string
export type AnchorConfidence = number
export type TextA = string
export type TextB = string
export type ContextA = string
export type ContextB = string
export type DeltaLexico = number | null
export type DeltaSemantico = number | null
export type Cuadrante = ('trivial' | 'parafrasis' | 'critico_oculto' | 'reescritura') | null
export type LexicoCritico = string[]
export type ElevacionDeterministica = boolean
export type ClasePuntuacion = string | null
export type Status = 'ok' | 'failed' | 'skipped' | 'stale'
export type QueCambio = string | null
export type Implicacion = string | null
export type Direccion = ('restrictivo' | 'permisivo' | 'equivalente' | 'divergente') | null
export type Naturaleza =
  ('obligacion' | 'plazo' | 'umbral' | 'alcance' | 'procedimiento' | 'definicion' | 'referencia' | 'sancion') | null
export type EfectoEsperado = string | null
export type RiesgoSiNoSeAtiende = string | null
export type SpanA = string | null
export type SpanB = string | null
export type Severidad = ('alta' | 'media' | 'baja' | 'nula') | null
export type RequiereCriterioHumano = boolean
export type MotivoAbstencion = string | null
export type Confianza = number | null
export type Provider = string
export type Model = string
export type PromptVersion = string
export type Temperature = number
export type UsedVision = boolean
export type InputHash = string
export type Timestamp = string
export type LatencyMs = number
export type Estado = 'pendiente' | 'aceptado' | 'corregido' | 'descartado_fp'
export type Comentario = string | null
export type InterpretacionCorregida = string | null
export type Revisor = string | null
export type RevisadoEn = string | null
export type CalificacionAnalisis = string | null

/**
 * Unidad de todo el sistema — una fila de la tabla de revisión (§2.1).
 */
export interface ChangeUnit {
  id: Id
  run_id: RunId
  kind: Kind
  page_a?: PageA
  page_b?: PageB
  bbox_a?: BboxA
  bbox_b?: BboxB
  page_size_a?: PageSizeA
  page_size_b?: PageSizeB
  section_path?: SectionPath
  anchor_confidence?: AnchorConfidence
  text_a?: TextA
  text_b?: TextB
  context_a?: ContextA
  context_b?: ContextB
  signals?: Signals
  analysis?: Analysis
  review?: Review
  calificacion_analisis?: CalificacionAnalisis
}
/**
 * Señales calculadas sin modelo generativo (§4, WP-6).
 */
export interface Signals {
  delta_lexico?: DeltaLexico
  delta_semantico?: DeltaSemantico
  cuadrante?: Cuadrante
  lexico_critico?: LexicoCritico
  elevacion_deterministica?: ElevacionDeterministica
  clase_puntuacion?: ClasePuntuacion
}
/**
 * Salida del rol analista_texto/analista_vision (§4, WP-6b).
 */
export interface Analysis {
  status?: Status
  que_cambio?: QueCambio
  implicacion?: Implicacion
  direccion?: Direccion
  naturaleza?: Naturaleza
  efecto_esperado?: EfectoEsperado
  riesgo_si_no_se_atiende?: RiesgoSiNoSeAtiende
  evidencia?: Evidencia | null
  severidad?: Severidad
  requiere_criterio_humano?: RequiereCriterioHumano
  motivo_abstencion?: MotivoAbstencion
  confianza?: Confianza
  provenance?: Provenance | null
}
/**
 * Spans literales que sustentan el análisis (§4.7 — grounding).
 */
export interface Evidencia {
  span_a?: SpanA
  span_b?: SpanB
}
export interface Provenance {
  provider: Provider
  model: Model
  prompt_version: PromptVersion
  temperature: Temperature
  used_vision: UsedVision
  input_hash: InputHash
  timestamp: Timestamp
  latency_ms: LatencyMs
}
/**
 * Estado de revisión humana (§6).
 */
export interface Review {
  estado?: Estado
  comentario?: Comentario
  interpretacion_corregida?: InterpretacionCorregida
  revisor?: Revisor
  revisado_en?: RevisadoEn
}
