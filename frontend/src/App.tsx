import { useState } from 'react';
import { TopBar } from './components/TopBar/TopBar';
import { ChatPanel } from './components/ChatPanel/ChatPanel';
import { DebugSidebar } from './components/DebugSidebar/DebugSidebar';
import { SettingsModal } from './components/SettingsModal/SettingsModal';
import { DisclaimerModal } from './components/DisclaimerModal/DisclaimerModal';
import { loadLLMConfig } from './state/settingsStore';
import { getOrCreateSessionId, startNewSessionId } from './state/sessionStore';
import type { LLMConfig, PipelineDebugInfo } from './types';
import './App.css';

export default function App() {
  const [sessionId, setSessionId] = useState(() => getOrCreateSessionId());
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(() => loadLLMConfig());
  const [debug, setDebug] = useState<PipelineDebugInfo | null>(null);

  function handleCloseSettings() {
    setSettingsOpen(false);
    setLlmConfig(loadLLMConfig());
  }

  function handleNewSession() {
    setSessionId(startNewSessionId());
    setDebug(null);
  }

  return (
    <div className="hc-app">
      <DisclaimerModal />
      <TopBar
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={() => setSidebarCollapsed((c) => !c)}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <div className="hc-app-body">
        {llmConfig ? (
          <ChatPanel
            key={sessionId}
            sessionId={sessionId}
            llmConfig={llmConfig}
            onDebugUpdate={setDebug}
            onNewSession={handleNewSession}
          />
        ) : (
          <div className="hc-app-config-prompt">请先点击右上角设置图标配置模型</div>
        )}
        <DebugSidebar debug={debug} collapsed={sidebarCollapsed} />
      </div>
      <SettingsModal open={settingsOpen} onClose={handleCloseSettings} />
    </div>
  );
}
