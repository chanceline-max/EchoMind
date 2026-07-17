import { useEffect, useState } from "react";

import { fetchHealth, InvalidHealthResponseError } from "../api/health";
import type { HealthResponse } from "../types/health";

type CheckState =
  | { kind: "checking" }
  | { kind: "online"; health: HealthResponse }
  | { kind: "unavailable" }
  | { kind: "invalid" };

export function BackendStatus() {
  const [state, setState] = useState<CheckState>({ kind: "checking" });
  useEffect(() => {
    let active = true;
    void fetchHealth().then((health) => {
      if (active) setState({ kind: "online", health });
    }).catch((error: unknown) => {
      if (active) setState(error instanceof InvalidHealthResponseError ? { kind: "invalid" } : { kind: "unavailable" });
    });
    return () => { active = false; };
  }, []);
  if (state.kind === "checking") return <p className="backend-status">正在检查后端状态…</p>;
  if (state.kind === "invalid") return <p className="backend-status backend-status--error">返回格式无效</p>;
  if (state.kind === "unavailable") return <p className="backend-status backend-status--error">后端不可用</p>;
  return <div className="backend-status backend-status--online"><strong>后端在线</strong><span>{state.health.service} · {state.health.version}</span></div>;
}
