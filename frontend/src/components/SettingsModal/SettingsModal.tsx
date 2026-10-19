import { useEffect, useState } from 'react';
import { loadLLMConfig, saveLLMConfig } from '../../state/settingsStore';
import { testConnection } from './testConnection';
import type { LLMConfig } from '../../types';
import './SettingsModal.css';

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
}

const EMPTY_CONFIG: LLMConfig = { base_url: '', api_key: '', model: '' };

export function SettingsModal({ open, onClose }: SettingsModalProps) {
  const [config, setConfig] = useState<LLMConfig>(EMPTY_CONFIG);
  const [status, setStatus] = useState<string | null>(null);
  const [statusColor, setStatusColor] = useState<string>('var(--hc-text-muted)');

  useEffect(() => {
    if (open) {
      setConfig(loadLLMConfig() ?? EMPTY_CONFIG);
      setStatus(null);
    }
  }, [open]);

  if (!open) return null;

  async function handleTestConnection() {
    setStatus('检测中...');
    setStatusColor('var(--hc-text-muted)');
    const result = await testConnection(config);
    if (result.ok) {
      setStatus('连接成功');
      setStatusColor('var(--hc-accent)');
    } else {
      setStatus(result.message);
      setStatusColor('#B5451D');
    }
  }

  function handleSave() {
    saveLLMConfig(config);
    setStatus('已保存（关闭请点右上角 ×）');
    setStatusColor('var(--hc-text-muted)');
  }

  return (
    <div className="hc-modal-overlay">
      <div data-testid="modal-backdrop" className="hc-modal-backdrop" />
      <div className="hc-modal-card">
        <button
          type="button"
          aria-label="关闭设置"
          className="hc-modal-close"
          onClick={onClose}
        >
          <span aria-hidden="true">×</span>
        </button>
        <p className="hc-modal-title">模型设置</p>
        <div className="hc-modal-form">
          <label className="hc-modal-field">
            <span>Base URL</span>
            <input
              type="text"
              placeholder="https://api.openai.com/v1"
              value={config.base_url}
              onChange={(e) => setConfig({ ...config, base_url: e.target.value })}
            />
          </label>
          <label className="hc-modal-field">
            <span>API Key</span>
            <input
              type="password"
              placeholder="sk-..."
              value={config.api_key}
              onChange={(e) => setConfig({ ...config, api_key: e.target.value })}
            />
          </label>
          <label className="hc-modal-field">
            <span>Model</span>
            <input
              type="text"
              placeholder="gpt-4o-mini"
              value={config.model}
              onChange={(e) => setConfig({ ...config, model: e.target.value })}
            />
          </label>
          <p className="hc-modal-hint">
            Key 仅在您发送消息时转发给上面填写的地址，不会保存在服务器，也不会被记录日志。
          </p>
          <div className="hc-modal-actions">
            <button type="button" onClick={handleTestConnection}>
              检测连接
            </button>
            <button type="button" className="hc-modal-save" onClick={handleSave}>
              保存
            </button>
          </div>
          {status && (
            <p className="hc-modal-status" style={{ color: statusColor }}>
              {status}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
