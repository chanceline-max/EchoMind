import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { fetchImport } from "../api/imports";

export function ImportDetailPage() {
  const id = useParams().sourceFileId ?? "";
  const query = useQuery({ queryKey: ["import", id], queryFn: () => fetchImport(id), enabled: Boolean(id), staleTime: 0, gcTime: 60_000 });
  if (query.isPending) return <main className="content-page"><p>正在读取导入结果…</p></main>;
  if (query.isError) return <main className="content-page"><p className="error-box">无法读取导入结果。</p></main>;
  const item = query.data;
  const metrics = [
    ["会话", item.conversation_count], ["参与者", item.participant_count], ["消息", item.message_count],
    ["已排除", item.excluded_message_count], ["警告", item.parser_warning_count + item.cleaning_warning_count],
  ];
  return (
    <main className="content-page">
      <p className="eyebrow">IMPORT COMPLETE</p><h1>导入完成</h1>
      <section className="panel detail-grid">
        <div><span>文件</span><strong>{item.filename}</strong></div>
        <div><span>Parser</span><strong>{item.parser_name} · {item.parser_version}</strong></div>
        <div><span>Cleaning Pipeline</span><strong>{item.cleaning_pipeline_version}</strong></div>
        <div><span>导入时间</span><strong>{new Date(item.imported_at).toLocaleString()}</strong></div>
      </section>
      <section className="metric-grid">{metrics.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</section>
      <Link className="primary-link" to={`/conversations?source_file_id=${item.source_file_id}`}>查看本次导入的会话</Link>
    </main>
  );
}
