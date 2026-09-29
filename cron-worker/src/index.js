// GitHubのworkflow cron(5分おき)がしばしば無言で止まるため、
// Cloudflare Worker自身のCron Triggerで直接entry.yml/update.ymlを起こす。
// サイト訪問にもGitHub純正cronにも依存しない、独立した心臓部。
const OWNER = "hinoki-mayo";
const REPO = "kyotei-shikake";

// update.yml本来のcron: 7:00/21:00/0:30 JST = 22:00/12:00/15:30 UTC
const UPDATE_SLOTS_UTC_MIN = [22 * 60, 12 * 60, 15 * 60 + 30];
const UPDATE_WINDOW_MIN = 10; // この5分間隔cronなら10分あれば1回は当たる

// レースがある時間帯だけentry.ymlを起こす(元のentry.yml本来のcronと同じ 8:00〜21:59 JST = 23:00〜12:59 UTC)
function inRaceHours(now) {
  const m = now.getUTCHours() * 60 + now.getUTCMinutes();
  return m >= 23 * 60 || m < 13 * 60;
}

function headers(token) {
  return {
    Authorization: `Bearer ${token}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "kyotei-shikake-cron-worker",
  };
}

async function dispatch(token, workflow) {
  const r = await fetch(
    `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: { ...headers(token), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  console.log(`dispatch ${workflow}: status=${r.status}`);
}

function inUpdateWindow(now) {
  const m = now.getUTCHours() * 60 + now.getUTCMinutes();
  return UPDATE_SLOTS_UTC_MIN.some((s) => m >= s && m < s + UPDATE_WINDOW_MIN);
}

export default {
  async scheduled(event, env, ctx) {
    const now = new Date();
    if (inRaceHours(now)) {
      ctx.waitUntil(dispatch(env.GH_PAT, "entry.yml"));
    }
    if (inUpdateWindow(now)) {
      ctx.waitUntil(dispatch(env.GH_PAT, "update.yml"));
    }
  },
};
