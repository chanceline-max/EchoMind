import { useState } from "react";

import type { MessageSummary } from "../types/api";

interface Props {
  message: MessageSummary;
  changing: boolean;
  onToggleExcluded: (message: MessageSummary) => void;
}

function TextBlock({ label, value }: { label: string; value: string }) {
  const [expanded, setExpanded] = useState(false);
  const long = value.length > 360;
  const visible = long && !expanded ? `${value.slice(0, 360)}…` : value;
  return (
    <section className="message-text">
      <h3>{label}</h3>
      <pre>{visible}</pre>
      {long && <button className="text-button" onClick={() => setExpanded(!expanded)}>{expanded ? "收起" : "展开全文"}</button>}
    </section>
  );
}

export function MessageCard({ message, changing, onToggleExcluded }: Props) {
  return (
    <article className={`message-card${message.excluded_from_analysis ? " is-excluded" : ""}`}>
      <header>
        <strong>{message.sender_display_name}</strong>
        <span>{message.timestamp ? new Date(message.timestamp).toLocaleString() : "时间未知"}</span>
        <span className="pill">{message.message_type}</span>
      </header>
      <div className="message-flags">
        {message.is_system_message && <span>系统消息</span>}
        {message.is_recalled_message && <span>撤回消息</span>}
        {message.excluded_from_analysis && <span>已排除分析</span>}
      </div>
      <TextBlock label="原始内容" value={message.raw_content} />
      <TextBlock label="规范化内容" value={message.normalized_content} />
      <button disabled={changing} onClick={() => onToggleExcluded(message)}>
        {message.excluded_from_analysis ? "恢复分析" : "排除分析"}
      </button>
    </article>
  );
}
