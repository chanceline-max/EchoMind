import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";

import { fetchConversation, fetchMessageLocation, fetchMessages, setMessageExcluded } from "../api/conversations";
import { MessageCard } from "../components/MessageCard";
import { Pagination } from "../components/Pagination";
import type { MessageSummary } from "../types/api";

export function ConversationDetailPage() {
  const id = useParams().conversationId ?? "";
  const [searchParams] = useSearchParams();
  const targetMessageId = searchParams.get("message") ?? "";
  const [manualOffset, setManualOffset] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["conversation", id], queryFn: () => fetchConversation(id), enabled: Boolean(id), staleTime: 0, gcTime: 60_000 });
  const location = useQuery({ queryKey: ["message-location", targetMessageId], queryFn: () => fetchMessageLocation(targetMessageId), enabled: Boolean(targetMessageId) });
  const offset = manualOffset ?? (location.data?.conversation_id === id ? location.data.suggested_offset : 0);
  const messages = useQuery({ queryKey: ["messages", id, offset], queryFn: () => fetchMessages(id, offset), enabled: Boolean(id), staleTime: 0, gcTime: 30_000 });
  useEffect(() => {
    if (!messages.data || !targetMessageId) return;
    document.getElementById(`message-${targetMessageId}`)?.scrollIntoView({ block: "center" });
  }, [messages.data, targetMessageId]);
  const exclusion = useMutation({
    mutationFn: (message: MessageSummary) => setMessageExcluded(message.id, !message.excluded_from_analysis),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["messages", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversation", id] }),
        queryClient.invalidateQueries({ queryKey: ["conversations"] }),
        queryClient.invalidateQueries({ queryKey: ["insights"] }),
        queryClient.invalidateQueries({ queryKey: ["insight"] }),
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
        <div className="message-list">{messages.data.items.map((message) => <MessageCard key={message.id} message={message} highlighted={message.id === targetMessageId} changing={exclusion.isPending && exclusion.variables?.id === message.id} onToggleExcluded={(item) => exclusion.mutate(item)} />)}</div>
        <Pagination offset={offset} limit={messages.data.limit} total={messages.data.total} onChange={setManualOffset} />
      </>}
    </main>
  );
}
