interface SystemNoticeProps {
  content: string;
}

export function SystemNotice({ content }: SystemNoticeProps) {
  return (
    <div data-testid="system-notice" className="hc-system-notice">
      <span className="hc-system-notice-line" />
      <span className="hc-system-notice-text">{content}</span>
      <span className="hc-system-notice-line" />
    </div>
  );
}
