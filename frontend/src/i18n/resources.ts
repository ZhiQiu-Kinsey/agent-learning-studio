import common from "./locales/zh-CN/common.json";
import errors from "./locales/zh-CN/errors.json";
import lesson from "./locales/zh-CN/lesson.json";
import lab from "./locales/zh-CN/lab.json";
import quiz from "./locales/zh-CN/quiz.json";
import stage from "./locales/zh-CN/stage.json";
import settings from "./locales/zh-CN/settings.json";

/** Source-locale resources are bundled for first paint and define the key types. */
export const sourceResources = { common, settings, quiz, lab, errors, stage, lesson } as const;
