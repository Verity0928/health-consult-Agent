import { describe, it, expect, beforeEach } from 'vitest';
import { getOrCreateSessionId, startNewSessionId } from './sessionStore';

beforeEach(() => sessionStorage.clear());

it('creates a non-empty session id when none exists', () => {
  expect(getOrCreateSessionId()).toBeTruthy();
});

it('returns the same id on a later call in the same tab (survives a page reload)', () => {
  const first = getOrCreateSessionId();
  const second = getOrCreateSessionId();
  expect(second).toBe(first);
});

it('startNewSessionId replaces the stored id with a new one', () => {
  const first = getOrCreateSessionId();
  const fresh = startNewSessionId();
  expect(fresh).not.toBe(first);
  expect(getOrCreateSessionId()).toBe(fresh);
});
