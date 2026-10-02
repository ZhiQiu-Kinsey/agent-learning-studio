# Workspace styles

`../workspace.css` is the import entry. Keep shared defaults first, then legacy responsive rules, then scoped experience styles with their own breakpoints. Design tokens and the global motion gates live in tokens.css; learning and curriculum overrides stay scoped.

Motion is decided once by `src/motion/` (`MotionProvider`): the OS preference and the learner's setting resolve to `<html data-motion="full|reduced|static">`. Never use `@media (prefers-reduced-motion)` directly; scope reduced-motion rules under `:root:not([data-motion="full"])` (Tailwind `motion-reduce:` / `motion-safe:` already follow it). Heavy effects go through `MotionIntent` or `useMotionBudget` so they lazy-load, pause offscreen and share the single WebGL slot.

| File | Responsibility |
| --- | --- |
| base.css | Theme tokens, typography, global defaults |
| tokens.css | Motion tokens, agent role colours, motion-level gates |
| shell.css | Sidebar, toolbar, compact lesson header and workspace modes |
| learning.css | Reading layout, study guide and source reference |
| laboratory.css | Input, answer, event timeline, JSON and code highlighting |
| effects.css | Integration styles for React Bits effects |
| forms.css | Quiz, model settings and mobile navigation sheet |
| curriculum.css | Curriculum map, search and course details |
| responsive.css | Breakpoints |
| experience.css | Shared luminous surfaces, full course sidebar and execution signal flow |
| learning-experience.css | Interactive lesson hero, concept cards, walkthrough and reading layout |
| curriculum-experience.css | Curriculum hero, domain navigation and animated overview |
| onboarding.css | Four prerequisite chapters, multi-level navigation and self-checks |
| self-check.css | Lesson 自检 (confidence, option feedback, trace hunt, checkpoints) and 回顾; imported by those scenes |

Tailwind and shadcn foundations remain in `../ui-foundation.css`.
