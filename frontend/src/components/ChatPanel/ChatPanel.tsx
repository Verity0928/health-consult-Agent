import { useEffect, useReducer, useRef, useState } from 'react';
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
  onNewSession?: () => void;
}

// Messages sent within this window of each other are combined into a
// single turn, like a real person splitting one thought across a few
// texts instead of each fragment getting answered on its own.
export const MERGE_DEBOUNCE_MS = 1500;

export function ChatPanel({ sessionId, llmConfig, onDebugUpdate, onNewSession }: ChatPanelProps) {
  const [state, dispatch] = useReducer(chatReducer, initialChatState);
  const [draft, setDraft] = useState('');
  const bufferRef = useRef<string[]>([]);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingRef = useRef(false);

  useEffect(() => {
    onDebugUpdate?.(state.lastDebug);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.lastDebug]);

  useEffect(() => {
    pendingRef.current = state.pending;
  }, [state.pending]);

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  async function flush() {
    if (pendingRef.current || bufferRef.current.length === 0) return;
    const combined = bufferRef.current.join('\n');
    bufferRef.current = [];
    pendingRef.current = true;
    dispatch({ type: 'FLUSH_BEGIN' });
    try {
      const result = await chat({ session_id: sessionId, message: combined, llm_config: llmConfig });
      dispatch({ type: 'SEND_SUCCESS', id: crypto.randomUUID(), result });
    } catch (err) {
      const text = err instanceof ApiError ? err.message : '网络连接失败，请稍后重试';
      dispatch({ type: 'SEND_ERROR', id: crypto.randomUUID(), error: text });
    } finally {
      pendingRef.current = false;
      if (bufferRef.current.length > 0) {
        flush();
      }
    }
  }

  function scheduleFlush() {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      timerRef.current = null;
      flush();
    }, MERGE_DEBOUNCE_MS);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const message = draft.trim();
    if (!message || state.stuck) return;
    setDraft('');
    dispatch({ type: 'ADD_USER_MESSAGE', id: crypto.randomUUID(), message });
    bufferRef.current.push(message);
    scheduleFlush();
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
      {state.stuck && (
        <div className="hc-chat-stuck-bar">
          <button type="button" onClick={() => onNewSession?.()}>
            开始新咨询
          </button>
        </div>
      )}
      <form className="hc-chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          role="textbox"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={state.stuck}
        />
        <button type="submit" disabled={state.stuck}>
          发送
        </button>
      </form>
      <p className="hc-disclaimer-footer" data-testid="disclaimer-footer">
        本应用是一个技术演示，内容基于演示用知识库生成，不构成医疗建议，请以线下就医为准。
      </p>
    </div>
  );
}
