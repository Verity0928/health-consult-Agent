interface MessageBubbleProps {
  content: string;
  align: 'left' | 'right';
}

export function MessageBubble({ content, align }: MessageBubbleProps) {
  return (
    <div data-testid="message-bubble" data-align={align} className="hc-message-bubble">
      {content}
    </div>
  );
}
