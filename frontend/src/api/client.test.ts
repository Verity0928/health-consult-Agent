import { describe, it, expect, vi, beforeEach } from 'vitest';
import { chat, health, pingConnection, ApiError } from './client';
import type { ChatTurnRequest } from '../types';

beforeEach(() => vi.restoreAllMocks());

it('health returns the parsed status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));
  expect(await health()).toEqual({ status: 'ok' });
});

it('chat posts the request body to /api/chat and returns the parsed result', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      reply: 'hi', status: 'answered',
      debug: { route_scope: null, sub_type: null, population_status: null, hit_status: null,
                route_decision: null, handoff_reason: null, self_check: null, retry_count: 0 },
    }),
  });
  vi.stubGlobal('fetch', fetchMock);
  const request: ChatTurnRequest = {
    session_id: 's1', message: 'hello',
    llm_config: { base_url: 'https://x', api_key: 'k', model: 'm' },
  };
  const result = await chat(request);
  expect(fetchMock).toHaveBeenCalledWith('/api/chat', expect.objectContaining({
    method: 'POST', body: JSON.stringify(request),
  }));
  expect(result.status).toBe('answered');
});

it('chat throws ApiError with the backend detail message on a non-2xx response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 502, json: async () => ({ detail: 'LLM 调用失败，请检查 API 配置' }),
  }));
  await expect(chat({ session_id: 's1', message: 'x', llm_config: { base_url: 'a', api_key: 'b', model: 'c' } }))
    .rejects.toThrow('LLM 调用失败，请检查 API 配置');
});

it('chat falls back to a generic message when the error body has no detail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
  await expect(chat({ session_id: 's1', message: 'x', llm_config: { base_url: 'a', api_key: 'b', model: 'c' } }))
    .rejects.toBeInstanceOf(ApiError);
});

it('pingConnection posts the llm config to /api/test-connection', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) });
  vi.stubGlobal('fetch', fetchMock);
  const config = { base_url: 'https://x', api_key: 'k', model: 'm' };
  await pingConnection(config);
  expect(fetchMock).toHaveBeenCalledWith('/api/test-connection', expect.objectContaining({
    method: 'POST', body: JSON.stringify(config),
  }));
});

it('pingConnection throws ApiError with the backend detail message on a non-2xx response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 502, json: async () => ({ detail: 'LLM 调用失败，请检查 API 配置' }),
  }));
  await expect(pingConnection({ base_url: 'a', api_key: 'b', model: 'c' }))
    .rejects.toThrow('LLM 调用失败，请检查 API 配置');
});
