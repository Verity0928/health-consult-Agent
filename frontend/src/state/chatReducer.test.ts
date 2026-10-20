import { describe, it, expect } from 'vitest';
import { chatReducer, initialChatState } from './chatReducer';
import type { PipelineDebugInfo, PipelineResult } from '../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('ADD_USER_MESSAGE appends a user message without setting pending', () => {
  const state = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '你好' });
  expect(state.messages).toEqual([{ id: '1', kind: 'user', content: '你好' }]);
  expect(state.pending).toBe(false);
});

it('ADD_USER_MESSAGE can append multiple messages while nothing is in flight', () => {
  let state = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '我最近' });
  state = chatReducer(state, { type: 'ADD_USER_MESSAGE', id: '2', message: '总是头疼' });
  expect(state.messages).toEqual([
    { id: '1', kind: 'user', content: '我最近' },
    { id: '2', kind: 'user', content: '总是头疼' },
  ]);
  expect(state.pending).toBe(false);
});

it('FLUSH_BEGIN sets pending without appending a message', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '你好' });
  const state = chatReducer(started, { type: 'FLUSH_BEGIN' });
  expect(state.pending).toBe(true);
  expect(state.messages).toHaveLength(1);
});

it('SEND_SUCCESS with status "answered" appends an ai-kind message and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '你好' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = { reply: '回答内容', status: 'answered', debug: emptyDebug };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'ai', content: '回答内容' });
  expect(state.pending).toBe(false);
  expect(state.lastDebug).toBe(result.debug);
});

it('SEND_SUCCESS with status "asked" appends an ai-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '吃点什么药' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = { reply: '您方便说下具体是哪种药吗？', status: 'asked', debug: emptyDebug };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('ai');
});

it('SEND_SUCCESS with status "handoff" appends a system-kind message, never ai', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '我想自杀' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = {
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_SUCCESS with status "handoff" or "closed" marks the chat stuck', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '我想自杀' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = {
    reply: '已为您转接人工', status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.stuck).toBe(true);
});

it('SEND_SUCCESS with status "answered" leaves the chat not stuck', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '你好' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = { reply: '回答内容', status: 'answered', debug: emptyDebug };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.stuck).toBe(false);
});

it('SEND_SUCCESS with status "closed" appends a system-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: '没有了谢谢' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const result: PipelineResult = { reply: '好的，祝您身体健康～', status: 'closed', debug: emptyDebug };
  const state = chatReducer(flushed, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_ERROR appends a system-kind message with the error text and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'ADD_USER_MESSAGE', id: '1', message: 'x' });
  const flushed = chatReducer(started, { type: 'FLUSH_BEGIN' });
  const state = chatReducer(flushed, { type: 'SEND_ERROR', id: '2', error: 'LLM 调用失败' });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'system', content: 'LLM 调用失败' });
  expect(state.pending).toBe(false);
});
