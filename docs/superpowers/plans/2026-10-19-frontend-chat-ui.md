# Frontend Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React frontend for the health-consult agent demo — chat UI, AI-decision debug sidebar, settings modal, first-use disclaimer — wired to the already-shipped FastAPI backend (`POST /api/chat`, `GET /api/health`), served as one static bundle from the same FastAPI process.

**Architecture:** A single-page React app with no routing. State is split into small, independently-testable pieces: a pure reducer owns the conversation's message list and status-to-rendering rule (the one rule this plan exists to protect: `handoff`/`closed` render as a system notice, never a chat bubble); two tiny storage modules own `sessionStorage` reads/writes (LLM config, session id); presentational components are thin and verified live in the browser rather than unit-tested.

**Tech Stack:** React + TypeScript + Vite, Vitest + React Testing Library + `@testing-library/user-event` for the pieces that carry real logic, plain CSS with the locked design tokens (no CSS framework — the palette is five hex values, a framework buys nothing here).

**Spec:** [docs/PRD-健康咨询Agent开源Demo设计文档.md](../../PRD-健康咨询Agent开源Demo设计文档.md) §8 (前端设计), §2.1/§2.3 (安全声明/API Key处理) — plus the UI style agreed in chat on 2026-10-19 (see Global Constraints below; it supersedes §8's generic description with exact values).

**Not in this plan:** the simplified operations dashboard (design doc §8.4) — it needs session-log persistence and aggregation endpoints the backend doesn't have yet, so it isn't independently testable until that backend work exists. Build it as its own plan once logging is in place.

## Global Constraints

- Design tokens (confirmed in chat 2026-10-19, "石墨靛" palette): page/card background `#F6F6F8`; user bubble background `#E3E1EC`, text `#44426B`; AI bubble background `#FFFFFF` with a 0.5px border, text `#1A1D23`; accent/primary `#44426B`. Put these in `src/styles/tokens.css` as CSS custom properties; components reference the variables, never the raw hex.
- Chat bubbles are capsules: `border-radius: 999px`.
- `status === "handoff"` or `status === "closed"` must render as a centered system notice (hairline dividers + small gray text, no bubble background) — **never** as a message bubble. This is a corrected requirement from an earlier pass of this conversation; Task 5 and Task 6 each carry a regression test for it.
- The settings modal opens only via the gear icon in the top bar, and closes only via its own close (×) button — not by clicking the backdrop, not automatically after Save. "Save" and "test connection" are two separate buttons with independent outcomes.
- The debug sidebar is expanded by default; its collapse toggle lives in the top bar next to the gear icon, as a peer control (not attached to the sidebar's own edge).
- The LLM config (`base_url`/`api_key`/`model`) is stored in `sessionStorage`, not `localStorage` — per the design doc, it must not survive the browser being closed. The first-use disclaimer acknowledgment is the opposite: `localStorage`, so it is asked once ever, not once per session.
- Backend request/response shapes (from `backend/app/schemas.py`, already shipped): `ChatTurnRequest = { session_id: string; message: string; llm_config: LLMConfig }`, `LLMConfig = { base_url: string; api_key: string; model: string }`, `PipelineResult = { reply: string; status: "answered" | "asked" | "handoff" | "closed"; debug: PipelineDebugInfo }`, `PipelineDebugInfo = { route_scope, sub_type, population_status, hit_status, route_decision, handoff_reason: string | null; self_check: SelfCheckResult | null; retry_count: number }`, `SelfCheckResult = { compliance_pass, grounding_pass, disclaimer_pass, format_pass, overall_pass: boolean; violations: string[] }`. Mirror these exactly in `src/types.ts` (Task 2).
- Vite dev server proxies `/api/*` to `http://localhost:8000` so the browser never does a cross-origin request and the backend needs no CORS changes.

## Review Focus

- **Page refresh mid-ASK_ONCE:** the browser tab's `session_id` must survive a reload (it's read from `sessionStorage`, not regenerated), or the backend's in-memory session (topic_turns, ask_round, pending-fact-answer state) silently orphans and the next message starts a fresh, uncorrelated session. Covered in Task 4.
- **API key outliving the browser session:** a careless default of `localStorage` for the LLM config would leak the key far longer than the spec intends. Covered in Task 3.
- **HANDOFF/closed rendered as a chat bubble:** the exact mistake already corrected once in this conversation — a regression here reads as "the AI casually announced it's handing off," which breaks the "real doctor" feel the whole UI is built around. Covered in Task 5 (reducer) and Task 6 (component).
- **Settings modal closing itself:** backdrop-click-to-close or auto-close-on-save are both default behaviors most modal implementations reach for, and both contradict the explicit requirement. Covered in Task 9.
- **Connection-test failure shown as a generic error:** a user debugging a wrong API key needs the backend's actual 502 detail text ("LLM 调用失败，请检查 API 配置..."), not a swallowed, generic "something went wrong." Covered in Task 2 (`ApiError` carries the detail) and Task 9 (`testConnection` surfaces it).

---

## Task 1: Project scaffolding

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/setupTests.ts`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: a working Vite dev server (`npm run dev`) and a working Vitest runner (`npm test`); every later task's files live under `frontend/src/`.

- [ ] **Step 1: Verify Node/npm are available**

Run: `node --version && npm --version`
Expected: both print a version. If either is missing, stop and report it — do not attempt a workaround.

- [ ] **Step 2: Create `frontend/package.json`**

Dependencies: `react`, `react-dom`. Dev dependencies: `typescript`, `vite`, `@vitejs/plugin-react`, `vitest`, `jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `@types/react`, `@types/react-dom`. Scripts: `"dev": "vite"`, `"build": "vite build"`, `"test": "vitest run"`.

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
});
```

- [ ] **Step 4: Create `frontend/vitest.config.ts`**

Configure `environment: 'jsdom'`, `globals: true`, `setupFiles: ['./src/setupTests.ts']`.

- [ ] **Step 5: Create `frontend/src/setupTests.ts`**

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 6: Create `frontend/tsconfig.json` and `frontend/tsconfig.node.json`**

Standard Vite React-TS template configs (`target: ES2020`, `jsx: react-jsx`, `strict: true`).

- [ ] **Step 7: Create `frontend/index.html`**

Minimal HTML shell with `<div id="root"></div>` and `<script type="module" src="/src/main.tsx"></script>`; `<title>健康咨询 Agent</title>`.

- [ ] **Step 8: Create `frontend/src/styles/tokens.css`**

```css
:root {
  --hc-bg: #F6F6F8;
  --hc-user-bg: #E3E1EC;
  --hc-user-text: #44426B;
  --hc-ai-bg: #FFFFFF;
  --hc-ai-text: #1A1D23;
  --hc-accent: #44426B;
  --hc-border: rgba(26, 29, 35, 0.12);
  --hc-text-muted: #6B7280;
}
```

- [ ] **Step 9: Write the failing test for `App`**

```tsx
// frontend/src/App.test.tsx
import { render, screen } from '@testing-library/react';
import { it, expect } from 'vitest';
import App from './App';

