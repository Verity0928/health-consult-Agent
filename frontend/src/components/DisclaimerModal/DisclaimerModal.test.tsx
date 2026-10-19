import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DisclaimerModal, DISCLAIMER_ACK_STORAGE_KEY } from './DisclaimerModal';

beforeEach(() => localStorage.clear());

it('shows the disclaimer when not yet acknowledged', () => {
  render(<DisclaimerModal />);
  expect(screen.getByText(/技术演示/)).toBeVisible();
});

it('hides itself and remembers acknowledgment after the user confirms', async () => {
  const user = userEvent.setup();
  render(<DisclaimerModal />);
  await user.click(screen.getByRole('button', { name: '我理解' }));
  expect(screen.queryByText(/技术演示/)).not.toBeInTheDocument();
  expect(localStorage.getItem(DISCLAIMER_ACK_STORAGE_KEY)).toBe('true');
});

it('does not show again once already acknowledged', () => {
  localStorage.setItem(DISCLAIMER_ACK_STORAGE_KEY, 'true');
  render(<DisclaimerModal />);
  expect(screen.queryByText(/技术演示/)).not.toBeInTheDocument();
});
