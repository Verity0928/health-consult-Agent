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
  stuck: boolean;
}

export type ChatAction =
  | { type: 'ADD_USER_MESSAGE'; id: string; message: string }
  | { type: 'FLUSH_BEGIN' }
  | { type: 'SEND_SUCCESS'; id: string; result: PipelineResult }
  | { type: 'SEND_ERROR'; id: string; error: string };

export const initialChatState: ChatState = {
  messages: [], pending: false, lastDebug: null, stuck: false,
};

const NON_CONVERSATIONAL_STATUSES: ChatStatus[] = ['handoff', 'closed'];

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, { id: action.id, kind: 'user', content: action.message }],
      };
    case 'FLUSH_BEGIN':
      return { ...state, pending: true };
    case 'SEND_SUCCESS': {
      const stuck = NON_CONVERSATIONAL_STATUSES.includes(action.result.status);
      const kind = stuck ? 'system' : 'ai';
      return {
        messages: [...state.messages, { id: action.id, kind, content: action.result.reply }],
        pending: false,
        lastDebug: action.result.debug,
        stuck,
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
