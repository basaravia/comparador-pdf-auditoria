// Regenera frontend/src/types/change_unit.ts desde schemas/change_unit.schema.json.
//
// Fuente de verdad: el modelo Pydantic (backend/src/comparador/schemas/change_unit.py).
// Este script solo traduce JSON Schema -> TS. Ver CLAUDE.md invariante #5:
// todo cambio al esquema regenera los tipos TS en el mismo commit.
//
// Uso: node frontend/scripts/generate-types.mjs

import { compile } from 'json-schema-to-typescript'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = resolve(__dirname, '..', '..')
const SCHEMA_PATH = resolve(REPO_ROOT, 'schemas', 'change_unit.schema.json')
const OUTPUT_PATH = resolve(REPO_ROOT, 'frontend', 'src', 'types', 'change_unit.ts')

const HEADER = `/**
 * Generado desde schemas/change_unit.schema.json — NO EDITAR A MANO.
 * Fuente de verdad: backend/src/comparador/schemas/change_unit.py
 * Regenerar con: node frontend/scripts/generate-types.mjs
 */

`

// json-schema-to-typescript no resuelve bien "prefixItems" (JSON Schema
// 2020-12, lo que emite Pydantic v2 para tuplas como bbox [x0,y0,x1,y1]).
// Lo reescribimos a la sintaxis de tupla draft-07 ("items": [...]) que sí
// soporta, para que bbox_a/page_size_a salgan tipados como number, no unknown.
function toDraft07Tuples(node) {
  if (Array.isArray(node)) return node.map(toDraft07Tuples)
  if (node === null || typeof node !== 'object') return node

  const out = {}
  for (const [key, value] of Object.entries(node)) {
    out[key] = toDraft07Tuples(value)
  }
  if (Array.isArray(out.prefixItems)) {
    out.items = out.prefixItems
    out.additionalItems = false
    delete out.prefixItems
  }
  return out
}

async function main() {
  const rawSchema = JSON.parse(readFileSync(SCHEMA_PATH, 'utf-8'))
  const schema = toDraft07Tuples(rawSchema)
  const ts = await compile(schema, 'ChangeUnit', {
    additionalProperties: false,
    style: { semi: false, singleQuote: true },
    bannerComment: '',
  })

  mkdirSync(dirname(OUTPUT_PATH), { recursive: true })
  writeFileSync(OUTPUT_PATH, HEADER + ts)
  console.log(`wrote ${OUTPUT_PATH.replace(REPO_ROOT + '/', '')}`)
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
