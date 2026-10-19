import type { PipelineDebugInfo } from '../../types';

export interface DebugRow {
  label: string;
  value: string;
}

const SCALAR_FIELDS: (keyof PipelineDebugInfo)[] = [
  'route_scope', 'sub_type', 'population_status', 'hit_status', 'route_decision', 'handoff_reason',
];

const SELF_CHECK_LABELS: { key: 'compliance_pass' | 'grounding_pass' | 'disclaimer_pass' | 'format_pass'; label: string }[] = [
  { key: 'compliance_pass', label: '质检·合规性' },
  { key: 'grounding_pass', label: '质检·溯源一致' },
  { key: 'disclaimer_pass', label: '质检·免责声明' },
  { key: 'format_pass', label: '质检·格式' },
];

export function formatDebugInfo(debug: PipelineDebugInfo | null): DebugRow[] {
  if (!debug) return [];

  const rows: DebugRow[] = [];
  for (const field of SCALAR_FIELDS) {
    const value = debug[field];
    if (value !== null && typeof value === 'string') {
      rows.push({ label: field, value });
    }
  }

  if (debug.self_check) {
    for (const { key, label } of SELF_CHECK_LABELS) {
      rows.push({ label, value: debug.self_check[key] ? '通过' : '不通过' });
    }
  }

  return rows;
}
