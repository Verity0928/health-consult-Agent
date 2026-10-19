import { useEffect, useReducer, useState } from 'react';
import { chatReducer, initialChatState } from '../../state/chatReducer';
import { chat, ApiError } from '../../api/client';
import { MessageBubble } from './MessageBubble';
import { SystemNotice } from './SystemNotice';
import type { LLMConfig, PipelineDebugInfo } from '../../types';
import './ChatPanel.css';

interface ChatPanelProps {
  sessionId: string;
  llmConfig: LLMConfig;
  onDebugUpdate?: (debug: PipelineDebugInfo | null) => void;
}

export function ChatPanel({ sessionId, llmConfig, onDebugUpdate }: ChatPanelProps) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [draft, setDraft] = useState('');

  useEffect(() => {
    onDebugUpdate?.(state.lastDebug);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.lastDebug]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || state.pending) return;
    setDraft('');
    const userId = crypto.randomUUID();
    dispatch({ type: 'SEND_START', id: userId, message });
    try {
      const result = await chat({ session_id: sessionId, message, llm_config: llmConfig });
      dispatch({ type: 'SEND_SUCCESS', id: crypto.randomUUID(), result });
    } catch (err) {
      const text = err instanceof ApiError ? err.message : '网络连接失败，请稍后重试';
      dispatch({ type: 'SEND_ERROR', id: crypto.randomUUID(), error: text });
    }
  }

  return (
    <div className="hc-chat-panel">
      <div className="hc-chat-messages">
        {state.messages.map((m) => {
          if (m.kind === 'system') {
            return <SystemNotice key={m.id} content={m.content} />;
          }
          return (
            <MessageBubble
              key={m.id}
              content={m.content}
              align={m.kind === 'user' ? 'right' : 'left'}
            />
          );
        })}
      </div>
      <form className="hc-chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          role="textbox"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={state.pending}
        />
        <button type="submit" disabled={state.pending}>
          发送
        </button>
      </form>
      <p className="hc-disclaimer-footer" data-testid="disclaimer-footer">
        本应用是一个技术演示，内容基于演示用知识库生成，不构成医疗建议，请以线下就医为准。
      </p>
    </div>
  );
}
