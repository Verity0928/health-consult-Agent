import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsModal } from './SettingsModal';
import * as settingsStore from '../../state/settingsStore';

it('renders nothing when open is false', () => {
  render(<SettingsModal open={false} onClose={() => {}} />);
  expect(screen.queryByText('模型设置')).not.toBeInTheDocument();
});

it('renders an optional Embedding Model field with a hint about the keyword fallback', () => {
  render(<SettingsModal open={true} onClose={() => {}} />);
  expect(screen.getByText('Embedding Model')).toBeInTheDocument();
  expect(screen.getByText(/回退到关键词检索/)).toBeInTheDocument();
});

it('includes embedding_model when saving', async () => {
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={() => {}} />);
  await user.type(screen.getByPlaceholderText('text-embedding-3-small'), 'my-embed-model');
  await user.click(screen.getByRole('button', { name: '保存' }));
  const saved = JSON.parse(sessionStorage.getItem('health-consult-llm-config') ?? '{}');
  expect(saved.embedding_model).toBe('my-embed-model');
});

it('a successful save closes the modal', async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={onClose} />);
  await user.click(screen.getByRole('button', { name: '保存' }));
  expect(onClose).toHaveBeenCalledOnce();
});

it('a failed save shows an error and keeps the modal open', async () => {
  vi.spyOn(settingsStore, 'saveLLMConfig').mockImplementation(() => {
    throw new Error('quota exceeded');
  });
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={onClose} />);
  await user.click(screen.getByRole('button', { name: '保存' }));
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByText('模型设置')).toBeVisible();
  expect(screen.getByText('保存失败，请检查浏览器存储设置后重试')).toBeVisible();
});

it('does not close on a backdrop click', async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={onClose} />);
  await user.click(screen.getByTestId('modal-backdrop'));
  expect(onClose).not.toHaveBeenCalled();
});

it('closes only when the close button is clicked', async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={onClose} />);
  await user.click(screen.getByRole('button', { name: '关闭设置' }));
  expect(onClose).toHaveBeenCalledOnce();
});
