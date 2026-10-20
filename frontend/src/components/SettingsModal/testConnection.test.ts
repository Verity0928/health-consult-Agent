import { describe, it, expect, vi } from 'vitest';
import { testConnection } from './testConnection';
import * as client from '../../api/client';

it('returns ok when pingConnection succeeds', async () => {
  vi.spyOn(client, 'pingConnection').mockResolvedValue(undefined);
  expect(await testConnection({ base_url: 'a', api_key: 'b', model: 'c' })).toEqual({ ok: true });
});

it('returns the backend error message on ApiError', async () => {
  vi.spyOn(client, 'pingConnection').mockRejectedValue(new client.ApiError('LLM 调用失败，请检查 API 配置'));
  const result = await testConnection({ base_url: 'a', api_key: 'bad', model: 'c' });
  expect(result).toEqual({ ok: false, message: 'LLM 调用失败，请检查 API 配置' });
});

it('returns a generic message on a non-ApiError failure', async () => {
  vi.spyOn(client, 'pingConnection').mockRejectedValue(new TypeError('Failed to fetch'));
  const result = await testConnection({ base_url: 'bad-url', api_key: 'b', model: 'c' });
  expect(result.ok).toBe(false);
});
