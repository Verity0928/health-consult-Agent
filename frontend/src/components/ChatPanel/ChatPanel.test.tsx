import { describe, it, expect, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel, MERGE_DEBOUNCE_MS } from './ChatPanel';
import * as client from '../../api/client';
import type { PipelineDebugInfo } from '../../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

// The debounce timer fires on a real setTimeout outside of any React event
// handler, so React doesn't know to flush the resulting state update unless
// this wait is itself wrapped in act().
function wait(ms: number) {
  return act(() => new Promise((resolve) => setTimeout(resolve, ms)));
}

it('renders a successful answer as a right/left message bubble pair', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({ reply: '含钾食物有香蕉橙子', status: 'answered', debug: emptyDebug });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '哪些食物富含钾');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100);
  await screen.findByText('含钾食物有香蕉橙子');
  expect(screen.getAllByTestId('message-bubble')).toHaveLength(2);
}, 10000);

it('shows a persistent footer disclaimer below the chat', () => {
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  expect(screen.getByTestId('disclaimer-footer')).toHaveTextContent(/技术演示/);
});

it('after a handoff, disables the input and offers to start a new consultation', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: '已为您转接人工', status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  });
  const onNewSession = vi.fn();
  const user = userEvent.setup();
  render(
    <ChatPanel
      sessionId="s1"
      llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }}
      onNewSession={onNewSession}
    />,
  );
  await user.type(screen.getByRole('textbox'), '我想自杀');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100);
  await screen.findByTestId('system-notice');
  expect(screen.getByRole('textbox')).toBeDisabled();
  await user.click(screen.getByRole('button', { name: '开始新咨询' }));
  expect(onNewSession).toHaveBeenCalledOnce();
}, 10000);

it('renders a handoff reply as a system notice, never as a message bubble', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '我想自杀');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100);
  const notice = await screen.findByTestId('system-notice');
  expect(notice).toHaveTextContent('已为您转接人工');
  const bubbles = screen.queryAllByTestId('message-bubble');
  expect(bubbles.some(b => b.textContent?.includes('已为您转接人工'))).toBe(false);
}, 10000);

it('the input stays usable while a request is in flight', async () => {
  let resolveChat: (value: unknown) => void = () => {};
  const chatPromise = new Promise((resolve) => { resolveChat = resolve; });
  vi.spyOn(client, 'chat').mockReturnValue(chatPromise as ReturnType<typeof client.chat>);
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '你好');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100); // the debounce fires and the request starts
  expect(screen.getByRole('textbox')).not.toBeDisabled();
  expect(screen.getByRole('button', { name: '发送' })).not.toBeDisabled();
  resolveChat({ reply: 'ok', status: 'answered', debug: emptyDebug });
  await screen.findByText('ok');
}, 10000);

it('combines messages sent within the debounce window into one request', async () => {
  const chatMock = vi.spyOn(client, 'chat').mockResolvedValue({ reply: '收到', status: 'answered', debug: emptyDebug });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '我最近');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await user.type(screen.getByRole('textbox'), '总是头疼');
  await user.click(screen.getByRole('button', { name: '发送' }));
  // both bubbles show immediately — before the merged reply even arrives
  expect(screen.getByText('我最近')).toBeInTheDocument();
  expect(screen.getByText('总是头疼')).toBeInTheDocument();
  expect(chatMock).not.toHaveBeenCalled();
  await wait(MERGE_DEBOUNCE_MS + 100);
  expect(chatMock).toHaveBeenCalledTimes(1);
  expect(chatMock).toHaveBeenCalledWith(expect.objectContaining({ message: '我最近\n总是头疼' }));
}, 10000);

it('a message sent while a request is in flight is sent as a follow-up once that request completes', async () => {
  let resolveFirst: (value: unknown) => void = () => {};
  const firstPromise = new Promise((resolve) => { resolveFirst = resolve; });
  const chatMock = vi.spyOn(client, 'chat')
    .mockReturnValueOnce(firstPromise as ReturnType<typeof client.chat>)
    .mockResolvedValueOnce({ reply: '第二条回复', status: 'answered', debug: emptyDebug });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '第一条');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await wait(MERGE_DEBOUNCE_MS + 100); // first request now in flight
  await user.type(screen.getByRole('textbox'), '第二条');
  await user.click(screen.getByRole('button', { name: '发送' }));
  resolveFirst({ reply: '第一条回复', status: 'answered', debug: emptyDebug });
  await screen.findByText('第一条回复');
  await wait(MERGE_DEBOUNCE_MS + 100); // the follow-up flush completes
  await screen.findByText('第二条回复');
  expect(chatMock).toHaveBeenCalledTimes(2);
  expect(chatMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ message: '第二条' }));
}, 10000);