it('renders the app title', () => {
  render(<App />);
  expect(screen.getByText('健康咨询 Agent')).toBeInTheDocument();
});
```

- [ ] **Step 10: Run test to verify it fails**

Run: `cd frontend && npm install && npm test`
Expected: FAIL (`App` not defined / module not found)

- [ ] **Step 11: Create `frontend/src/main.tsx` and `frontend/src/App.tsx`**

`main.tsx` imports `./styles/tokens.css` and renders `<App />` into `#root` via `createRoot`. `App.tsx` is a placeholder functional component rendering a heading with the text `健康咨询 Agent` — full composition happens in Task 11.

- [ ] **Step 12: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (1 test)

- [ ] **Step 13: Commit**

```bash
git add frontend/
git commit -m "chore(frontend): scaffold Vite + React + TS + Vitest project"
```

---

## Task 2: Shared types and API client

**Files:**
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces (in `types.ts`): `LLMConfig`, `ChatTurnRequest`, `ChatStatus`, `SelfCheckResult`, `PipelineDebugInfo`, `PipelineResult` — exact shapes from Global Constraints.
- Produces (in `client.ts`): `ApiError extends Error`; `health(): Promise<{ status: string }>`; `chat(request: ChatTurnRequest): Promise<PipelineResult>` — throws `ApiError` (message = backend's `detail` field, or a fallback) on a non-2xx response.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/api/client.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { chat, health, ApiError } from './client';
import type { ChatTurnRequest } from '../types';

beforeEach(() => vi.restoreAllMocks());

it('health returns the parsed status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) }));
  expect(await health()).toEqual({ status: 'ok' });
});

