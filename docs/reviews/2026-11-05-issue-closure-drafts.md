# 待关闭 issue 与评论草稿

基于 `dev` @ `514787c6` 的核查结果。每条都注明了实现位置和测试，并明确标出仍未验证的部分——
不要把"代码已实现"写成"已验收"。

复制对应评论到 issue 后关闭即可，或授权我批量执行。

---

## #106 — Normalize painted inpainting masks for each provider

已实现于 `backend/app/runners/mask_converter.py`。

每种引擎现在收到各自要求的极性，不再到处假设 ComfyUI 的 `1 - alpha`：

- `normalize_mask_for_comfyui` — 反转 alpha
- `normalize_mask_for_webui` / `normalize_mask_for_fal_ai` — 灰度，白=编辑
- `normalize_mask_for_openai` — 反转 alpha

调用点：`creative_runner.py` 的 770 / 928 / 983 / 990 行，以及 `webui_runner.py` 的 236 行。
没有任何 provider 路径直接使用原始涂抹通道。

测试：`test_mask_converter.py`、`test_mask_adapter_payloads.py`、`test_custom_mask.py`，
共 18 个测试在 `dev` 上通过。

**仍未验证**：这是源码与 payload 级别的修复，没有记录真实引擎带涂抹 mask 的输出。
实时 inpaint 场景在发布验收中仍属未验证项。

---

## #124 — Restore complete canvas transactions with undo and redo

已实现于 `frontend/src/stores/useCanvasStore.ts`。

`CanvasSnapshot` 现在同时包含 `nodes`、`edges` 和 `selectedNodeId`（第 30–35 行），
`removeNode` 删除边后 undo 能完整恢复。`pushSnapshot` 上限 24 步，`undo`/`redo` 双向可达。

键盘绑定在 `FlowCanvas.tsx` 第 299/307 行，`acceptsCanvasShortcut()` 会排除输入框、
对话框和菜单内的按键，避免在输入时误触发。

测试：`frontend/src/tests/canvasTransactions.test.ts`。

---

## #121 — Return task IDs at submission and expose accurate cancellation states

已实现于 `backend/app/api/creative.py`。

提交即返回 `{'task_id': ..., 'status': 'queued'}`（第 40 行），不再需要轮询反查。
配套端点：`GET /tasks/{task_id}`（状态）、`GET /tasks/{task_id}/events`（带 `after_sequence` 的增量流）。

---

## #136 — Render and export managed media using verified MIME and format metadata

已实现于 `frontend/src/utils/media.ts`。

`extensionForMime()` 按实际 MIME 决定扩展名（png/jpeg/webp/gif/mp4/webm），未知类型降级为 `.bin`
而不是谎报 `.png`。`downloadOriginalMedia()` 读取响应 `blob.type`，优先于卡片上记录的 MIME。
`isPlayableVideo()` 用 MIME 优先、扩展名兜底来判断是否走视频分支。

---

## #139 — Align advertised language support with complete workflow translations

已按保守方向处理：`VERIFIED_UI_LANGUAGES = ['en']`（`translations.ts` 第 21 行），
其余七个字典在设置界面明确标为 preview 并说明会回退到英文。

`docs/UI_LOCALE_COVERAGE.md` 记录了这个契约：不把翻译 preview 宣称为完整支持，
缺失键回退英文，运行时诊断与用户内容保持原文。

---

## #142 — Consolidate typed execution, lifecycle, and API contracts

已实现于 `backend/app/core/execution_contract.py`：执行前按注册的节点契约校验
图、绑定和数据类型，失败抛 `ExecutionContractError`。

测试：`backend/tests/test_execution_contract.py`（修复提交 `62446c33`）。

---

## #138 — Standardize accessible dialogs and scope canvas keyboard shortcuts

共享 `Dialog` 组件已统一：焦点陷阱、`openDialogs` 栈保证只有顶层响应 Escape、
恢复先前焦点（`frontend/src/components/ui/Dialog.tsx`）。

快捷键作用域由 `acceptsCanvasShortcut()` 处理，输入框、`[role="dialog"]`、
`[role="menu"]` 等内的按键不会触发画布操作。

测试：`projectDialogAccessibility.test.tsx`、`remainingDialogs.test.tsx`。

---

## 建议保留（未关闭）

- **#118 / #120 / #130 / #131 / #132 / #133 / #134 / #137 / #141** — 代码有对应实现，
  但"完成"的判定依赖实际交互体验，无法只靠源码和单测确认。
- **#100** — 跟踪 issue，等所有子项有结论后再关。
- **#143** — 就是当前 PR #243 卡住的那道门禁，验收补齐后才算完成。

## 不要做的事

不要为了让看板好看就把上面保留项也关掉。这份草稿的价值在于
"关掉的是有证据的，留下的是没证据的"——两者混在一起就失去了意义。
