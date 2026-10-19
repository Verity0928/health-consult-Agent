import { describe, it, expect } from 'vitest';
import { chatReducer, initialChatState } from './chatReducer';
import type { PipelineDebugInfo, PipelineResult } from '../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('SEND_START appends a user message and sets pending', () => {
  const state = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '你好' });
  expect(state.messages).toEqual([{ id: '1', kind: 'user', content: '你好' }]);
  expect(state.pending).toBe(true);
});

it('SEND_SUCCESS with status "answered" appends an ai-kind message and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '你好' });
  const result: PipelineResult = { reply: '回答内容', status: 'answered', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'ai', content: '回答内容' });
  expect(state.pending).toBe(false);
  expect(state.lastDebug).toBe(result.debug);
});

it('SEND_SUCCESS with status "asked" appends an ai-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '吃点什么药' });
  const result: PipelineResult = { reply: '您方便说下具体是哪种药吗？', status: 'asked', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('ai');
});

it('SEND_SUCCESS with status "handoff" appends a system-kind message, never ai', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '我想自杀' });
  const result: PipelineResult = {
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_SUCCESS with status "closed" appends a system-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '没有了谢谢' });
  const result: PipelineResult = { reply: '好的，祝您身体健康～', status: 'closed', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_ERROR appends a system-kind message with the error text and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: 'x' });
  const state = chatReducer(started, { type: 'SEND_ERROR', id: '2', error: 'LLM 调用失败' });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'system', content: 'LLM 调用失败' });
  expect(state.pending).toBe(false);
});
