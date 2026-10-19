import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TopBar } from './TopBar';

it('calls onToggleSidebar when the sidebar toggle is clicked', async () => {
  const onToggleSidebar = vi.fn();
  const user = userEvent.setup();
  render(<TopBar sidebarCollapsed={false} onToggleSidebar={onToggleSidebar} onOpenSettings={() => {}} />);
  await user.click(screen.getByRole('button', { name: '收起侧栏' }));
  expect(onToggleSidebar).toHaveBeenCalledOnce();
});

it('calls onOpenSettings when the gear button is clicked', async () => {
  const onOpenSettings = vi.fn();
  const user = userEvent.setup();
  render(<TopBar sidebarCollapsed={false} onToggleSidebar={() => {}} onOpenSettings={onOpenSettings} />);
  await user.click(screen.getByRole('button', { name: '模型设置' }));
  expect(onOpenSettings).toHaveBeenCalledOnce();
});

it('labels the sidebar toggle "展开侧栏" when already collapsed', () => {
  render(<TopBar sidebarCollapsed={true} onToggleSidebar={() => {}} onOpenSettings={() => {}} />);
  expect(screen.getByRole('button', { name: '展开侧栏' })).toBeInTheDocument();
});