it('chat posts the request body to /api/chat and returns the parsed result', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({
      reply: 'hi', status: 'answered',
      debug: { route_scope: null, sub_type: null, population_status: null, hit_status: null,
                route_decision: null, handoff_reason: null, self_check: null, retry_count: 0 },
    }),
  });
  vi.stubGlobal('fetch', fetchMock);
  const request: ChatTurnRequest = {
    session_id: 's1', message: 'hello',
    llm_config: { base_url: 'https://x', api_key: 'k', model: 'm' },
  };
  const result = await chat(request);
  expect(fetchMock).toHaveBeenCalledWith('/api/chat', expect.objectContaining({
    method: 'POST', body: JSON.stringify(request),
  }));
  expect(result.status).toBe('answered');
});

it('chat throws ApiError with the backend detail message on a non-2xx response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false, status: 502, json: async () => ({ detail: 'LLM 调用失败，请检查 API 配置' }),
  }));
  await expect(chat({ session_id: 's1', message: 'x', llm_config: { base_url: 'a', api_key: 'b', model: 'c' } }))
    .rejects.toThrow('LLM 调用失败，请检查 API 配置');
});

it('chat falls back to a generic message when the error body has no detail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500, json: async () => ({}) }));
  await expect(chat({ session_id: 's1', message: 'x', llm_config: { base_url: 'a', api_key: 'b', model: 'c' } }))
    .rejects.toBeInstanceOf(ApiError);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- client`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `frontend/src/types.ts`**

As specified in Global Constraints — plain TypeScript interfaces/types, no runtime code.

- [ ] **Step 4: Implement `frontend/src/api/client.ts`**

```ts
export class ApiError extends Error {}

export async function health(): Promise<{ status: string }> {
  const res = await fetch('/api/health');
  return res.json();
}

export async function chat(request: ChatTurnRequest): Promise<PipelineResult> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(body.detail ?? `请求失败（状态码 ${res.status}）`);
  }
  return res.json();
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- client`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/api/
git commit -m "feat(frontend): shared types and API client"
```

---

## Task 3: Settings store (sessionStorage LLM config)

**Files:**
- Create: `frontend/src/state/settingsStore.ts`
- Test: `frontend/src/state/settingsStore.test.ts`

**Interfaces:**
- Consumes: `LLMConfig` (Task 2).
- Produces: `loadLLMConfig(): LLMConfig | null`; `saveLLMConfig(config: LLMConfig): void`; `clearLLMConfig(): void`. Storage key constant `LLM_CONFIG_STORAGE_KEY = 'health-consult-llm-config'`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/state/settingsStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { loadLLMConfig, saveLLMConfig, clearLLMConfig, LLM_CONFIG_STORAGE_KEY } from './settingsStore';

beforeEach(() => { sessionStorage.clear(); localStorage.clear(); });

it('returns null when nothing is saved', () => {
  expect(loadLLMConfig()).toBeNull();
});

it('round-trips a saved config', () => {
  const config = { base_url: 'https://api.openai.com/v1', api_key: 'sk-test', model: 'gpt-4o-mini' };
  saveLLMConfig(config);
  expect(loadLLMConfig()).toEqual(config);
});

it('uses sessionStorage, not localStorage, so the key does not survive a new browser session', () => {
  saveLLMConfig({ base_url: 'a', api_key: 'b', model: 'c' });
  expect(localStorage.getItem(LLM_CONFIG_STORAGE_KEY)).toBeNull();
  expect(sessionStorage.getItem(LLM_CONFIG_STORAGE_KEY)).not.toBeNull();
});

