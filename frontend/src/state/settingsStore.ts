import type { LLMConfig } from '../types';

export const LLM_CONFIG_STORAGE_KEY = 'health-consult-llm-config';

export function loadLLMConfig(): LLMConfig | null {
  const raw = sessionStorage.getItem(LLM_CONFIG_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as LLMConfig;
  } catch {
    return null;
  }
}

export function saveLLMConfig(config: LLMConfig): void {
  sessionStorage.setItem(LLM_CONFIG_STORAGE_KEY, JSON.stringify(config));
}

export function clearLLMConfig(): void {
  sessionStorage.removeItem(LLM_CONFIG_STORAGE_KEY);
}
