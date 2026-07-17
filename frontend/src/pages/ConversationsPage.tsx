import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { fetchConversations } from "../api/conversations";
import { Pagination } from "../components/Pagination";

export function ConversationsPage() {
  const [params, setParams] = useSearchParams();
  const sourceFileId = params.get("source_file_id") ?? "";
  const [filter, setFilter] = useState(sourceFileId);
  const offset = Number(params.get("offset") ?? 0) || 0;
  const query = useQuery({ queryKey: ["conversations", sourceFileId, offset], queryFn: () => fetchConversations(sourceFileId, offset), staleTime: 0, gcTime: 60_000 });
  const update = (nextOffset: number, nextSource = sourceFileId) => {
    const next = new URLSearchParams();
    if (nextSource) next.set("source_file_id", nextSource);
    if (nextOffset) next.set("offset", String(nextOffset));
    setParams(next);
  };
  return (
    <main className="content-page">
      <p className="eyebrow">CONVERSATIONS</p><h1>会话</h1>
      <form className="filter-row" onSubmit={(event) => { event.preventDefault(); update(0, filter.trim()); }}>
        <label>按 SourceFile ID 筛选<input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="可留空" /></label>
        <button type="submit">应用筛选</button>
      </form>
      {query.isPending && <p>正在读取会话…</p>}
      {query.isError && <p className="error-box">无法读取会话。</p>}
      {query.data && <>
        <div className="conversation-list">{query.data.items.map((item) => (
          <Link className="conversation-row" key={item.id} to={`/conversations/${item.id}`}>
            <div><strong>{item.title ?? "未命名会话"}</strong><span>{item.platform}</span></div>
            <div className="row-metrics"><span>{item.participant_count} 人</span><span>{item.message_count} 条消息</span><span>{item.excluded_message_count} 条排除</span></div>
            <small>{item.started_at ? new Date(item.started_at).toLocaleString() : "时间未知"} — {item.ended_at ? new Date(item.ended_at).toLocaleString() : "时间未知"}</small>
          </Link>
        ))}</div>
        {query.data.total === 0 && <p className="empty-state">还没有可显示的会话，请先导入聊天记录。</p>}
        <Pagination offset={offset} limit={query.data.limit} total={query.data.total} onChange={update} />
      </>}
    </main>
  );
}