it('clearLLMConfig removes the saved config', () => {
  saveLLMConfig({ base_url: 'a', api_key: 'b', model: 'c' });
  clearLLMConfig();
  expect(loadLLMConfig()).toBeNull();
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- settingsStore`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `frontend/src/state/settingsStore.ts`**

`loadLLMConfig` reads `sessionStorage.getItem(LLM_CONFIG_STORAGE_KEY)`, `JSON.parse`s it, returns `null` on missing/invalid; `saveLLMConfig` `JSON.stringify`s into the same key; `clearLLMConfig` removes it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- settingsStore`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state/settingsStore.ts frontend/src/state/settingsStore.test.ts
git commit -m "feat(frontend): sessionStorage-backed LLM config store"
```

---

## Task 4: Session store (session id persistence)

**Files:**
- Create: `frontend/src/state/sessionStore.ts`
- Test: `frontend/src/state/sessionStore.test.ts`

**Interfaces:**
- Produces: `getOrCreateSessionId(): string`. Storage key constant `SESSION_ID_STORAGE_KEY = 'health-consult-session-id'`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/state/sessionStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest';
import { getOrCreateSessionId } from './sessionStore';

beforeEach(() => sessionStorage.clear());

it('creates a non-empty session id when none exists', () => {
  expect(getOrCreateSessionId()).toBeTruthy();
});

it('returns the same id on a later call in the same tab (survives a page reload)', () => {
  const first = getOrCreateSessionId();
  const second = getOrCreateSessionId();
  expect(second).toBe(first);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- sessionStore`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `frontend/src/state/sessionStore.ts`**

Reads `sessionStorage.getItem(SESSION_ID_STORAGE_KEY)`; if absent, generates one with `crypto.randomUUID()` and stores it; returns the id either way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- sessionStore`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state/sessionStore.ts frontend/src/state/sessionStore.test.ts
git commit -m "feat(frontend): sessionStorage-backed session id"
```

---

## Task 5: Chat reducer

**Files:**
- Create: `frontend/src/state/chatReducer.ts`
- Test: `frontend/src/state/chatReducer.test.ts`

**Interfaces:**
- Consumes: `PipelineResult`, `ChatStatus`, `PipelineDebugInfo` (Task 2).
- Produces: `ChatMessageView = { id: string; kind: 'user' | 'ai' | 'system'; content: string }`; `ChatState = { messages: ChatMessageView[]; pending: boolean; lastDebug: PipelineDebugInfo | null }`; `ChatAction = { type: 'SEND_START'; id: string; message: string } | { type: 'SEND_SUCCESS'; id: string; result: PipelineResult } | { type: 'SEND_ERROR'; id: string; error: string }`; `initialChatState: ChatState`; `chatReducer(state: ChatState, action: ChatAction): ChatState`.

This is where the handoff/closed-is-not-a-bubble rule lives: `SEND_SUCCESS` maps `result.status` to a message `kind` — `'handoff'` and `'closed'` become `kind: 'system'`; `'answered'` and `'asked'` become `kind: 'ai'`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/state/chatReducer.test.ts
import { describe, it, expect } from 'vitest';
import { chatReducer, initialChatState } from './chatReducer';
import type { PipelineDebugInfo, PipelineResult } from '../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('SEND_START appends a user message and sets pending', () => {
  const state = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '你好' });
  expect(state.messages).toEqual([{ id: '1', kind: 'user', content: '你好' }]);
  expect(state.pending).toBe(true);
});

it('SEND_SUCCESS with status "answered" appends an ai-kind message and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '你好' });
  const result: PipelineResult = { reply: '回答内容', status: 'answered', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'ai', content: '回答内容' });
  expect(state.pending).toBe(false);
  expect(state.lastDebug).toBe(result.debug);
});

it('SEND_SUCCESS with status "asked" appends an ai-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '吃点什么药' });
  const result: PipelineResult = { reply: '您方便说下具体是哪种药吗？', status: 'asked', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('ai');
});

it('SEND_SUCCESS with status "handoff" appends a system-kind message, never ai', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '我想自杀' });
  const result: PipelineResult = {
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_SUCCESS with status "closed" appends a system-kind message', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: '没有了谢谢' });
  const result: PipelineResult = { reply: '好的，祝您身体健康～', status: 'closed', debug: emptyDebug };
  const state = chatReducer(started, { type: 'SEND_SUCCESS', id: '2', result });
  expect(state.messages[1].kind).toBe('system');
});

