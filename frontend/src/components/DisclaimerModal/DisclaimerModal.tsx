import { useState } from 'react';
import './DisclaimerModal.css';

export const DISCLAIMER_ACK_STORAGE_KEY = 'health-consult-disclaimer-ack';

export function DisclaimerModal() {
  const [acknowledged, setAcknowledged] = useState(
    () => localStorage.getItem(DISCLAIMER_ACK_STORAGE_KEY) === 'true',
  );

  if (acknowledged) return null;

  function handleAcknowledge() {
    localStorage.setItem(DISCLAIMER_ACK_STORAGE_KEY, 'true');
    setAcknowledged(true);
  }

  return (
    <div className="hc-disclaimer-overlay">
      <div className="hc-disclaimer-backdrop" />
      <div className="hc-disclaimer-card">
        <p className="hc-disclaimer-text">
          本项目是一个技术演示，用于展示 AI Agent 的架构设计，不是医疗产品。对话内容基于演示用的知识库数据生成，不构成医疗建议。
        </p>
        <button type="button" className="hc-disclaimer-ack" onClick={handleAcknowledge}>
          我理解
        </button>
      </div>
    </div>
  );
}
