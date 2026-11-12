# 0.1.1 验收实操指南（针对当前环境）

目标：在候选提交上产出一个 `release-acceptance` artifact，让 `Current-head Release Acceptance` 变绿。

---

## 零、先理解门禁的四个硬条件

校验逻辑全部在 `scripts/verify-release-evidence.py`，没有例外：

| 条件 | 代码位置 | 说明 |
| --- | --- | --- |
| 40 条记录一条不能少 | `REQUIREMENTS` + `SCENARIOS` | R01–R18、L01–L12、11 个场景 |
| `status` 必须是 `"passed"` | 第 50 行 | `"unverified"` 直接失败 |
| `evidence_level` 必须是 `live`/`packaged-live` | 第 47–49 行 | R17 可 `ci`；L01/L12/clean-windows-package 只能 `packaged-live` |
| 每个 `artifacts` 路径必须指向 bundle 内**存在且非空**的文件 | 第 60–62 行 | `../` 会被拒 |

另外 `environment` 三个字段、`integrations` 三个字段都必须非空。

**校验脚本只验证文件存在且非空，不验证内容。** 所以正确做法是真的跑，不是造壳。

---

## 一、当前这台机器的阻塞

运行手册第五节已经列出，我逐条确认过：

| 阻塞 | 状态 | 需要你提供 |
| --- | --- | --- |
| ComfyUI 是 CPU-only torch | ❌ 跑不了真出图 | NVIDIA 显卡机器，或装 CUDA 版 torch |
| 没有完整 checkpoint（只有 `.part`） | ❌ 无法出图 | 下载一个完整模型（几 GB） |
| 没有干净 Windows VM | ❌ L01/L12/clean-package 无法证明 | Hyper-V 或 VirtualBox 建一台 |
| 没有授权云密钥 | ❌ cloud journey 跑不了 | 一个有额度的 provider key |
| 未测 125%/150% 缩放 | ❌ R06 不完整 | 系统显示设置里切换后重测 |

**这四项里，干净 VM 是绕不过去的**——L01、L12、`clean-windows-package` 被硬编码为只接受 `packaged-live`，源码树里跑得再完美也不算。

---

## 二、验证一下签名问题（可选，但建议先修）

你的 `user.signingkey` 存的是公钥**字符串**，但 `op-ssh-sign.exe` 期望**文件路径**：

```bash
git config --get user.signingkey
git config --get gpg.ssh.program
```

修复方式二选一（需要你确认，我不擅自改全局配置）：

```bash
# 方案 A：指向 1Password 生成的公钥文件（需先在 1Password 里启用 SSH agent）
git config --global user.signingkey "C:/Users/Berry/.ssh/1Password/<key-name>.pub"

# 方案 B：如果不需要签名，直接关掉
git config --global commit.gpgsign false
```

> 注：`C:\Users\Berry\.ssh\1Password\` 目前只有 `config`，没有 `.pub` 文件——说明 1Password 的 SSH agent 没在这台机器上导出密钥。你可能需要先在 1Password 桌面端 → Settings → Developer → 勾选 "Use the SSH Agent"。

---

## 三、需要一个上传 workflow（目前仓库里没有）

`grep upload-artifact .github/workflows/` 返回空——**没有任何 workflow 会生成 artifact**。这是你现在无论怎么跑都过不了门禁的直接原因。

要建一个 manual workflow，在**候选提交的确切 SHA**上跑并上传。注意：workflow 文件本身会改变提交，所以流程是这样的：

1. 先建好 workflow（提交到 `release/v0.1.1`）
2. 用这个新的 head SHA 跑全部验收
3. 证据里的 `commit` 和 PR head 都指向这个新 SHA

workflow 内容大致这样（`workflow_dispatch`，接收 base64 证据或从 release asset 下载）：

```yaml
name: Release Evidence Upload
on:
  workflow_dispatch:
    inputs:
      bundle_base64:
        description: base64-encoded evidence bundle zip
        required: true

jobs:
  upload:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Decode bundle
        run: |
          echo "${{ inputs.bundle_base64 }}" | base64 -d > bundle.zip
          mkdir -p bundle && unzip bundle.zip -d bundle
      - name: Self-check
        run: |
          pip install --quiet nothing || true
          python scripts/verify-release-evidence.py \
            --evidence bundle/evidence.json \
            --commit "${{ github.sha }}"
      - uses: actions/upload-artifact@v4
        with:
          name: release-acceptance
          path: bundle/
