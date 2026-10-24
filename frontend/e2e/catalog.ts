import type { Page } from "@playwright/test";
import type { CurriculumData } from "../src/types";

/**
 * 目录里的课已全部开放。测试“未开放课程”的界面时，只在浏览器收到的目录里把一门课改回
 * planned；后端和仓库里的目录不变。选最后一门课，不影响前面课程的先修关系。
 */
export const PLANNED_FIXTURE = "capstone-study-assistant";

export function withPlannedLesson(
  catalog: CurriculumData,
  id: string = PLANNED_FIXTURE,
): CurriculumData {
  return {
    ...catalog,
    lessons: catalog.lessons.map((lesson) =>
      lesson.id === id ? { ...lesson, status: "planned" } : lesson,
    ),
  };
}

/** 让页面拿到的 /api/curriculum 里有一门 planned 课（保留请求的语言等参数）。 */
export async function routePlannedLesson(
  page: Page,
  id: string = PLANNED_FIXTURE,
) {
  await page.route(
    (url) => url.pathname === "/api/curriculum",
    async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        json: withPlannedLesson(await response.json(), id),
      });
    },
  );
}