it('SEND_ERROR appends a system-kind message with the error text and clears pending', () => {
  const started = chatReducer(initialChatState, { type: 'SEND_START', id: '1', message: 'x' });
  const state = chatReducer(started, { type: 'SEND_ERROR', id: '2', error: 'LLM 调用失败' });
  expect(state.messages[1]).toEqual({ id: '2', kind: 'system', content: 'LLM 调用失败' });
  expect(state.pending).toBe(false);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- chatReducer`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `frontend/src/state/chatReducer.ts`**

As specified in Interfaces; a `const NON_CONVERSATIONAL_STATUSES: ChatStatus[] = ['handoff', 'closed']` constant drives the `kind` decision in the `SEND_SUCCESS` branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- chatReducer`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/state/chatReducer.ts frontend/src/state/chatReducer.test.ts
git commit -m "feat(frontend): chat reducer — handoff/closed render as system, never ai"
```

---

## Task 6: Message bubble, system notice, and chat panel

**Files:**
- Create: `frontend/src/components/ChatPanel/MessageBubble.tsx`
- Create: `frontend/src/components/ChatPanel/SystemNotice.tsx`
- Create: `frontend/src/components/ChatPanel/ChatPanel.tsx`
- Create: `frontend/src/components/ChatPanel/ChatPanel.css`
- Test: `frontend/src/components/ChatPanel/ChatPanel.test.tsx`

**Interfaces:**
- Consumes: `chatReducer`, `initialChatState`, `ChatMessageView` (Task 5); `chat` (Task 2, mocked in the test); `LLMConfig` (Task 2).
- Produces: `MessageBubble(props: { content: string; align: 'left' | 'right' })` — renders `<div data-testid="message-bubble" data-align={align}>{content}</div>`, capsule-styled per the design tokens. `SystemNotice(props: { content: string })` — renders `<div data-testid="system-notice">{content}</div>` as a centered divider line, no bubble background. `ChatPanel(props: { sessionId: string; llmConfig: LLMConfig; onDebugUpdate?: (debug: PipelineDebugInfo | null) => void })` — owns a `useReducer(chatReducer, initialChatState)`, a text input, and a send button; on submit, dispatches `SEND_START`, calls `chat(...)`, dispatches `SEND_SUCCESS`/`SEND_ERROR`; renders `user`-kind messages right-aligned via `MessageBubble`, `ai`-kind left-aligned via `MessageBubble`, `system`-kind via `SystemNotice`. A `useEffect` keyed on `state.lastDebug` calls `onDebugUpdate?.(state.lastDebug)` whenever it changes — this is the only way `lastDebug` leaves `ChatPanel`, since `DebugSidebar` is a sibling in `App` (Task 11), not a child of `ChatPanel`, and has no other way to see it.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/ChatPanel/ChatPanel.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatPanel } from './ChatPanel';
import * as client from '../../api/client';
import type { PipelineDebugInfo } from '../../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('renders a successful answer as a right/left message bubble pair', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({ reply: '含钾食物有香蕉橙子', status: 'answered', debug: emptyDebug });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '哪些食物富含钾');
  await user.click(screen.getByRole('button', { name: '发送' }));
  await screen.findByText('含钾食物有香蕉橙子');
  expect(screen.getAllByTestId('message-bubble')).toHaveLength(2);
});

it('renders a handoff reply as a system notice, never as a message bubble', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: '您描述的情况需要医生进一步介入，已为您转接人工，请稍候。',
    status: 'handoff', debug: { ...emptyDebug, handoff_reason: 'red_flag' },
  });
  const user = userEvent.setup();
  render(<ChatPanel sessionId="s1" llmConfig={{ base_url: 'a', api_key: 'b', model: 'c' }} />);
  await user.type(screen.getByRole('textbox'), '我想自杀');
  await user.click(screen.getByRole('button', { name: '发送' }));
  const notice = await screen.findByTestId('system-notice');
  expect(notice).toHaveTextContent('已为您转接人工');
  const bubbles = screen.queryAllByTestId('message-bubble');
  expect(bubbles.some(b => b.textContent?.includes('已为您转接人工'))).toBe(false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- ChatPanel`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `MessageBubble.tsx`, `SystemNotice.tsx`, `ChatPanel.tsx`, `ChatPanel.css`**

`ChatPanel` renders a scrollable message list (mapping `state.messages` to `MessageBubble`/`SystemNotice` by `kind`), a text `<input>` (role `textbox`), and a `<button>我发送</button>`-equivalent labeled exactly `发送`; the submit handler is disabled while `state.pending` is true. `ChatPanel.css` applies the capsule radius and the token colors from `tokens.css` (`var(--hc-user-bg)` etc.) — align `user` bubbles right via `data-align="right"`, `ai` bubbles left via `data-align="left"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- ChatPanel`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatPanel/
git commit -m "feat(frontend): message bubbles, system notice, and chat panel"
```

---

## Task 7: Debug sidebar

**Files:**
- Create: `frontend/src/components/DebugSidebar/formatDebugInfo.ts`
- Create: `frontend/src/components/DebugSidebar/DebugSidebar.tsx`
- Create: `frontend/src/components/DebugSidebar/DebugSidebar.css`
- Test: `frontend/src/components/DebugSidebar/formatDebugInfo.test.ts`
- Test: `frontend/src/components/DebugSidebar/DebugSidebar.test.tsx`

**Interfaces:**
- Consumes: `PipelineDebugInfo`, `SelfCheckResult` (Task 2).
- Produces: `DebugRow = { label: string; value: string }`; `formatDebugInfo(debug: PipelineDebugInfo | null): DebugRow[]` — maps non-null scalar fields of `debug` to rows using the field name as `label` (e.g. `route_scope`), skips `null` fields, and when `self_check` is present flattens it into 4 rows labeled `质检·合规性` / `质检·溯源一致` / `质检·免责声明` / `质检·格式` with value `通过` / `不通过`. `DebugSidebar(props: { debug: PipelineDebugInfo | null; collapsed: boolean })` — renders nothing but a 0-width container when `collapsed` is true; otherwise renders a `AI 决策过程` heading and the rows from `formatDebugInfo(debug)`, with `route_decision`'s row rendered as a pill (reusing `var(--hc-user-bg)`/`var(--hc-user-text)`) instead of plain text.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/components/DebugSidebar/formatDebugInfo.test.ts
import { describe, it, expect } from 'vitest';
import { formatDebugInfo } from './formatDebugInfo';
import type { PipelineDebugInfo } from '../../types';

const emptyDebug: PipelineDebugInfo = {
  route_scope: null, sub_type: null, population_status: null, hit_status: null,
  route_decision: null, handoff_reason: null, self_check: null, retry_count: 0,
};

it('returns an empty array when debug is null', () => {
  expect(formatDebugInfo(null)).toEqual([]);
});

it('maps non-null scalar fields to rows, skipping nulls', () => {
  const rows = formatDebugInfo({
    ...emptyDebug, route_scope: 'in_scope', sub_type: 'lifestyle_education',
    hit_status: 'hit', route_decision: 'ANSWER',
  });
  expect(rows).toContainEqual({ label: 'route_scope', value: 'in_scope' });
  expect(rows).toContainEqual({ label: 'route_decision', value: 'ANSWER' });
  expect(rows.find(r => r.label === 'population_status')).toBeUndefined();
});

it('flattens self_check into 4 labeled pass/fail rows', () => {
  const rows = formatDebugInfo({
    ...emptyDebug,
    self_check: { compliance_pass: true, grounding_pass: false, disclaimer_pass: true, format_pass: true, overall_pass: false, violations: ['x'] },
  });
  expect(rows).toContainEqual({ label: '质检·溯源一致', value: '不通过' });
  expect(rows).toContainEqual({ label: '质检·合规性', value: '通过' });
});
```

```tsx
// frontend/src/components/DebugSidebar/DebugSidebar.test.tsx
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- DebugSidebar formatDebugInfo`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `formatDebugInfo.ts`, `DebugSidebar.tsx`, `DebugSidebar.css`**

As specified in Interfaces.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- DebugSidebar formatDebugInfo`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DebugSidebar/
git commit -m "feat(frontend): debug sidebar showing the AI decision chain"
```

---

## Task 8: Top bar

**Files:**
- Create: `frontend/src/components/TopBar/TopBar.tsx`
- Create: `frontend/src/components/TopBar/TopBar.css`
- Test: `frontend/src/components/TopBar/TopBar.test.tsx`

**Interfaces:**
- Produces: `TopBar(props: { sidebarCollapsed: boolean; onToggleSidebar: () => void; onOpenSettings: () => void })` — renders the app title, a sidebar-toggle icon button (accessible name `收起侧栏` when `sidebarCollapsed` is false, `展开侧栏` when true; `aria-expanded={!sidebarCollapsed}`) and a gear icon button (accessible name `模型设置`), both in the same row, calling `onToggleSidebar`/`onOpenSettings` respectively.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/components/TopBar/TopBar.test.tsx
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- TopBar`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `TopBar.tsx`, `TopBar.css`**

As specified in Interfaces; the toggle button's background uses `var(--hc-user-bg)` when `sidebarCollapsed` is true (pressed state), transparent otherwise.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- TopBar`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/TopBar/
git commit -m "feat(frontend): top bar with sidebar toggle and settings gear"
```

---

## Task 9: Settings modal

**Files:**
- Create: `frontend/src/components/SettingsModal/testConnection.ts`
- Create: `frontend/src/components/SettingsModal/SettingsModal.tsx`
- Create: `frontend/src/components/SettingsModal/SettingsModal.css`
- Test: `frontend/src/components/SettingsModal/testConnection.test.ts`
- Test: `frontend/src/components/SettingsModal/SettingsModal.test.tsx`

**Interfaces:**
- Consumes: `chat`, `ApiError` (Task 2); `LLMConfig` (Task 2); `saveLLMConfig`, `loadLLMConfig` (Task 3).
- Produces: `ConnectionTestResult = { ok: true } | { ok: false; message: string }`; `testConnection(config: LLMConfig): Promise<ConnectionTestResult>` — calls `chat({ session_id: 'connection-test', message: '连接测试', llm_config: config })`; on success returns `{ ok: true }`; on `ApiError` returns `{ ok: false, message: error.message }`; on any other thrown error returns `{ ok: false, message: '网络连接失败，请检查地址是否正确' }`.
- Produces: `SettingsModal(props: { open: boolean; onClose: () => void })` — hidden entirely when `open` is false; renders a backdrop (`data-testid="modal-backdrop"`, click does nothing) behind a card with Base URL / API Key / Model inputs (pre-filled from `loadLLMConfig()` when the modal opens), a `检测连接` button (calls `testConnection`, shows `检测中...` then the result message), a `保存` button (calls `saveLLMConfig`, shows an inline `已保存` confirmation, does **not** call `onClose`), and a close button with accessible name `关闭设置` that calls `onClose`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/components/SettingsModal/testConnection.test.ts
import { describe, it, expect, vi } from 'vitest';
import { testConnection } from './testConnection';
import * as client from '../../api/client';

it('returns ok when chat succeeds', async () => {
  vi.spyOn(client, 'chat').mockResolvedValue({
    reply: 'x', status: 'answered',
    debug: { route_scope: null, sub_type: null, population_status: null, hit_status: null,
              route_decision: null, handoff_reason: null, self_check: null, retry_count: 0 },
  });
  expect(await testConnection({ base_url: 'a', api_key: 'b', model: 'c' })).toEqual({ ok: true });
});

it('returns the backend error message on ApiError', async () => {
  vi.spyOn(client, 'chat').mockRejectedValue(new client.ApiError('LLM 调用失败，请检查 API 配置'));
  const result = await testConnection({ base_url: 'a', api_key: 'bad', model: 'c' });
  expect(result).toEqual({ ok: false, message: 'LLM 调用失败，请检查 API 配置' });
});

it('returns a generic message on a non-ApiError failure', async () => {
  vi.spyOn(client, 'chat').mockRejectedValue(new TypeError('Failed to fetch'));
  const result = await testConnection({ base_url: 'bad-url', api_key: 'b', model: 'c' });
  expect(result.ok).toBe(false);
});
```

```tsx
// frontend/src/components/SettingsModal/SettingsModal.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SettingsModal } from './SettingsModal';

it('renders nothing when open is false', () => {
  render(<SettingsModal open={false} onClose={() => {}} />);
  expect(screen.queryByText('模型设置')).not.toBeInTheDocument();
});

it('stays open after clicking Save — only the close button closes it', async () => {
  const user = userEvent.setup();
  render(<SettingsModal open={true} onClose={() => {}} />);
  await user.click(screen.getByRole('button', { name: '保存' }));
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm test -- testConnection SettingsModal`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `testConnection.ts`**

As specified in Interfaces; `try { await chat(...); return { ok: true }; } catch (e) { if (e instanceof ApiError) return { ok: false, message: e.message }; return { ok: false, message: '网络连接失败，请检查地址是否正确' }; }`.

- [ ] **Step 4: Implement `SettingsModal.tsx`, `SettingsModal.css`**

As specified in Interfaces; the backdrop's `onClick` is intentionally absent/no-op — do not wire it to `onClose`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm test -- testConnection SettingsModal`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/SettingsModal/
git commit -m "feat(frontend): settings modal with independent test-connection and save"
```

---

## Task 10: First-use disclaimer

**Files:**
- Create: `frontend/src/components/DisclaimerModal/DisclaimerModal.tsx`
- Create: `frontend/src/components/DisclaimerModal/DisclaimerModal.css`
- Test: `frontend/src/components/DisclaimerModal/DisclaimerModal.test.tsx`

**Interfaces:**
- Produces: `DISCLAIMER_ACK_STORAGE_KEY = 'health-consult-disclaimer-ack'`; `DisclaimerModal()` — a self-gating component with no props: on mount, checks `localStorage.getItem(DISCLAIMER_ACK_STORAGE_KEY)`; if not `'true'`, renders a modal containing text that includes the substring `技术演示` (spec §2.1's core disclaimer) and a button labeled `我理解`; clicking it sets `localStorage.setItem(DISCLAIMER_ACK_STORAGE_KEY, 'true')` and hides the modal. If already acknowledged, renders nothing.

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/components/DisclaimerModal/DisclaimerModal.test.tsx
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- DisclaimerModal`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `DisclaimerModal.tsx`, `DisclaimerModal.css`**

As specified in Interfaces; copy adapted from spec §2.1 ("这是一个技术架构演示项目，不是医疗产品。对话内容基于演示用的知识库数据生成，不构成医疗建议。").

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm test -- DisclaimerModal`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DisclaimerModal/
git commit -m "feat(frontend): first-use disclaimer gated on localStorage"
```

---

## Task 11: App composition, backend static serving, and browser verification

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `backend/main.py`
- Test: manual — Browser-tool walkthrough (no new automated test; every piece wired here already has its own unit coverage from Tasks 2–10)

**Interfaces:**
- Consumes: everything from Tasks 1–10.
- Produces: a complete `App` composing `DisclaimerModal` + `TopBar` + `ChatPanel` + `DebugSidebar` + `SettingsModal`; `backend/main.py` serving the built frontend.

`App` state: `sidebarCollapsed: boolean` (default `false`), `settingsOpen: boolean` (default `false`), `llmConfig: LLMConfig | null` (loaded via `loadLLMConfig()` on mount, re-read whenever `SettingsModal` closes so a just-saved config takes effect immediately), `debug: PipelineDebugInfo | null` (default `null`, updated via `ChatPanel`'s `onDebugUpdate` prop — this is how `DebugSidebar`, a sibling of `ChatPanel`, sees the latest decision chain). `sessionId` comes from `getOrCreateSessionId()` once, via `useState(() => getOrCreateSessionId())`. Layout: `TopBar` across the top; below it, `ChatPanel` and `DebugSidebar` side by side (`DebugSidebar` width collapses per `sidebarCollapsed`, and receives `debug={debug}`). If `llmConfig` is `null`, render a prompt ("请先点击右上角设置图标配置模型" ) instead of `ChatPanel` — do not render `ChatPanel` with a null config. `SettingsModal` is always mounted, controlled by `settingsOpen`.

- [ ] **Step 1: Implement `App.tsx`**

Wire the composition exactly as described above. No new test file — Task 1's existing `App.test.tsx` (`renders the app title`) must still pass unmodified; update it only if the title's markup location changed, not its assertion.

- [ ] **Step 2: Run the full frontend test suite**

Run: `cd frontend && npm test`
Expected: all tests from Tasks 1–10 PASS

- [ ] **Step 3: Build the frontend**

Run: `cd frontend && npm run build`
Expected: succeeds, produces `frontend/dist/`

- [ ] **Step 4: Modify `backend/main.py` to serve the built frontend**

Add, after the existing `/api/health` and `/api/chat` route definitions (so explicit API routes are registered before the catch-all mount):

```python
from pathlib import Path
from fastapi.staticfiles import StaticFiles

_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
```

The `is_dir()` guard matters: without it, `backend/tests/test_api.py` (which imports `main` directly) breaks on any machine/CI run where the frontend hasn't been built yet.

- [ ] **Step 5: Run the backend test suite to confirm it's unaffected**

Run: `cd backend && .venv/Scripts/python.exe -m pytest -v` (adjust venv path for the shell)
Expected: all existing backend tests still PASS, whether or not `frontend/dist` exists

- [ ] **Step 6: Browser verification**

Start the backend (`cd backend && .venv/Scripts/python.exe -m uvicorn main:app --reload`) and open it in the Browser tool. Using a placeholder API key (red-flag handling needs no real LLM call — `check_l0` short-circuits before any LLM is touched, so this exercises the full real HTTP stack: Vite-built static serving, the settings modal, and the backend):
  1. Confirm the disclaimer appears on first load and dismissing it persists (reload the page, confirm it does not reappear).
  2. Open settings via the gear icon; confirm it's a floating overlay, backdrop click does nothing, Save keeps it open, × closes it.
  3. Send a message containing a red-flag phrase (e.g. "我想自杀"); confirm the reply renders as a centered system notice, not a chat bubble, and the debug sidebar shows `handoff_reason: red_flag`.
  4. Toggle the sidebar collapsed/expanded via the top bar icon; confirm the icon's accessible name flips.
  Note in the report to the user that full ANSWER/ASK_ONCE visual verification against a *real* LLM response requires their own API key (already covered structurally by Task 6's mocked-`chat()` tests) — offer to re-run that walkthrough live if they provide one.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx backend/main.py
git commit -m "feat: wire frontend composition and serve the built app from FastAPI"
```