```

> 关键：`--commit "${{ github.sha }}"` 必须在 workflow 里用真实 SHA，不是硬编码。而且 workflow 必须在这个 SHA 上运行成功。

---

## 四、逐项怎么跑

### 环境准备

1. **干净 VM**：按 `docs/CLEAN_MACHINE_TESTING.md`，确认 `python`、`git`、`node` 命令全部失败
2. **打包**（在开发机）：
   ```bash
   git checkout release/v0.1.1
   powershell -ExecutionPolicy Bypass -File scripts/package-windows-release.ps1 -Version 0.1.1
   ```
   产物在 `dist/`，把 ZIP 拷进 VM

### 场景 → 证据映射

| 场景 | 在哪跑 | 证据文件 |
| --- | --- | --- |
| `clean-windows-package` | **干净 VM** | 首启截图 + 启动日志 |
| `cloud-image-journey` | 任意机器 + 真密钥 | 出图 PNG + 截图 |
| `comfyui-image-journey` | NVIDIA 机器 | 出图 + 引擎日志 |
| `webui-image-journey` | NVIDIA 机器 | 出图 + 引擎日志 |
| `project-reopen` | 任意 | 关前/重开后两张截图 |
| `masked-edit` | 任意（可云端） | 新图 + 截图 |
| `upscale-export` | 任意 | 导出文件 + 截图 |
| `task-recovery` | 任意 | 任务记录导出 |
| `external-ownership` | 任意 | 进程快照（`tasklist` 输出） |
| `install-update-recovery` | 任意 | 日志 + 截图 |
| `safe-exit` | 任意 | 截图（409 响应） |

### R/L 条目

大部分 R/L 条目可以用上面的场景证据交叉覆盖，但 **L01、L12 必须额外有打包版证据**。其余条目按 `docs/ACCEPTANCE_DOSSIER.md` 第 5 节的描述逐项跑。

### 缩放检查（R06）

Windows 设置 → 显示 → 缩放，分别切到 125% 和 150%，各截一张 1024×700 和 1440×900 的图。

---

## 五、填 evidence.json

以 `docs/acceptance/evidence-template.json` 为骨架，把 40 条全部改成：

```json
{
  "id": "L01",
  "status": "passed",
  "evidence_level": "packaged-live",
  "artifacts": ["artifacts/L01-clean-vm-startup.png", "artifacts/L01-startup.log"]
}
```

顶部的公共字段：

```json
"commit": "<40位完整SHA>",
"environment": {
  "os": "Windows 11 10.0.26200",
  "machine": "VM 名称 + 硬件",
  "tested_at": "2026-11-07T14:30:00+08:00"
},
"integrations": {
  "engines": ["ComfyUI 0.3.x / WebUI 1.10"],
  "providers": ["fal.ai", "OpenAI"],
  "models": ["sd_xl_base_1.0.safetensors"]
}
```

---

## 六、本地自检（必做，别等 CI）

```bash
python scripts/verify-release-evidence.py \
  --evidence ./bundle/evidence.json \
  --commit <你的40位SHA>
```

打印 `PASS` 才算 bundle 合格。

---

## 七、上传并引用

1. 把 bundle 打成 zip，base64 编码
2. 在候选 SHA 上手动触发 workflow，粘贴 base64
3. 拿到 `run_id`
4. 在 PR 正文加**恰好一行**：
   ```html
   <!-- berry-acceptance {"run_id":123456789,"artifact":"release-acceptance"} -->
   ```
5. 门禁自动重跑

---

## 八、诚实性

运行手册第六节写得很清楚：

> `verify-release-evidence.py` 只能证明"文件存在且非空"，无法证明内容真实。

如果某一项确实跑不了（比如没有云密钥），**正确做法是让门禁继续失败**，而不是放空壳文件。这与 `AGENTS.md` 的"不宣称未验证能力"一致。

---

## 九、最省事的路径

如果只是想先把 `dev` 的代码推上去，而不做完整发布：

- 保持 `release/v0.1.1` 待命（已经合好 `dev` 了）
- PR #249（`dev` → `main`）可以作为集成性提升，但它同样会触发验收门禁
- **两条路都绕不开验收**，因为门禁挂在所有 target `main` 的 PR 上

所以真正的问题不是"怎么绕过"，而是"什么时候跑验收"。如果你告诉我：
- 有没有 NVIDIA 显卡机器
- 有没有可用的云密钥
- 能不能建 VM

我可以直接把可执行的脚本和 workflow 写好，你跑就行。
