# 前端工作区

前端使用 React、TypeScript、Vite 和 Tailwind CSS。学习课程与实验工作台共用课程、输入和运行记录；切换工作区不会重新执行课程。

## 模块职责

- `src/App.tsx`：导学、课程导航、工作区与模型设置入口。
- `src/hooks/useStudio.ts`：课程数据、参数、运行、取消与回放状态。
- `src/components/workspace/LearningWorkspace.tsx`：课程讲解、源码、提示词与自测。
- `src/components/workspace/Laboratory.tsx`：任务输入、回答、事件列表和 JSON 观察器。
- `src/components/workspace/ModelSettings.tsx`：模型供应商与连接配置。
- `src/lesson-extensions/`：可信课程插槽、结构化参数面板及实际事件报告。
- `src/styles/`：按业务模块组织样式，`workspace.css` 只保留导入入口。

## 组件与动效

React Bits 提供文字、入场、光效、菜单、开关和回放交互；shadcn/ui 提供对话框、抽屉、Tabs、Accordion 和表单基础组件。Markdown、代码高亮与 SSE 使用 react-markdown、Prism 和 eventsource-parser。

共享 `useMotionPreference` 响应系统“减少动画”的实时变化。离屏或隐藏页面暂停循环动效；Aurora 限制分辨率和帧率，WebGL 不可用时保留静态背景。课程示意与实际运行证据分别标识，动效不用于推断模型隐含思考或虚构学习完成度。

前端课程扩展在构建时登记，不从课程 JSON 动态加载远程脚本。扩展失败回退默认页面，报告读取当前回放位置的实际事件。接口与接入步骤见 [新增课程指南](adding-lessons.md)。

## 验证

构建前端后运行浏览器测试，覆盖工作区切换、运行与回放、模型设置、响应式布局、主题、减少动画及课程扩展。命令与测试模式见 [开发验证](validation.md)。
