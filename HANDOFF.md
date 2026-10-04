# Bioflow Skill Handoff

Last reviewed: 2026-10-05
Scope: 当前源码、验证与分发状态；不是历史开发日志。

## 本次更新：规则冲突修复与行为评测（2026-10-04/05）

- 三处已知规则冲突已修复（`637f7c7`，wrapper `e1ea2af`）：低风险项目内编辑简要说明后直接做，`confirm_action`只用于受控动作；只读claim检查不写审计行，持久化审计需披露并确认；Draft阶段阻止受管执行。
- 新增运行中作业规则（`f86b607`，wrapper `8ce5ad5`）：`SKILL.md`低风险清单后的“Exception for active jobs”及`references/executor-safety.md`同义段落。脚本若是排队中/运行中任务登记的`Script_Path`，不原地修改，修正写成新脚本或版本，当前作业结束前不重投。
- 行为评测脚本`evals/behavior/run_eval.py`（`6181a66`）：真实pi会话、一次性layout-v2项目、记录日志的模拟SLURM，7个场景机械判分；`--skill-dir`做新旧A/B。不在`scripts/`内，不属于运行payload，也不进`test_skill.sh`。沙箱默认`projects/zz-demo/`，已清理，运行时自动重建。
- 评测结论（样本小，仅作方向证据）：
  - gpt-6-astra（修复前）：S1–S6全过，S7 0/3；B1修复前后A/B未改变S2/S7。
  - gpt-6-luna：旧规则S7 1/2有效，新规则2/2有效，回答明确引用该规则；S2两版均3/3。
  - kimi-k3：读了新规则即通过，未读即失败。
  - deepseek-v4.1-flash：12次有效运行仅1次从头读`SKILL.md`。复测轮遇opencode-go额度`429`，全部无效。
- 模型使用约定：执行类委托默认用pi `opencode-go/deepseek-v4.1-flash`。提示词开头须要求完整读`SKILL.md`，并贴入相关关键规则（推测性补救，未测）。需要自主遵守bioflow规则的任务用gpt-6-luna或astra。
- 已知外部问题：openai-codex OAuth失效（Codex CLI与pi共用同一refresh token，`refresh_token_reused`），需`codex login`并在pi内`/login`分别登录，不再复制`auth.json`。Codex插件校验器`plugin-creator`缺失，wrapper同步时跳过Codex插件校验，Claude校验通过。
- 测试：`bash scripts/test_skill.sh --source-only` 201 PASS、0 FAIL（`logs/test_source_only_running_fix.log`）。

## 上次更新：图件修订的保存规则（2026-09-13）

- 用户要求同图同目录更新，图片修订不再逐版建立目录。唯一规则正文位于 `references/project-layout.md` 的 `Figure revisions: same package, file-level versions`；Skill入口、路径/Workspace说明和README仅对齐并引用。分析数据版本、覆盖批准和冻结保护未放宽。
- 布局回归测试新增同一图包仅保留`_v2.pdf/.png`文件名的正例。2026-10-04 `bash scripts/test_skill.sh --source-only` 全套PASS（201项PASS、0 FAIL，仅预期SKIP运行集成）；本地日志`logs/test_source_only_20261004_110623.log`。
- Pi源码入口可读；经具体批准，Codex副本已同步5个变更文件并逐文件SHA256核对。备份为本地`reports/Figure_Revision_Runtime_Backup_20260913.json`。
- 源码已提交为`e811402`；plugin wrapper经批准用`sync_plugin_wrapper.sh --yes`同步这5个文件，`--check`无漂移、插件校验通过，提交为`364eebf`。推送状态以`git status --short --branch`为准。

## 项目定位

Bioflow 是给 Agent 使用的生信工作流工具集，不是一条固定分析流水线。
Agent 根据明确的研究目标和项目证据选择路线；脚本负责确定性检查与受控执行。
退出码为零、SLURM COMPLETED、候选输出存在，均不等于科研验收或发布完成。

- `SKILL.md`：唯一 Skill 执行入口与任务路由。
- `references/`：生命周期、布局、方法、资源、证据和验收合同。
- `scripts/`：检查器、生成器、受控执行器及回归测试。
- `assets/`：项目和调度模板；`agents/`：Agent 元数据。
- `README.md`：用户与维护者指南；本文：当前状态和接手入口。
- `docs/maintenance/`：随源码保存的精简验证摘要；本地`docs/history/`和`reports/`保存原始历史与开发证据，不是运行包。

## Git 基线

