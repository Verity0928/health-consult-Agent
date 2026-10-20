import { act, render, screen } from '@testing-library/react';
import { it, expect, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import App from './App';
import * as client from './api/client';
import { saveLLMConfig } from './state/settingsStore';
import { DISCLAIMER_ACK_STORAGE_KEY } from './components/DisclaimerModal/DisclaimerModal';
import { SESSION_ID_STORAGE_KEY } from './state/sessionStore';
import { MERGE_DEBOUNCE_MS } from './components/ChatPanel/ChatPanel';
import type { PipelineDebugInfo } from './types';

// The send debounce timer fires on a real setTimeout outside any React
// event handler, so this wait must be wrapped in act() for React to flush
// the resulting state update.
function wait(ms: number) {
  return act(() => new Promise((resolve) => setTimeout(resolve, ms)));
}

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

beforeEach(() => {
  sessionStorage.clear();
  localStorage.setItem(DISCLAIMER_ACK_STORAGE_KEY, 'true');
  saveLLMConfig({ base_url: 'a', api_key: 'b', model: 'c' });
});

it('renders the app title', () => {
  render(<App />);
  expect(screen.getByText('健康咨询 Agent')).toBeInTheDocument();
});

it('starting a new consultation after a handoff clears the chat and issues a fresh session id', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: '已为您转接人工', status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  });
  const user = userEvent.setup();
  render(<App />);
  const firstSessionId = sessionStorage.getItem(SESSION_ID_STORAGE_KEY);

  await user.type(screen.getByRole('textbox'), '我想自杀');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100);
  await screen.findByTestId('system-notice');

  await user.click(screen.getByRole('button', { name: '开始新咨询' }));

  expect(screen.queryByTestId('system-notice')).not.toBeInTheDocument();
  expect(screen.queryByText('我想自杀')).not.toBeInTheDocument();
  expect(sessionStorage.getItem(SESSION_ID_STORAGE_KEY)).not.toBe(firstSessionId);
});
