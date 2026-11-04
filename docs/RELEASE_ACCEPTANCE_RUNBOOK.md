# 0.1.1 验收操作手册

面向执行验收的人。目标：在候选提交 `bfdf1458` 上跑完要求项，产出一个证据 bundle，
让 PR #243 的 `Current-head Release Acceptance` 通过。

在此之前，该检查失败是预期行为，不代表代码有问题。

## 一、门禁到底检查什么

`.github/workflows/release-acceptance.yml` 只做四件事：

1. 从 PR 正文解析 **恰好一条** 引用：
   `<!-- berry-acceptance {"run_id":123456789,"artifact":"release-acceptance"} -->`
2. 用 GitHub API 取该 run，要求：同仓库、`status=completed`、`conclusion=success`、
   `head_sha` **完全等于** PR 的 head 提交。
3. 下载该 run 里名为 `release-acceptance` 的 artifact。
4. 运行 `scripts/verify-release-evidence.py` 校验内容。

第 3 步拿到的 artifact 根目录必须有 `evidence.json`，以及它引用的所有文件。

## 二、evidence.json 格式

以 `docs/acceptance/evidence-template.json` 为骨架。全部 30 个条目
（R01–R18、L01–L12）加 11 个场景都要出现，且：

| 字段 | 要求 |
| --- | --- |
| `commit` | 40 位完整 SHA，必须等于被测提交 |
| `status` | 必须是 `"passed"`，`"unverified"` 一律失败 |
| `evidence_level` | `live` 或 `packaged-live`；R17 额外允许 `ci` |
| `artifacts` | 非空数组，每个路径指向 bundle 内**存在且非空**的文件 |
| `environment` | `os`、`machine`、`tested_at` 三项都必填 |
| `integrations` | `engines`、`providers`、`models` 三项都必填（可写 `["none"]`） |

**强制 `packaged-live` 的三项**：`clean-windows-package` 场景、`L01`、`L12`。
这三个必须在打包后的安装版上跑，源码树里跑不算。

路径安全：artifact 路径必须在 bundle 目录内，`../` 会被拒绝。

## 三、11 个场景分别怎么验

| 场景 ID | 怎么验 | 证据文件建议 |
| --- | --- | --- |
| `cloud-image-journey` | 配好 BYOK 密钥，画布上跑一次文生图，出图并保存 | 出图文件 + 截图 |
| `comfyui-image-journey` | 起 ComfyUI，文生图跑通 | 出图 + 引擎日志 |
| `webui-image-journey` | 起 WebUI，文生图跑通 | 出图 + 引擎日志 |
| `project-reopen` | 存项目 → 关应用 → 重开 → 布局/资产/历史都在 | 前后两张截图 |
| `masked-edit` | 选中图 → 涂抹 → 局部重绘 → 原图与新图并存 | 新图 + 截图 |
| `upscale-export` | 放大 → 看尺寸 → 导出文件 | 导出文件 + 截图 |
| `task-recovery` | 跑任务时重启后端 → 状态可恢复 | 任务记录导出 |
| `external-ownership` | 连接一个外部启动的引擎，执行时不得终止它 | 进程快照 |
| `install-update-recovery` | 装引擎中断 → 可见未完成 → 重试成功 | 日志 + 截图 |
| `safe-exit` | 有活动任务时关窗 → 不静默杀任务 | 截图 |
| `clean-windows-package` | **打包版**在干净 VM 上首次启动到画布 | 截图 + 启动日志 |

## 四、执行顺序

### 第 1 步：准备干净环境

L01/L12/clean-windows-package 三项强制 `packaged-live`，所以需要一台
**没有 Python、Git、Node.js** 的 Windows 机器或 VM。参考
`docs/CLEAN_MACHINE_TESTING.md`，用 `python --version` 等命令确认全部失败。

### 第 2 步：在候选提交上打包

```bash
git checkout bfdf1458
powershell -ExecutionPolicy Bypass -File scripts/package-windows-release.ps1 -Version 0.1.1
```

产物在 `dist/`。把 ZIP 拷到干净 VM 上解压运行。

### 第 3 步：逐项跑场景

按上表执行。每跑完一项，把产物文件放进同一个目录，并在
`evidence.json` 对应条目里写上相对路径。

**记录真实版本**：`integrations` 里写清楚引擎版本、模型文件名、provider 名称。
不写会被判为缺失。

### 第 4 步：本地自检

在提交证据前先本地跑一遍校验，别等 CI：

```bash
python scripts/verify-release-evidence.py \
  --evidence ./bundle/evidence.json \
  --commit bfdf145825683c6ddbd7d59eecf7721fafd06a6e
```

全部通过会打印 `PASS`。

### 第 5 步：上传 artifact

证据 bundle **不进 Git**（门禁文档明确要求外部存放）。需要一个新的
workflow 在那个确切提交上运行并上传：

```yaml
- uses: actions/upload-artifact@v4
  with:
    name: release-acceptance
    path: bundle/
```

要求：同仓库、在该提交上、`conclusion=success`。不能有密钥。

### 第 6 步：在 PR 正文写引用

拿到 run_id 后，在 PR #243 正文里加一行（**只能有一行**）：

```html
<!-- berry-acceptance {"run_id":123456789,"artifact":"release-acceptance"} -->
```

门禁会自动重跑。

### 第 7 步：产品负责人批准

`BRANCHING_STRATEGY.md` §7 要求 release PR 必须有产品负责人批准才能合并。
这一步 CI 无法替代。

## 五、当前已知阻塞

| 阻塞 | 影响 | 解法 |
| --- | --- | --- |
| 本机 ComfyUI 运行时是 CPU-only torch | `comfyui-image-journey`、R03/R05/L05/L06 跑不了 | 装 CUDA 版 torch 或换一台有 NVIDIA 驱动的机器 |
| 没有可用 checkpoint（只有 `.part` 未完成文件） | 无法出图 | 下载一个完整模型 |
| 没有干净 Windows VM | L01/L12/clean-windows-package 无法证明 | 建 Hyper-V/VirtualBox VM |
| 没有授权云凭据 | `cloud-image-journey`、R13 无法跑 | 用户提供有额度的密钥 |
| 未测 125%/150% 缩放 | R06 不完整 | 在系统显示设置里切换后重测布局 |

## 六、诚实性提醒

`verify-release-evidence.py` 只能证明"文件存在且非空"，无法证明内容真实。
门禁文档原文：「Evidence completeness does not prove the content's truth.」

所以不要为了过门禁而填凑数。如果某一项确实跑不了，正确做法是让门禁继续失败，
而不是塞一个空壳文件。这与 `AGENTS.md` 的"不宣称未验证能力"是同一条原则。
