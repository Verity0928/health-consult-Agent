import type { ChatStatus, PipelineDebugInfo, PipelineResult } from '../types';

export interface ChatMessageView {
  id: string;
  kind: 'user' | 'ai' | 'system';
  content: string;
}

export interface ChatState {
  messages: ChatMessageView[];
  pending: boolean;
  lastDebug: PipelineDebugInfo | null;
}

export type ChatAction =
  | { type: 'SEND_START'; id: string; message: string }
  | { type: 'SEND_SUCCESS'; id: string; result: PipelineResult }
  | { type: 'SEND_ERROR'; id: string; error: string };

export const initialChatState: ChatState = { messages: [], pending: false, lastDebug: null };

const NON_CONVERSATIONAL_STATUSES: ChatStatus[] = ['handoff', 'closed'];

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SEND_START':
      return {
        ...state,
        messages: [...state.messages, { id: action.id, kind: 'user', content: action.message }],
        pending: true,
      };
    case 'SEND_SUCCESS': {
      const kind = NON_CONVERSATIONAL_STATUSES.includes(action.result.status) ? 'system' : 'ai';
      return {
        messages: [...state.messages, { id: action.id, kind, content: action.result.reply }],
        pending: false,
        lastDebug: action.result.debug,
      };
    }
    case 'SEND_ERROR':
      return {
        ...state,
        messages: [...state.messages, { id: action.id, kind: 'system', content: action.error }],
        pending: false,
      };
    default:
      return state;
  }
}
