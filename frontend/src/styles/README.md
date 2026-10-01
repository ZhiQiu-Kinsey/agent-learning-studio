# Workspace styles

`../workspace.css` is the import entry. Keep shared defaults first, then legacy responsive rules, then scoped experience styles with their own breakpoints. Global theme and motion rules belong in experience.css; learning and curriculum overrides stay scoped.

| File | Responsibility |
| --- | --- |
| base.css | Theme tokens, typography, global defaults |
| shell.css | Sidebar, toolbar, compact lesson header and workspace modes |
| learning.css | Reading layout, study guide and source reference |
| laboratory.css | Input, answer, event timeline, JSON and code highlighting |
| effects.css | Integration styles for React Bits effects |
| forms.css | Quiz, model settings and mobile navigation sheet |
| curriculum.css | Curriculum map, search and course details |
| responsive.css | Breakpoints and reduced-motion overrides |
| experience.css | Shared luminous surfaces, full course sidebar and execution signal flow |
| learning-experience.css | Interactive lesson hero, concept cards, walkthrough and reading layout |
| curriculum-experience.css | Curriculum hero, domain navigation and animated overview |
| onboarding.css | Four prerequisite chapters, multi-level navigation and self-checks |

Tailwind and shadcn foundations remain in `../ui-foundation.css`.
