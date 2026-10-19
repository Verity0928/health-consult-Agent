import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { DebugSidebar } from './DebugSidebar';

it('shows its content when not collapsed', () => {
  render(<DebugSidebar debug={null} collapsed={false} />);
  expect(screen.getByText('AI 决策过程')).toBeVisible();
});

it('hides its content when collapsed', () => {
  render(<DebugSidebar debug={null} collapsed={true} />);
  expect(screen.queryByText('AI 决策过程')).not.toBeInTheDocument();
});
