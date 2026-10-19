import { describe, it, expect } from 'vitest';
import { formatDebugInfo } from './formatDebugInfo';
import type { PipelineDebugInfo } from '../../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('returns an empty array when debug is null', () => {
  expect(formatDebugInfo(null)).toEqual([]);
});

it('maps non-null scalar fields to rows, skipping nulls', () => {
  const rows = formatDebugInfo({
    ...emptyDebug, route_scope: 'in_scope', sub_type: 'lifestyle_education',
    hit_status: 'hit', route_decision: 'ANSWER',
  });
  expect(rows).toContainEqual({ label: 'route_scope', value: 'in_scope' });
  expect(rows).toContainEqual({ label: 'route_decision', value: 'ANSWER' });
  expect(rows.find(r => r.label === 'population_status')).toBeUndefined();
});

it('flattens self_check into 4 labeled pass/fail rows', () => {
  const rows = formatDebugInfo({
    ...emptyDebug,
    self_check: { compliance_pass: true, grounding_pass: false, disclaimer_pass: true, format_pass: true, overall_pass: false, violations: ['x'] },
  });
  expect(rows).toContainEqual({ label: '质检·溯源一致', value: '不通过' });
  expect(rows).toContainEqual({ label: '质检·合规性', value: '通过' });
});
