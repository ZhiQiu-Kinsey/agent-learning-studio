# Third-party notices / 第三方声明

This project copies or adapts the upstream code below. Copied files name their source in the file header; register any new borrowing here.

本项目复制或改编了以下上游代码。复制代码的文件头注明来源；新增借用时在此登记。

## React Bits

- Source / 来源：https://reactbits.dev (David Haz)
- License / 许可：MIT + Commons Clause License Condition v1.0 — full text in `frontend/src/components/react-bits/LICENSE.md`. The Commons Clause forbids selling the components themselves; it does not change the MIT license of the rest of this project. / 全文见该文件；Commons Clause 禁止出售这些组件本身，不改变本项目其余部分的 MIT 许可。
- Scope / 范围：components in `frontend/src/components/react-bits/` and those in `frontend/src/components/curriculum/` marked as React Bits / `frontend/src/components/react-bits/` 与 `frontend/src/components/curriculum/` 中注明 React Bits 来源的组件
- Assets / 资源：`frontend/src/assets/lanyard/card.glb` and `lanyard.png` come from the React Bits repository `src/assets/lanyard/` (part of the Lanyard component, same license) / 来自 React Bits 仓库 `src/assets/lanyard/`（Lanyard 组件配套，同一许可）

## OpenMAIC

- Source / 来源：https://github.com/THU-MAIC/OpenMAIC (THU-MAIC, reference commit `8f7d51e`)
- Scope / 范围：
  - `frontend/scripts/check-i18n-keys.mjs`: adapted from / 改编自 `scripts/check-i18n-keys.mjs`
  - `frontend/scripts/cjk-scan.mjs`: idea from / 思路来自 `tests/workbench/workbench-i18n.test.ts`

```text
MIT License

Copyright (c) 2026 THU-MAIC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Dependencies installed via npm (no source copied) / 通过 npm 引入的依赖（未复制源码）

Licenses ship with each package; only the ones worth noting are listed. / 许可证随各包分发，这里只列出需要注意的项：

- elkjs (EPL-2.0): curriculum map route layout, lazy-loaded / 课程地图路线图布局，懒加载。
- three, @react-three/fiber, @react-three/drei, meshline, @react-three/rapier (MIT) and @dimforge/rapier3d-compat (Apache-2.0): the 3D learning badge (Lanyard) in the Review scene, lazy-loaded / 回顾页 3D 学习徽章（Lanyard），懒加载。
- @xyflow/react (MIT), cmdk (MIT), i18next / react-i18next (MIT), motion (MIT), @axe-core/playwright (MPL-2.0, tests only / 仅测试使用).
- react-joyride (MIT): mask and positioning for the guided tour, lazy-loaded with it / 实验导览的遮罩与定位，随导览懒加载。
