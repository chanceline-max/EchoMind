import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchProfiles, generateProfile } from "../api/profiles";
import { Pagination } from "../components/Pagination";
import type { EvidenceMode, ProfileGenerationOptions, ProfileSummary } from "../types/profiles";

const statusText = {
  current: "当前",
  stale: "来源已变化",
  source_unavailable: "来源不可用",
} as const;

function SnapshotRow({ profile }: { profile: ProfileSummary }) {
  return (
    <Link className="profile-row" to={`/profiles/${profile.id}`}>
      <div className="profile-row__identity">
        <span className="profile-number">{profile.document_hash.slice(0, 8)}</span>
        <div><h2>{new Date(profile.generated_at).toLocaleString()}</h2><p>{profile.profile_version} · {profile.evidence_mode}</p></div>
      </div>
      <dl><div><dt>Insight</dt><dd>{profile.insight_count}</dd></div><div><dt>Evidence</dt><dd>{profile.evidence_count}</dd></div></dl>
      <span className={`source-state source-state--${profile.current_source_status}`}>{statusText[profile.current_source_status]}</span>
      {profile.stale_reason_codes.length > 0 && <small>{profile.stale_reason_codes.join(" · ")}</small>}
    </Link>
  );
}

export function ProfilesPage() {
  const [offset, setOffset] = useState(0);
  const [includePartialEvidence, setIncludePartialEvidence] = useState(true);
  const [includeInvalidated, setIncludeInvalidated] = useState(true);
  const [evidenceMode, setEvidenceMode] = useState<EvidenceMode>("references");
  const [includeReasoning, setIncludeReasoning] = useState(true);
  const generatedAsOf = useMemo(() => new Date().toISOString(), []);
  const queryClient = useQueryClient();
  const profiles = useQuery({
    queryKey: ["profiles", offset],
    queryFn: () => fetchProfiles(offset),
    staleTime: 0,
    gcTime: 30_000,
  });
  const mutation = useMutation({
    mutationFn: (options: ProfileGenerationOptions) => generateProfile(options),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["profiles"] }),
  });
  const submit = () => {
    if (
      evidenceMode === "excerpts" &&
      !window.confirm("导出的 Profile 将包含部分聊天证据摘录。是否继续？")
    ) return;
    mutation.mutate({
      includePartialEvidence,
      includeInvalidated,
      evidenceMode,
      includeReasoning,
      generatedAsOf,
    });
  };

  return (
    <main className="content-page profile-page">
      <header className="profile-heading"><div><p className="eyebrow">Stage 10 · Immutable record</p><h1>EchoProfile</h1></div><p>把已确认判断冻结成可追溯快照。生成过程完全离线，不调用模型，也不会修改 Insight。</p></header>
      <section className="profile-generator" aria-labelledby="profile-generator-title">
        <div className="generator-intro"><span className="profile-seal">I → E</span><div><p className="eyebrow">Confirmed only</p><h2 id="profile-generator-title">生成新快照</h2><p>只纳入 confirmed Insight；低支撑强度不会被自动排除。</p></div></div>
        <div className="generator-options">
          <label className="check-row"><input type="checkbox" checked={includePartialEvidence} onChange={(event) => setIncludePartialEvidence(event.target.checked)} />包含 partial Insight</label>
          <label className="check-row"><input type="checkbox" checked={includeInvalidated} onChange={(event) => setIncludeInvalidated(event.target.checked)} />显示证据已失效判断</label>
          <label>Evidence 模式<select aria-label="Evidence 模式" value={evidenceMode} onChange={(event) => setEvidenceMode(event.target.value as EvidenceMode)}><option value="references">仅引用（默认）</option><option value="excerpts">包含 Evidence 摘录</option></select></label>
          <label className="check-row"><input type="checkbox" checked={includeReasoning} onChange={(event) => setIncludeReasoning(event.target.checked)} />包含推理依据</label>
        </div>
        {evidenceMode === "excerpts" && <p className="sensitive-note" role="note">敏感导出：生成的 Profile 将包含部分聊天证据摘录，请妥善保管。</p>}
        <div className="generator-action"><button className="primary-button" disabled={mutation.isPending} onClick={submit}>{mutation.isPending ? "正在冻结来源…" : "生成 Profile"}</button><span>不会调用模型 · 不会修改 Insight</span></div>
        {mutation.isError && <p className="error-box" role="alert">{mutation.error.message || "生成失败，请检查已确认 Insight。"}</p>}
        {mutation.data && <p className="success-box" role="status">{mutation.data.reused ? "已复用相同来源与配置的快照。" : "新快照已生成。"} <Link to={`/profiles/${mutation.data.profile_snapshot_id}`}>查看详情 →</Link></p>}
      </section>

      <section className="snapshot-ledger"><div className="section-heading"><p className="eyebrow">Snapshot ledger</p><h2>历史快照</h2><span>{profiles.data?.total ?? 0} 份</span></div>
        {profiles.isPending && <p className="loading-line">正在读取 Profile 快照…</p>}
        {profiles.isError && <p className="error-box" role="alert">无法读取 Profile，或服务器返回格式无效。</p>}
        {profiles.data?.items.length === 0 && <div className="empty-state">还没有 Profile 快照。先确认 Insight，再生成第一份档案。</div>}
        <div className="profile-list">{profiles.data?.items.map((profile) => <SnapshotRow key={profile.id} profile={profile} />)}</div>
        {profiles.data && <Pagination offset={offset} limit={profiles.data.limit} total={profiles.data.total} onChange={setOffset} />}
      </section>
    </main>
  );
}
