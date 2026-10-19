import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsModal } from './SettingsModal';

it('renders nothing when open is false', () => {
  render(<SettingsModal open={false} onClose={() => {}} />);
  expect(screen.queryByText('模型设置')).not.toBeInTheDocument();
});

it('saving does not call onClose — only the close button closes it', async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={onClose} />);
  await user.click(screen.getByRole('button', { name: '保存' }));
  expect(onClose).not.toHaveBeenCalled();
  expect(screen.getByText('模型设置')).toBeVisible();
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
