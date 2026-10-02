# 第三方声明

本项目复制或改编了以下上游代码。复制代码的文件头注明来源；新增借用时在此登记。

## React Bits

- 来源：https://reactbits.dev （David Haz）
- 许可：MIT + Commons Clause License Condition v1.0，全文见 `frontend/src/components/react-bits/LICENSE.md`
- 范围：`frontend/src/components/react-bits/` 与 `frontend/src/components/curriculum/` 中注明 React Bits 来源的组件
- 资源：`frontend/src/assets/lanyard/card.glb`、`lanyard.png` 来自 React Bits 仓库 `src/assets/lanyard/`（Lanyard 组件配套，同一许可）

## OpenMAIC

- 来源：https://github.com/THU-MAIC/OpenMAIC （THU-MAIC，参考提交 `8f7d51e`）
- 范围：
  - `frontend/scripts/check-i18n-keys.mjs`：改编自 `scripts/check-i18n-keys.mjs`
  - `frontend/scripts/cjk-scan.mjs`：思路来自 `tests/workbench/workbench-i18n.test.ts`

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

## 通过 npm 引入的依赖（未复制源码）

许可证随各包分发，这里只列出需要注意的项：

- elkjs（EPL-2.0）：课程地图路线图布局，懒加载。
- three、@react-three/fiber、@react-three/drei、meshline、@react-three/rapier（MIT）与 @dimforge/rapier3d-compat（Apache-2.0）：回顾页 3D 学习徽章（Lanyard），懒加载。
- @xyflow/react（MIT）、cmdk（MIT）、i18next / react-i18next（MIT）、motion（MIT）、@axe-core/playwright（MPL-2.0，仅测试使用）。
