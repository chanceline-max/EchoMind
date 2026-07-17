import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { fetchConversation, fetchMessages, setMessageExcluded } from "../api/conversations";
import { MessageCard } from "../components/MessageCard";
import { Pagination } from "../components/Pagination";
import type { MessageSummary } from "../types/api";

export function ConversationDetailPage() {
  const id = useParams().conversationId ?? "";
  const [offset, setOffset] = useState(0);
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => fetchConversation(id), enabled: Boolean(id), staleTime: 0, gcTime: 60_000 });
  const messages = useQuery({ queryKey: ["messages", id, offset], queryFn: () => fetchMessages(id, offset), enabled: Boolean(id), staleTime: 0, gcTime: 30_000 });
  const exclusion = useMutation({
    mutationFn: (message: MessageSummary) => setMessageExcluded(message.id, !message.excluded_from_analysis),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversation", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
      ]);
    },
  });
  if (detail.isPending) return <main className="content-page"><p>正在读取会话…</p></main>;
  if (detail.isError) return <main className="content-page"><p className="error-box">无法读取会话。</p></main>;
  return (
    <main className="content-page">
      <p className="eyebrow">{detail.data.platform}</p><h1>{detail.data.title ?? "未命名会话"}</h1>
      <section className="panel conversation-meta">
        <div><span>参与者</span><strong>{detail.data.participants.map((item) => item.display_name).join("、")}</strong></div>
        <div><span>消息</span><strong>{detail.data.message_count}</strong></div>
        <div><span>已排除</span><strong>{detail.data.excluded_message_count}</strong></div>
      </section>
      {exclusion.isError && <p className="error-box" role="alert">更新排除状态失败。</p>}
      {messages.isPending && <p>正在读取消息…</p>}
      {messages.isError && <p className="error-box">无法读取消息。</p>}
      {messages.data && <>
        <div className="message-list">{messages.data.items.map((message) => <MessageCard key={message.id} message={message} changing={exclusion.isPending && exclusion.variables?.id === message.id} onToggleExcluded={(item) => exclusion.mutate(item)} />)}</div>
        <Pagination offset={offset} limit={messages.data.limit} total={messages.data.total} onChange={setOffset} />
      </>}
    </main>
  );
}
