// 日次更新(予想とサイトの更新)がcronの無言スキップで飛んだ時の安全網。
// update.ymlは1日3回(7:00/21:00/0:30 JST = 22:00/12:00/15:30 UTC)しか
// 走らないので、entry.ymlのように常時チェックはせず、各時刻の直後
// 30分だけ「未実行なら起こす」。ホームページ訪問時に呼ばれる想定。
import { lastRunMs, dispatch } from "../_gh.js";

const WORKFLOW = "update.yml";
const SLOTS_UTC_MIN = [12 * 60, 15 * 60 + 30, 22 * 60]; // 21:00 / 0:30 / 7:00 JST
const CATCH_WINDOW_MIN = 30;

function inCatchWindow(now) {
  const m = now.getUTCHours() * 60 + now.getUTCMinutes();
  return SLOTS_UTC_MIN.some((s) => m >= s && m < s + CATCH_WINDOW_MIN);
}

export async function onRequestPost(context) {
  const token = context.env.GH_PAT;
  try {
    if (!inCatchWindow(new Date())) {
      return new Response(null, { status: 204 });
    }
    const sinceMs = Date.now() - (await lastRunMs(token, WORKFLOW));
    if (sinceMs < CATCH_WINDOW_MIN * 60 * 1000) {
      console.log(`nudge(update): skip (last run ${Math.round(sinceMs / 1000)}s ago)`);
      return new Response(null, { status: 204 });
    }
    const r = await dispatch(token, WORKFLOW);
    console.log(`nudge(update): dispatched status=${r.status} body=${r.body}`);
  } catch (e) {
    console.log(`nudge(update): error ${e}`);
  }
  return new Response(null, { status: 204 });
}
