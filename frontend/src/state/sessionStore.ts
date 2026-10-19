export const SESSION_ID_STORAGE_KEY = 'health-consult-session-id';

export function getOrCreateSessionId(): string {
  let id = sessionStorage.getItem(SESSION_ID_STORAGE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_ID_STORAGE_KEY, id);
  }
  return id;
}

export function startNewSessionId(): string {
  const id = crypto.randomUUID();
  sessionStorage.setItem(SESSION_ID_STORAGE_KEY, id);
  return id;
}
