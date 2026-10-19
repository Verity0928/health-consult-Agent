import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel } from './ChatPanel';
import * as client from '../../api/client';
import type { PipelineDebugInfo } from '../../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('renders a successful answer as a right/left message bubble pair', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({ reply: '含钾食物有香蕉橙子', status: 'answered', debug: emptyDebug });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '哪些食物富含钾');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await screen.findByText('含钾食物有香蕉橙子');
  expect(screen.getAllByTestId('message-bubble')).toHaveLength(2);
});

it('renders a handoff reply as a system notice, never as a message bubble', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '我想自杀');
  await user.click(screen.getByRole('button', { name: '发送' }));
  const notice = await screen.findByTestId('system-notice');
  expect(notice).toHaveTextContent('已为您转接人工');
  const bubbles = screen.queryAllByTestId('message-bubble');
  expect(bubbles.some(b => b.textContent?.includes('已为您转接人工'))).toBe(false);
});
