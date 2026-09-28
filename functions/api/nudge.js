// サイト訪問をきっかけに「展示の進入を反映」ワークフローを起こす。
// 公式サーバーへの実際のアクセスはentry.py側(1レース1回だけ)のまま。
// 連打防止は自前でキャッシュせず、GitHub上の直近の実行時刻を都度確認する
// (Cache APIのTTLは信頼できず、期限切れせず何時間も張り付くことがあった)。
const OWNER = "hinoki-mayo";
const REPO = "kyotei-shikake";
const WORKFLOW = "entry.yml";
const COOLDOWN_MS = 120 * 1000;

function ghHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "kyotei-shikake-nudge",
  };
}

export async function onRequestPost(context) {
  const token = context.env.GH_PAT;
  try {
    const listResp = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/runs?per_page=1`,
      { headers: ghHeaders(token) }
    );
    const data = await listResp.json();
    const last = data.workflow_runs && data.workflow_runs[0];
    const lastMs = last ? new Date(last.created_at).getTime() : 0;
    const sinceMs = Date.now() - lastMs;
    if (sinceMs < COOLDOWN_MS) {
      console.log(`nudge: skip (last run ${Math.round(sinceMs / 1000)}s ago)`);
      return new Response(null, { status: 204 });
    }
    const dispResp = await fetch(
      `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: { ...ghHeaders(token), "Content-Type": "application/json" },
        body: JSON.stringify({ ref: "main" }),
      }
    );
    const dispBody = await dispResp.text();
    console.log(`nudge: dispatched status=${dispResp.status} body=${dispBody}`);
  } catch (e) {
    console.log(`nudge: error ${e}`);
  }
  return new Response(null, { status: 204 });
}
