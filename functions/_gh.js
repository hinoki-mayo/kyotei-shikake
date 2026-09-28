// entry.yml/update.yml共通のGitHub Actions呼び出しヘルパー。
// ファイル名が_始まりなのでCloudflare Pages Functionsはルートとして扱わない。
const OWNER = "hinoki-mayo";
const REPO = "kyotei-shikake";

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "kyotei-shikake-nudge",
  };
}

export async function lastRunMs(token, workflow) {
  const r = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/runs?per_page=1`,
    { headers: headers(token) }
  );
  const data = await r.json();
  const last = data.workflow_runs && data.workflow_runs[0];
  return last ? new Date(last.created_at).getTime() : 0;
}

export async function dispatch(token, workflow) {
  const r = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: { ...headers(token), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  const body = await r.text();
  return { status: r.status, body };
}
