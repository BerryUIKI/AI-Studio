# Persistent Right Sidebar AI Agent Specification

## 1. Overview
Previously, AI Agents existed as an exclusive full-page singleton view within the left navigation rail. In practice, creative assistants (prompt expansion, asset generation, and future ComfyUI workflow generation/editing) require contextual synergy across views (Canvas, Model Hub, Embedded ComfyUI, Launcher).

This specification formalizes the transformation of AI Agents into a **Persistent, Collapsible Right Sidebar** with dedicated toggle controls in the top titlebar.

---

## 2. Layout & Architectural Principles

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│ [Logo] [Launcher] [Canvas] [Model Hub] [ComfyUI] [WebUI] ...      [✨ Agent ◨]   │ ← Topbar Toggle
├──────┬────────────────────────────────────────────────────────────┬──────────────┤
│      │                                                            │ ✨ Agent     │
│ Left │                                                            │ (Persistent  │
│ Rail │                  Main Active View Container                │  Right Rail) │
│ Nav  │        (Launcher / Canvas / Model Hub / ComfyUI / WebUI)   ├──────────────┤
│      │                                                            │ • Natural    │
│      │                                                            │   Language   │
│      │                                                            │ • Workflows  │
└──────┴────────────────────────────────────────────────────────────┴──────────────┘
```

1. **Left Rail Cleanliness**:
   - Remove `agents` from `GlobalNavRail` and `ViewType`.
   - Left rail strictly organizes destination views: Launcher Hub, Infinite Canvas, Model Hub, ComfyUI, SD WebUI, and Settings.

2. **Persistent Contextual Right Sidebar**:
   - Positioned as a dedicated, smoothly collapsible flex/absolute right panel adjacent to the main workspace.
   - When collapsed, workspace occupies 100% remaining horizontal width.
   - When opened, occupies `w-96` (384px) with high-density chat history, human-in-the-loop proposals, and canvas synchronization.

3. **Titlebar & Sidebar Header Controls**:
   - Top Titlebar features the primary toggle button with glowing active indicator and shortcut hint.
   - Panel header features collapse (`ChevronRight` / `PanelRightClose`) and close (`X`) controls.

4. **Future Synergy Capabilities**:
   - Direct image creation onto Canvas.
   - ComfyUI workflow generation and node graph editing in real-time.
