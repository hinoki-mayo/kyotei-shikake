// サイト訪問をきっかけに「展示の進入を反映」ワークフローを起こす。
// 公式サーバーへの実際のアクセスはentry.py側(1レース1回だけ)のまま。
// 連打防止は自前でキャッシュせず、GitHub上の直近の実行時刻を都度確認する
// (Cache APIのTTLは信頼できず、期限切れせず何時間も張り付くことがあった)。
import { lastRunMs, dispatch } from "../_gh.js";

const WORKFLOW = "entry.yml";
const COOLDOWN_MS = 120 * 1000;

export async function onRequestPost(context) {
  const token = context.env.GH_PAT;
  try {
    const sinceMs = Date.now() - (await lastRunMs(token, WORKFLOW));
    if (sinceMs < COOLDOWN_MS) {
      console.log(`nudge(entry): skip (last run ${Math.round(sinceMs / 1000)}s ago)`);
      return new Response(null, { status: 204 });
    }
    const r = await dispatch(token, WORKFLOW);
    console.log(`nudge(entry): dispatched status=${r.status} body=${r.body}`);
  } catch (e) {
    console.log(`nudge(entry): error ${e}`);
  }
  return new Response(null, { status: 204 });
}
