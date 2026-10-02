import common from "./locales/zh-CN/common.json";
import errors from "./locales/zh-CN/errors.json";
import blocks from "./locales/zh-CN/blocks.json";
import lesson from "./locales/zh-CN/lesson.json";
import home from "./locales/zh-CN/home.json";
import lab from "./locales/zh-CN/lab.json";
import quiz from "./locales/zh-CN/quiz.json";
import stage from "./locales/zh-CN/stage.json";
import settings from "./locales/zh-CN/settings.json";
import command from "./locales/zh-CN/command.json";
import curriculum from "./locales/zh-CN/curriculum.json";

/** Source-locale resources are bundled for first paint and define the key types. */
export const sourceResources = {
  common,
  settings,
  quiz,
  lab,
  errors,
  stage,
  lesson,
  blocks,
  home,
  command,
  curriculum,
} as const;
