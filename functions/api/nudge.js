// サイト訪問をきっかけに「展示の進入を反映」ワークフローを起こす。
// 公式サーバーへの実際のアクセスはentry.py側(1レース1回だけ)のまま。
// ここでは短いクールダウンで、GitHub Actionsの起動を間引くだけ。
const OWNER = "hinoki-mayo";
const REPO = "kyotei-shikake";
const WORKFLOW = "entry.yml";
const COOLDOWN_SECONDS = 120;

export async function onRequestPost(context) {
  const cacheKey = new Request("https://internal.nudge.invalid/entry-check");
  const cache = caches.default;

  if (await cache.match(cacheKey)) {
    return new Response(null, { status: 204 });
  }

  context.waitUntil(
    (async () => {
      await cache.put(
        cacheKey,
        new Response("locked", { headers: { "Cache-Control": `max-age=${COOLDOWN_SECONDS}` } })
      );
      try {
        await fetch(
          `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${context.env.GH_PAT}`,
              Accept: "application/vnd.github+json",
              "X-GitHub-Api-Version": "2022-11-28",
              "User-Agent": "kyotei-shikake-nudge",
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ ref: "main" }),
          }
        );
      } catch (e) {
        // ベストエフォート。失敗しても次のcronやアクセスで再試行される。
      }
    })()
  );

  return new Response(null, { status: 204 });
}