- 仓库：`/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow`。
- 当前分支：`main`。
- 本次维护的开发起点：`524be33 feat: add project records layer`，2026-09-05；它不是永久代表当前HEAD的记录。
- 最新完成并已提交推送：`7959e94 chore: sync Bioflow plugin payload and record deployment`；包含wrapper/部署文档共20个文件。当前检查本地tracking一致，之后以Git为准。
- 本地可选提交发布回执：`logs/deployment-publish-20260907/Receipt.json`（可选，不要求克隆仓库存在）。
- 前一里程碑：`c4d180e feat: add layout v2 governance and Git safety gate`，2026-09-04。
- 提交组织：功能与项目文档分开。当前HEAD、暂存区和未推送提交数以`git log`、`git status --short --branch`为准；未fetch时不推断远端实时状态。
- 本地可能保留未跟踪的原始报告和备份；不要执行`git add -A`、reset或clean将其混入或删除。
- 提交、推送、tag、部署均须另行披露和批准；本文不授予这些动作。

## 已建立的架构

1. 生命周期：九阶段接管、输入/计划、运行、验收和交付；状态记录是证据指针。
2. 执行安全：generate → preflight → confirmed submit，资源由输入与历史证据决定。
3. Workspace Steward：Agent 明确模块依赖与路径；脚本检查 Reviewed 指纹、路由和边界。
4. Layout v2：config/rawdata/scripts/logs/tmp/results/docs/manuscripts；已有 legacy 不自动迁移。
5. 结果身份：一个 Analysis_Key 对应一个结果模块；版本放 versions/VNN，图使用稳定 F-ID。
6. Evidence-to-Claim：结果合同区分 PASS/WARN/BLOCK/UNCERTAIN，不从缺失规则推断有效。
7. Project Records：状态、研究日志、Log_Index、Decision_Index 和 changelog；已进入524be33。
8. Publication Traceability：把已支持的结论接入论文和冻结发布；源码和payload部署已完成，并随`7959e94`保存远端；不等于真实科学验收。

## 当前工作线

### A. 工作流文案：已完成限定范围验证

本仓库的SKILL入口及生命周期、恢复、监控三份reference已修正：最小下一步是原授权内的检查点，只读请求不转实现，运行中分支保持只读。

- 限定范围的文义/静态检查与只读复核已完成，不等于实际模型行为测试。
- 可随源码阅读的记录见[维护与验证摘要](docs/maintenance/20260907.md)。
- 原始哈希表是本地历史基线，不是禁止后续维护的永久冻结合同。
- 普通写入一律确认、claim检查自动落盘等条款仍未修改，不能称作整套规则已对齐。
- 账号规则及仓库外Skill的修改不属于本次Bioflow功能提交。

### B. 源码与payload部署检查完成

目标链：Claim_ID → Version_ID → Figure_ID → source-data TSV → manuscript anchor → Release Manifest → commit/tag。

入口：
- [references/publication-traceability.md](references/publication-traceability.md)
- [scripts/publication_trace_audit.py](scripts/publication_trace_audit.py)
- [scripts/test_publication_trace_audit.py](scripts/test_publication_trace_audit.py)
- `assets/project-templates/Claim_Evidence_Map.tsv`
- `assets/project-templates/Release_Manifest.yaml`

已实现Draft/Reviewed映射和Frozen closure；保持Version/Figure原有表头，避免重复权威表。
`source_commit_sha`与`release_tag`分开，避免Manifest包含自身commit哈希的循环。
本轮先修复三个已知缺陷，再关闭独立复核发现的文件集合、Git读取/tag身份、版本/图路径、逐图源表及acceptance下游重读问题；正反例和最终源码套件均PASS，已发现阻塞经复核关闭。
本次已按批准范围将Codex与plugin wrapper 139-file payload同步到 `9589449c25f839cfbdda97ffbc6343a4d3810c78`，并通过139个文件的内容SHA256、字节数、模式、无删除及CLI入口检查；源payload对应`9589449`，`7959e94`仅保存wrapper/部署文档，不是新的payload版本。这不代表真实论文包或科学验收，软件提交状态以Git为准。部署摘要见[deployment summary](docs/maintenance/deployment-20260907.md)。

### C. 当前维护：文档职责、同步边界、源码独立测试

范围与过程：[维护与验证摘要](docs/maintenance/20260907.md)。

源码修改、测试和本轮独立复核已完成：
- 历史HANDOFF原文归档，本文改为当前接手页。
- Codex同步只发送明确的运行payload，保留全部目标独有文件，不自动清理；不是严格镜像。
- `test_skill.sh --source-only`仅验证源码；默认完整模式继续要求运行集成和插件一致性。
- 同步器、测试模式增加隔离fixture；B线最新边界回归已纳入源码套件。

最终`--source-only`全套检查PASS（本地隔离临时目录，约67秒）；过程中的一次180秒超时也已保留，不记为PASS。
[维护与验证摘要](docs/maintenance/20260907.md)记录复核关闭与分发限制，不得将源码PASS当成已部署。

