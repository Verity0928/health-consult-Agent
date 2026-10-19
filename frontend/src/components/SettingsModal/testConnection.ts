import { chat, ApiError } from '../../api/client';
import type { LLMConfig } from '../../types';

export type ConnectionTestResult = { ok: true } | { ok: false; message: string };

export async function testConnection(config: LLMConfig): Promise<ConnectionTestResult> {
  try {
    await chat({ session_id: 'connection-test', message: '连接测试', llm_config: config });
    return { ok: true };
  } catch (err) {
    if (err instanceof ApiError) {
      return { ok: false, message: err.message };
    }
    return { ok: false, message: '网络连接失败，请检查地址是否正确' };
  }
}
