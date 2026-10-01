import common from "./locales/zh-CN/common.json";
import lab from "./locales/zh-CN/lab.json";
import quiz from "./locales/zh-CN/quiz.json";
import settings from "./locales/zh-CN/settings.json";

/** Source-locale resources are bundled for first paint and define the key types. */
export const sourceResources = { common, settings, quiz, lab } as const;
