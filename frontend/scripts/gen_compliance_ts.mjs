#!/usr/bin/env node
// 从 shared/compliance.yaml 生成 src/data/questionnaires.ts + solutions.ts
// 改合规规则后运行: npm run gen:compliance (vite build 前自动运行 prebuild)
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import yaml from 'js-yaml'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const sharedPath = resolve(scriptDir, '../../shared/compliance.yaml')
const outDir = resolve(scriptDir, '../src/data')
const data = yaml.load(readFileSync(sharedPath, 'utf-8'))

const HEADER =
  '// DO NOT EDIT - generated from shared/compliance.yaml by scripts/gen_compliance_ts.mjs'

// ── questionnaires.ts ──────────────────────────────────────────
const bone = data.questionnaires.find((q) => q.id === 'bone_density_v1')
const leg = data.questionnaires.find((q) => q.id === 'leg_pain_v1')
const qTs = `${HEADER}
// 量表定义 (单一事实源 shared/compliance.yaml)

export type RiskLevel = 'low' | 'medium' | 'high' | 'urgent'

export type QuestionOption = {
  key: string
  label: string
  weight: number
}

export type Question = {
  id: string
  text: string
  type: 'single' | 'multi'
  options: QuestionOption[]
  tag: string
}

export type Questionnaire = {
  id: string
  scene: 'report' | 'symptom' | 'product'
  title: string
  description: string
  questions: Question[]
}

export const BONE_DENSITY_QUESTIONNAIRE: Questionnaire = ${JSON.stringify(bone, null, 2)}

export const LEG_PAIN_QUESTIONNAIRE: Questionnaire = ${JSON.stringify(leg, null, 2)}

export const ALL_QUESTIONNAIRES: Questionnaire[] = [
  BONE_DENSITY_QUESTIONNAIRE,
  LEG_PAIN_QUESTIONNAIRE,
]

export function getQuestionnaireById(id: string): Questionnaire | undefined {
  return ALL_QUESTIONNAIRES.find((q) => q.id === id)
}
`
writeFileSync(resolve(outDir, 'questionnaires.ts'), qTs)

// ── solutions.ts ───────────────────────────────────────────────
const boneSols = Object.fromEntries(
  data.solutions.filter((s) => s.scene === 'report').map((s) => [s.tag, s]),
)
const legSols = Object.fromEntries(
  data.solutions.filter((s) => s.scene === 'symptom').map((s) => [s.tag, s]),
)
const sTs = `${HEADER}
// 方案模板 (单一事实源 shared/compliance.yaml)

import type { RiskLevel } from './questionnaires'

export type SolutionSection = {
  icon: string
  title: string
  content: string
}

export type Solution = {
  id: string
  scene: 'report' | 'symptom' | 'product'
  tag: string
  title: string
  riskLevel: RiskLevel
  department: string
  oneLineConclusion: string
  lifestyle: SolutionSection[]
  nutrition: SolutionSection[]
  alert: SolutionSection[]
}

export const BONE_DENSITY_SOLUTIONS: Record<string, Solution> = ${JSON.stringify(boneSols, null, 2)}

export const LEG_PAIN_SOLUTIONS: Record<string, Solution> = ${JSON.stringify(legSols, null, 2)}

export function getSolution(scene: 'report' | 'symptom', tag: string): Solution | undefined {
  if (scene === 'report') return BONE_DENSITY_SOLUTIONS[tag]
  if (scene === 'symptom') return LEG_PAIN_SOLUTIONS[tag]
  return undefined
}

export function listSolutions(scene: 'report' | 'symptom'): Solution[] {
  if (scene === 'report') return Object.values(BONE_DENSITY_SOLUTIONS)
  if (scene === 'symptom') return Object.values(LEG_PAIN_SOLUTIONS)
  return []
}
`
writeFileSync(resolve(outDir, 'solutions.ts'), sTs)

console.log('generated questionnaires.ts + solutions.ts from shared/compliance.yaml')