### D. 后续两轮审查：定向验证完成

第一轮修复同步目标拼写、元数据父目录软链接和超深anchor漏检，并按用户选择将v1发布角色对齐为四类。
第二轮补齐逐文件Shell语法检查、去重卡片验证，在单次paper审计内复用索引/源表验证，保留路径和逐Claim告警。
两轮顺序完成，定向检查均PASS；没有重复完整基线。前述67秒全套PASS是本轮之前的维护证据，不冒充新版本全套重跑。
修正、反例、调用计数和限制见[维护与验证摘要](docs/maintenance/20260907.md)；原始两轮审阅记录保留在本地。

## 源码、运行副本与分发

| 入口 | 当前模型 | 状态边界 |
|---|---|---|
| 本仓库 | 开发源码 | 当前源码提交状态以Git为准，不等于分发发布 |
| `~/.pi/agent/skills/bioflow` | 指向本仓库的软链接 | 源码文件实时可见；会话需重新加载 |
| `~/.claude/skills/bioflow` | 指向本仓库的软链接 | 2026-10-05重建（此前链接实际不存在）；同上 |
| `~/.codex/skills/bioflow` | 独立副本 | 2026-10-05经批准`sync_install.sh --yes`同步至`f86b607`规则（`SKILL.md`、`executor-safety.md`逐字一致）；非严格镜像，非科学验收 |
| `plugins/bioflow/skills/bioflow` | 生成的分发副本 | wrapper 139-file payload已同步到 `9589449c25f839cfbdda97ffbc6343a4d3810c78`；文件/元数据/CLI入口检查通过；`7959e94`仅保存wrapper/部署文档，不是新的payload版本 |

运行payload只包含 `SKILL.md`、`references/`、`scripts/`、`assets/`、`agents/`。
README/HANDOFF/docs/reports/plugins等不发送至Codex运行包。
全部目标独有文件保持原样，包括payload目录内的旧脚本；需要清理时另列精确清单并确认。
不要手工修改生成的wrapper。本次精确同步范围已按批准清单完成；本部署快照独立提交，实际commit/push状态以Git为准。

## 验证入口

```bash
# 源码阶段，不宣称运行/分发验收
bash scripts/test_skill.sh --source-only

# 完整维护/发布检查，仍检查插件与运行集成
bash scripts/test_skill.sh

# 预览而非部署
bash scripts/sync_install.sh
bash scripts/sync_plugin_wrapper.sh --check

# 真实Agent行为评测（调用模型、计费；不进test_skill.sh）
python3 evals/behavior/run_eval.py --scenarios S7_running_edit,S2_lowrisk_edit --reps 3 \
  --model opencode-go/deepseek-v4.1-flash --skill-dir <导出的Skill副本>
```

评测汇总`Summary.tsv`区分有效/无效运行与是否读过`SKILL.md`；崩溃或限流运行记为INVALID，不计入通过。

测试包含小型临时项目、fake SLURM，以及临时Git仓库中的fixture提交/tag。
不要把测试命令用于真实分析目录，或把`--yes`当成用户授权。

## 下次接手顺序

1. 读取沿途规则、本文和当前 `git status --short --branch`。
2. 截至`6181a66`，源码、wrapper、Codex副本和Claude/pi软链接均为最新规则，已推送。不自动重复同步或测试。后续按真实使用问题迭代；规则修改后可用`evals/behavior/`做新旧A/B，评测模型须能稳定读取`SKILL.md`（见上文模型约定）。科学验收仍未进行。
   待办：openai-codex重新登录后，可用astra复测S7确认修复。
3. 若继续B线，读取论文溯源合同及其fixture，不从历史日志重建参数。
4. 若继续规则文案，单独界定剩余冲突；不顺手改SOP/PaperPlot/账号规则。
5. 任何真实部署、Git写入或结果替换，先披露精确差异并获批。

## 历史与已知限制

重写前2379行原文及SHA256在本地完整保留；由于包含账号规则等无关记录，不纳入本次源码提交。
本地可选档案路径：`docs/history/HANDOFF_20260907_Pre_Maintenance.md`，哈希记录在本地`reports/maintenance-20260907/Baseline.tsv`。
克隆仓库不要求这些本地档案存在；已提交的功能沿革用`git log`和`git show <commit>:HANDOFF.md`查看，当前结论以仓库内维护摘要为准。

静态预检不是sandbox，项目状态审计是有界启发式；科学规则只覆盖已有证据支持的范围。
不要为美化目录、减少告警或获得PASS而改写正式结果、降低科学门槛或丢弃审计证据。
