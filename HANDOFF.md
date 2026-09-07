# Bioflow Skill Handoff

Last reviewed: 2026-09-07
Scope: 当前源码、验证与分发状态；不是历史开发日志。

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
8. Publication Traceability：把已支持的结论接入论文和冻结发布；当前仍是未发布功能。

## 当前工作线

### A. 工作流文案：已完成限定范围验证

本仓库的SKILL入口及生命周期、恢复、监控三份reference已修正：最小下一步是原授权内的检查点，只读请求不转实现，运行中分支保持只读。

- 限定范围的文义/静态检查与只读复核已完成，不等于实际模型行为测试。
- 可随源码阅读的记录见[维护与验证摘要](docs/maintenance/20260907.md)。
- 原始哈希表是本地历史基线，不是禁止后续维护的永久冻结合同。
- 普通写入一律确认、claim检查自动落盘等条款仍未修改，不能称作整套规则已对齐。
- 账号规则及仓库外Skill的修改不属于本次Bioflow功能提交。

### B. Publication Traceability：源码验证和复核完成，未部署

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
当前没有将该层部署至Codex副本或插件wrapper，也没有真实论文包验收或Git发布。

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
| `~/.claude/skills/bioflow` | 指向本仓库的软链接 | 同上 |
| `~/.codex/skills/bioflow` | 独立副本 | 指定文案已更新；论文溯源功能未部署 |
| `plugins/bioflow/skills/bioflow` | 生成的分发副本 | 已知落后；不得冒充当前源码验收 |

运行payload只包含 `SKILL.md`、`references/`、`scripts/`、`assets/`、`agents/`。
README/HANDOFF/docs/reports/plugins等不发送至Codex运行包。
全部目标独有文件保持原样，包括payload目录内的旧脚本；需要清理时另列精确清单并确认。
不要手工修改生成的wrapper。源码通过后才讨论精确同步范围，不能为了测试PASS自动部署。

## 验证入口

```bash
# 源码阶段，不宣称运行/分发验收
bash scripts/test_skill.sh --source-only

# 完整维护/发布检查，仍检查插件与运行集成
bash scripts/test_skill.sh

# 预览而非部署
bash scripts/sync_install.sh
bash scripts/sync_plugin_wrapper.sh --check
```

测试包含小型临时项目、fake SLURM，以及临时Git仓库中的fixture提交/tag。
不要把测试命令用于真实分析目录，或把`--yes`当成用户授权。

## 下次接手顺序

1. 读取沿途规则、本文和当前 `git status --short --branch`。
2. 本轮源码维护已完成；先看验证报告，区分已完成源码/复核与尚未执行的部署、科学验收和发布。
3. 若继续B线，读取论文溯源合同及其fixture，不从历史日志重建参数。
4. 若继续规则文案，单独界定剩余冲突；不顺手改SOP/PaperPlot/账号规则。
5. 任何真实部署、Git写入或结果替换，先披露精确差异并获批。

## 历史与已知限制

重写前2379行原文及SHA256在本地完整保留；由于包含账号规则等无关记录，不纳入本次源码提交。
本地可选档案路径：`docs/history/HANDOFF_20260907_Pre_Maintenance.md`，哈希记录在本地`reports/maintenance-20260907/Baseline.tsv`。
克隆仓库不要求这些本地档案存在；已提交的功能沿革用`git log`和`git show <commit>:HANDOFF.md`查看，当前结论以仓库内维护摘要为准。

静态预检不是sandbox，项目状态审计是有界启发式；科学规则只覆盖已有证据支持的范围。
不要为美化目录、减少告警或获得PASS而改写正式结果、降低科学门槛或丢弃审计证据。
