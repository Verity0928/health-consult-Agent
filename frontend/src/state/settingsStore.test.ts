import { describe, it, expect, beforeEach } from 'vitest';
import { loadLLMConfig, saveLLMConfig, clearLLMConfig, LLM_CONFIG_STORAGE_KEY } from './settingsStore';

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });

it('returns null when nothing is saved', () => {
  expect(loadLLMConfig()).toBeNull();
});

it('round-trips a saved config', () => {
  const config = { base_url: 'https://api.openai.com/v1', api_key: 'sk-test', model: 'gpt-4o-mini' };
  saveLLMConfig(config);
  expect(loadLLMConfig()).toEqual(config);
});

it('uses sessionStorage, not localStorage, so the key does not survive a new browser session', () => {
  saveLLMConfig({ base_url: 'a', api_key: 'b', model: 'c' });
  expect(localStorage.getItem(LLM_CONFIG_STORAGE_KEY)).toBeNull();
  expect(sessionStorage.getItem(LLM_CONFIG_STORAGE_KEY)).not.toBeNull();
});

it('clearLLMConfig removes the saved config', () => {
  saveLLMConfig({ base_url: 'a', api_key: 'b', model: 'c' });
  clearLLMConfig();
  expect(loadLLMConfig()).toBeNull();
});
