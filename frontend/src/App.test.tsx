import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import App from './App';

it('renders the app title', () => {
  render(<App />);
  expect(screen.getByText('健康咨询 Agent')).toBeInTheDocument();
});
