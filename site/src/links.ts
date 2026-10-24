/** Repository links. The site deploys from main, so blob links point at main. */
export const REPO = "https://github.com/ZhiQiu-Kinsey/agent-learning-studio";
export const repoFile = (path: string) => `${REPO}/blob/main/${path}`;
export const LINKS = {
  readme: { "zh-CN": repoFile("README.zh-CN.md"), en: repoFile("README.md") },
  verification: repoFile("docs/verification/live-runs-2026-10-21.md"),
  license: repoFile("LICENSE"),
  notices: repoFile("THIRD_PARTY_NOTICES.md"),
} as const;

/** Files under public/, resolved against the deployed base path. */
export const asset = (path: string) => `${import.meta.env.BASE_URL}${path}`;
