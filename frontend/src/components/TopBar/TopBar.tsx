import './TopBar.css';

interface TopBarProps {
  sidebarCollapsed: boolean;
  onToggleSidebar: () => void;
  onOpenSettings: () => void;
}

export function TopBar({ sidebarCollapsed, onToggleSidebar, onOpenSettings }: TopBarProps) {
  const toggleLabel = sidebarCollapsed ? '展开侧栏' : '收起侧栏';

  return (
    <div className="hc-top-bar">
      <span className="hc-top-bar-title">健康咨询 Agent</span>
      <div className="hc-top-bar-actions">
        <button
          type="button"
          aria-label={toggleLabel}
          aria-expanded={!sidebarCollapsed}
          className="hc-top-bar-icon-button"
          style={{ background: sidebarCollapsed ? 'var(--hc-user-bg)' : 'transparent' }}
          onClick={onToggleSidebar}
        >
          <span aria-hidden="true">▤</span>
        </button>
        <button
          type="button"
          aria-label="模型设置"
          className="hc-top-bar-icon-button"
          onClick={onOpenSettings}
        >
          <span aria-hidden="true">⚙</span>
        </button>
      </div>
    </div>
  );
}
