import { formatDebugInfo } from './formatDebugInfo';
import type { PipelineDebugInfo } from '../../types';
import './DebugSidebar.css';

interface DebugSidebarProps {
  debug: PipelineDebugInfo | null;
  collapsed: boolean;
}

export function DebugSidebar({ debug, collapsed }: DebugSidebarProps) {
  if (collapsed) {
    return <div className="hc-debug-sidebar hc-debug-sidebar-collapsed" />;
  }

  const rows = formatDebugInfo(debug);

  return (
    <div className="hc-debug-sidebar">
      <p className="hc-debug-sidebar-title">AI 决策过程</p>
      <div className="hc-debug-sidebar-rows">
        {rows.map((row) => (
          <div className="hc-debug-sidebar-row" key={row.label}>
            <span className="hc-debug-sidebar-label">{row.label}</span>
            {row.label === 'route_decision' ? (
              <span className="hc-debug-sidebar-pill">{row.value}</span>
            ) : (
              <span className="hc-debug-sidebar-value">{row.value}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
