import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { fetchProfiles, generateProfile } from "../api/profiles";
import { Pagination } from "../components/Pagination";
import { evidenceModeLabel, profileSourceStatusLabel, staleReasonLabel } from "../labels";
import type { ProfileGenerationOptions, ProfileSummary } from "../types/profiles";

function SnapshotRow({ profile }: { profile: ProfileSummary }) {
  return (
    <Link className="profile-row" to={`/profiles/${profile.id}`}>
      <div className="profile-row__identity">
        <span className="profile-number">{profile.document_hash.slice(0, 8)}</span>
        <div><h2>{new Date(profile.generated_at).toLocaleString()}</h2><p>{profile.profile_version} · {evidenceModeLabel(profile.evidence_mode)}</p></div>
      </div>
      <dl><div><dt>洞察</dt><dd>{profile.insight_count}</dd></div><div><dt>证据</dt><dd>{profile.evidence_count}</dd></div></dl>
      <span className={`source-state source-state--${profile.current_source_status}`}>{profileSourceStatusLabel(profile.current_source_status)}</span>
      {profile.stale_reason_codes.length > 0 && <small>{profile.stale_reason_codes.map(staleReasonLabel).join(" · ")}</small>}
    </Link>
  );
}

export function ProfilesPage() {
  const [offset, setOffset] = useState(0);
  const [includePartialEvidence, setIncludePartialEvidence] = useState(true);
  const [includeInvalidated, setIncludeInvalidated] = useState(true);
  const [remoteConsent, setRemoteConsent] = useState(false);
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
    if (!window.confirm("将基于当前已确认洞察生成综合人格分析。人格框架只作为参考，是否继续？")) return;
    mutation.mutate({
      includePartialEvidence,
      includeInvalidated,
      evidenceMode: "references",
      includeReasoning: true,
      includePersonalitySynthesis: true,
      remoteConsent,
      generatedAsOf,
    });
  };

  return (
    <main className="content-page profile-page">
      <header className="profile-heading"><div><p className="eyebrow">综合人格档案</p><h1>EchoProfile</h1></div><p>把分散的已确认判断连接成一份完整人物分析。Big Five 与 MBTI 只提供辅助理解，不定义你。</p></header>
      <section className="profile-generator" aria-labelledby="profile-generator-title">
        <div className="generator-intro"><span className="profile-seal">洞察 → 理解</span><div><p className="eyebrow">EchoProfile 2.0</p><h2 id="profile-generator-title">生成综合人格分析</h2><p>AI 会跨主题整理性格、思维、决策、关系、压力、优势与成长方向，不在正文堆叠证据编号。</p></div></div>
        <div className="generator-options">
          <label className="check-row"><input type="checkbox" checked={includePartialEvidence} onChange={(event) => setIncludePartialEvidence(event.target.checked)} />包含部分有效洞察</label>
          <label className="check-row"><input type="checkbox" checked={includeInvalidated} onChange={(event) => setIncludeInvalidated(event.target.checked)} />让模型考虑历史变化与失效判断</label>
          <label className="check-row consent-row"><input type="checkbox" checked={remoteConsent} onChange={(event) => setRemoteConsent(event.target.checked)} />若当前配置远程 Provider，同意发送已确认的 Insight 派生文本</label>
        </div>
        <p className="sensitive-note" role="note">隐私边界：不会发送原始聊天、Evidence 摘录、姓名或文件信息；远程 Provider 仅接收已确认 Insight 的派生内容。</p>
        <div className="generator-action"><button className="primary-button" disabled={mutation.isPending} onClick={submit}>{mutation.isPending ? "正在综合分析…" : "生成综合人格档案"}</button><span>内部保留证据链 · 正文不显示引用</span></div>
        {mutation.isError && <p className="error-box" role="alert">{mutation.error.message || "生成失败，请检查已确认洞察。"}</p>}
        {mutation.data && <p className="success-box" role="status">{mutation.data.reused ? "已复用相同来源与配置的快照。" : "新快照已生成。"} <Link to={`/profiles/${mutation.data.profile_snapshot_id}`}>查看详情 →</Link></p>}
      </section>

      <section className="snapshot-ledger"><div className="section-heading"><p className="eyebrow">快照记录</p><h2>历史快照</h2><span>{profiles.data?.total ?? 0} 份</span></div>
        {profiles.isPending && <p className="loading-line">正在读取档案快照…</p>}
        {profiles.isError && <p className="error-box" role="alert">无法读取档案，或服务器返回格式无效。</p>}
        {profiles.data?.items.length === 0 && <div className="empty-state">还没有档案快照。先确认洞察，再生成第一份档案。</div>}
        <div className="profile-list">{profiles.data?.items.map((profile) => <SnapshotRow key={profile.id} profile={profile} />)}</div>
        {profiles.data && <Pagination offset={offset} limit={profiles.data.limit} total={profiles.data.total} onChange={setOffset} />}
      </section>
    </main>
  );
}
