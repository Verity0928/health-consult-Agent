import type { ChatTurnRequest, PipelineResult } from '../types';

export class ApiError extends Error {}

export async function health(): Promise<{ status: string }> {
  const res = await fetch('/api/health');
  return res.json();
}

export async function chat(request: ChatTurnRequest): Promise<PipelineResult> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? `请求失败（状态码 ${res.status}）`);
  }
  return res.json();
}
