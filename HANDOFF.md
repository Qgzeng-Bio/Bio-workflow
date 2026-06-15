# Bio-Workflow Skill Handoff

Last updated: 2026-06-15 — KMERIA pilot failure feedback

---

## 2026-06-15 — KMERIA pilot 失败反馈回流

### 背景 / 目标

用户在真实项目
`/data9/home/qgzeng/projects/2-C_quinoa/10-population_structure/4-kmer-GWAS`
中使用本 skill 从空目录构建 KMERIA workflow，并经历 pilot/benchmark 多次失败重提。目标是只读审查真实日志，把可泛化的问题固化进 `bio-workflow`，不修改该 KMERIA 项目、不重提作业。

### 关键发现

- `845500` 失败根因不是资源：日志明确提示 `kmeria count` 输出格式与 `kctm` 期望的 KMC sorted database 格式不兼容，随后在 `kctm_job.sh` 读取 `*_k31.txt` 时失败。
- `845510` 快速失败与 `.err` 为空；结合脚本可疑点，`set -euo pipefail` 下的展示型管道（如 `ls ... | head`）会把预览命令变成作业失败风险。
- `845518` benchmark 失败只输出 `FAIL t=4`，没有字面 `error`；需要保留完整 stderr/time log，不能只 grep `error|invalid`。
- `project_state_audit.sh --check-queue` 在当前环境无法访问 SLURM accounting 时，曾被旧日志里的“脚本生成成功”误导为 `Complete_unvalidated`；已改为在最新日志未终止时输出 `Queued_or_running / Queue_state_unknown`。

### 已完成变更

- `SKILL.md` / `skills.md`
  - 新增 K-mer GWAS / KMERIA task route。
  - 写脚本规则新增：避免未保护的 `| head` 预览管道；保留完整 stage stderr/time log；生成器出现格式不兼容警告时先停下。
- `references/software-resource-cards.md`
  - 新增 `KMERIA` 资源卡，覆盖 count/matrix/association 阶段、格式兼容、pilot、磁盘增长、长短参数和重跑风险。
- `references/validation-checklists.md` / `references/resume-protocol.md`
  - 增加 KMERIA 格式链路验收、pipefail/preview 管道诊断、SLURM 查询不可用时的保守 resume 规则。
- `scripts/slurm_preflight.sh`
  - 新增未保护 `| head` 检查，有风险时 `FAIL`。
  - 新增 KMERIA wrapper/count/kctm 静态提示。
  - 将 `kmeria` 加入大计算命令检测。
- `scripts/slurm_failure_triage.sh`
  - 新增 `KMERIA_FORMAT_INCOMPAT`、`KMERIA_COUNT_FAILED`、`SHELL_PIPEFAIL_SIGPIPE` 分类。
  - 修复 sacct/slurmdbd 不可访问时误判为项目权限错误的问题。
- `scripts/project_state_audit.sh`
  - 收紧 terminal completion 模式，不再把 “All scripts generated successfully” 或局部 stage 成功当作全流程完成。
  - 新增最新未终止运行日志检测；队列/accounting 不可用时输出 `Queue_state_unknown`，并让建议 TSV 的 `Job_ID` 跟主证据一致。

### 命令 / 测试结果

已运行：

```bash
bash -n scripts/project_state_audit.sh
bash -n scripts/slurm_preflight.sh
bash -n scripts/slurm_failure_triage.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
rg -n "KMERIA|KMERIA_FORMAT_INCOMPAT|SHELL_PIPEFAIL_SIGPIPE|Queue_state_unknown|pipe-to-head|count output format" SKILL.md skills.md references scripts
```

真实日志回归：

- `slurm_failure_triage.sh --err logs/km_pilot_845500.err --out logs/km_pilot_845500.out`
  输出 `Failure_Type: KMERIA_FORMAT_INCOMPAT`。
- `slurm_failure_triage.sh --err logs/km_bench_845518.err --out logs/km_bench_845518.out`
  输出 `Failure_Type: KMERIA_COUNT_FAILED`。
- `slurm_preflight.sh --script scripts/10_pilot.sbatch --mode debug`
  报出相对日志路径、未保护 `| head`、`rm -rf`，并给出 KMERIA 格式链路 WARN。
- `project_state_audit.sh --project <KMERIA项目> --max-depth 3 --max-files 1000 --check-queue`
  在 SLURM 查询不可用时输出 `Queued_or_running / Queue_state_unknown`，证据指向 `logs/km_pilot_845512.out` 和 Job_ID `845512`。

新增 `/tmp/bio-workflow-kmeria-regression/` 夹具：

- `preflight_good.sbatch`: `PASS=15 WARN=0 FAIL=0`。
- `preflight_bad_head.sbatch`: 仅因 `Unguarded pipe to head` 失败，`FAIL=1`。

### caveats / 注意事项

- 当前只更新 skill，不修改 KMERIA 项目脚本和结果目录，也没有重提/取消任何作业。
- 当前环境偶发 `sacct`/`squeue` socket 权限错误；audit/triage 已改为保守处理，但真实队列状态仍需在可访问 SLURM 的会话里复查。
- `SHELL_PIPEFAIL_SIGPIPE` 对 845510 需要 job accounting 或人工脚本上下文；如果只有空 `.err` 和短 `.out`，triage 会保守返回 UNKNOWN。

### 下一步建议

1. 等当前 KMERIA pilot/benchmark 到终态后，再用新版 audit + triage 复查最新日志。
2. 如要修 KMERIA 项目本身，优先解决 count→kctm 格式兼容，再改 `ls|head`、相对日志路径和 `rm -rf results/pilot`。
3. 后续可为 KMERIA 增加专门的项目模板或 `scripts/kmeria_preflight.sh`，但应基于这次 pilot 的终态结果再定。

---

## 2026-06-15 — GitHub 发布与 README 同步

### 背景 / 目标

用户确认 GitHub 仓库 `https://github.com/Qgzeng-Bio/Bio-workflow` 用于托管当前 `bio-workflow` skill。目标是把当前 skill 文件发布到远端，并保留远端已有初始 README。

### 已完成变更

- 新增本地文件 `README.md`
  - 内容来自远端已有 `README.md`：
    `# Bio-workflow` 和 `bioinformatics workflow`。
- 使用临时 git 工作副本 `/tmp/bio_workflow_push_repo` 完成发布
  - 当前项目目录里的 `.git/` 是异常只读空目录，无法原地初始化。
  - 临时副本包含 `SKILL.md`、`skills.md`、`HANDOFF.md`、`agents/`、`references/`、`scripts/` 和远端 `README.md`。
- GitHub 远端更新
  - 首次 skill 提交：`1a423bd Initial bio-workflow skill`。
  - 合并远端 README 后推送：`599c74f Merge remote-tracking branch 'origin/main'`。
  - 远端 `main` 已包含 11 个文件：`README.md`、skill 主文件、handoff、agent metadata、3 个 references、3 个 scripts。

### 命令 / 检查

已运行的关键命令：

```bash
git init -b main
git add HANDOFF.md SKILL.md skills.md agents references scripts
git commit -m "Initial bio-workflow skill"
git remote add origin https://github.com/Qgzeng-Bio/Bio-workflow.git
git remote set-url origin git@github.com:Qgzeng-Bio/Bio-workflow.git
git fetch origin
git merge origin/main --allow-unrelated-histories --no-edit
git push -u origin main
git ls-tree -r --name-only origin/main
```

结论：

- `git push -u origin main` 使用 SSH remote 成功。
- 远端原本不是完全空仓库，已有 `README.md` 初始提交；已合并保留，没有强推覆盖。
- 当前工作目录已补回 `README.md`，与远端文件集保持一致。

### caveats / 注意事项

- 当前工作目录 `/data9/home/qgzeng/projects/3-Biotools_create/bio-workflow` 仍不是正常 git repo，因为 `.git/` 是异常只读空目录。
- 后续若要在当前目录正常 `git status` / `git commit`，建议重新 clone 到新目录，或在可写环境下处理异常 `.git/` 后重新接入远端。
- `/tmp/bio_workflow_push_repo` 是发布用临时仓库，不是长期维护目录。

### 下一步建议

1. 使用 GitHub 远端作为正式 source of truth。
2. 找合适时机重新 clone：
   `git clone git@github.com:Qgzeng-Bio/Bio-workflow.git <new-dir>`。
3. 若继续在当前目录开发，先解决异常 `.git/`，否则本地无法正常追踪改动。

---

## 2026-06-15 — Review fixes：扫描边界、权限优先级和误报修正

### 背景 / 目标

根据整体 review 发现的 5 个风险点做小范围修复：audit 不能隐性大扫描，写入权限需要尊重更近 `AGENTS.md`，SLURM preflight 不能误报合法短参数，`Analysis_ready` 不能被旧验收记录污染，UNKNOWN 失败不能用退出码 0 混过去。

### 已完成变更

- `scripts/project_state_audit.sh`
  - 新增 `--max-files 1000`，每个固定目录最多采样指定数量文件。
  - 拒绝宽根目录：`/`、`/data9`、`/data9/home`、`/data9/home/qgzeng`、`/data9/home/qgzeng/projects`。
  - 明确默认 `--project .`，不会向上回溯到父目录或账户根目录。
  - 达到扫描上限时输出 `[WARN] Bounded scan warnings`。
  - `workflow_status.tsv` 只接受最新一条 `Stage=Analysis_ready` 且 `Status=Validated/Accepted/Pass/Passed/Analysis_ready`，并要求证据或输出路径存在。
- `SKILL.md`
  - 写入权限改成：始终先应用最近的 `AGENTS.md`；若没有更严格的 `AGENTS.md`，才使用 skill 的低风险默认动作。
  - resume 入口补充：默认当前目录，不向上扫描；全盘/账户级扫描必须用户确认并给出 bounded plan。
- `references/resume-protocol.md` 和 `references/validation-checklists.md`
  - 同步 `--max-files`、当前目录优先、宽根目录拒绝规则。
- `scripts/slurm_preflight.sh`
  - 修复合法 compact short option 误报，支持 `#SBATCH -c16`、`#SBATCH -n4` 这类写法。
- `scripts/slurm_failure_triage.sh`
  - UNKNOWN 失败证据退出码改为 2；已分类失败仍退出 1；WARN/无失败证据退出 0。
- `skills.md`
  - 已重新同步为 `SKILL.md` 的 byte-for-byte mirror。

### 验证命令 / 结果

已运行：

```bash
bash -n scripts/project_state_audit.sh
bash -n scripts/slurm_preflight.sh
bash -n scripts/slurm_failure_triage.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
```

针对性夹具：

- `/tmp/bio_workflow_fix_20260615/limit`: `--max-files 50` 截断为 50 个输入，并输出 bounded scan WARN。
- `/data9/home/qgzeng/projects`: audit 拒绝宽根目录，退出 1。
- `/tmp/bio_workflow_fix_20260615/analysis_latest`: 旧 `Analysis_ready` + 最新 `Complete_unvalidated` 时，audit 正确输出 `Complete_unvalidated / Needs_validation`。
- `/tmp/bio_workflow_review_20260615/short_c.slurm`: `#SBATCH -c16` 不再误报，preflight `PASS=13 WARN=0 FAIL=0`。
- `/tmp/bio_workflow_fix_20260615/triage/unknown.err`: UNKNOWN 失败证据退出 2。

### caveats / 注意事项

- `project_state_audit.sh` 仍是启发式接管工具；达到 `--max-files` 后要把证据视作可能不完整。
- 宽根目录拒绝是脚本级保护；如果用户确实需要账户级盘点，应单独设计 bounded plan，而不是直接改大 `--max-depth`。
- `workflow_status.tsv` 的最新行语义更严格；旧项目若没有维护最新状态行，可能会回落到 `Complete_unvalidated`，这是保守行为。

---

## 2026-06-15 — Resume layer：从任意阶段接管项目

### 背景 / 目标

上一版 `bio-workflow` 已经能规划、写脚本、预检、提交前说明和结果验收，但默认思路仍偏“从头开始”。本轮新增 Resume Protocol，让后续 agent 先判断项目当前状态，再决定最小下一步动作，覆盖只有输入、脚本待提交、任务运行中、任务失败、结果待验收、结果已验收待分析六类入口。

### 已完成变更

- 更新 `SKILL.md`
  - frontmatter 增加 project resume/takeover 触发语义。
  - 在 `Task routing` 前新增 `Resume an existing project` 强制入口。
  - 明确不默认从头规划：先用只读状态快照，再进入 input / preflight / monitor / failure / validation / analysis。
  - 固定 resume 输出形状：`📌 当前阶段`、`🔎 证据`、`⚠️ 阻塞`、`🛠️ 下一步最小动作`。
- 新增 `references/resume-protocol.md`
  - 定义 6 个状态：`Input_ready`、`Script_ready`、`Queued_or_running`、`Failed`、`Complete_unvalidated`、`Analysis_ready`。
  - 每个状态包含判定证据、禁止动作、下一步入口和常见风险。
  - 定义 `reports/workflow_status.tsv` 标准列：
    `Stage	Status	Evidence_Path	Job_ID	Exit_Code	Input_Path	Output_Path	Next_Action	Updated_Time`。
- 新增 `scripts/project_state_audit.sh`
  - 只读；默认检查 `config/ data/ scripts/ logs/ results/ reports/ tmp/`。
  - 默认 `--project . --max-depth 3`；不会扫 `/data9` 大目录。
  - 输出状态候选、最近脚本/日志/结果、证据路径、推荐最小下一步和可复制为 `workflow_status.tsv` 的 TSV 行。
  - `--check-queue` 只在发现 job ID 后调用 `squeue`/`sacct`。
- 新增 `scripts/slurm_failure_triage.sh`
  - 接口：`--jobid <id>` 或 `--err <file>`，可选 `--out <file>` / `--logs-dir <dir>`。
  - 分类：OOM、TIMEOUT、missing input、permission、env/tool、segfault、disk full、format/chromosome mismatch、network/proxy。
  - 输出失败类型、证据和最小修复建议；不自动重提。
- 更新 `references/validation-checklists.md`
  - 新增 `Resume checklist`。
  - 强化 `Complete_unvalidated` 必须先验收，不能直接进入生物学解释。
- 更新 `agents/openai.yaml`
  - 默认提示补上 resume/takeover 语义。
- 同步 `skills.md`
  - 仍保持为 `SKILL.md` 的 byte-for-byte mirror。

### 验证命令 / 结果

已运行：

```bash
bash -n scripts/project_state_audit.sh
bash -n scripts/slurm_failure_triage.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
rg -n "Resume an existing project|workflow_status.tsv|project_state_audit.sh|slurm_failure_triage.sh|Input_ready|Script_ready|Queued_or_running|Failed|Complete_unvalidated|Analysis_ready" SKILL.md skills.md references scripts HANDOFF.md
```

验证结论：

- `quick_validate.py` 输出 `Skill is valid!`
- `cmp -s SKILL.md skills.md` 退出 0。
- 两个新增脚本 `bash -n` 均退出 0。
- 关键入口、`workflow_status.tsv`、两个新增脚本名和 6 个状态名均可被 `rg` 检出。

`/tmp/bio_workflow_resume_fixtures_20260615/` 夹具测试结果：

- `input_only`: audit 输出 `Input_ready / Needs_planning`。
- `script_ready`: audit 输出 `Script_ready / Needs_preflight`。
- `running`: audit 输出 `Queued_or_running / Needs_monitoring`。
- `failed`: audit 输出 `Failed / Needs_triage`。
- `complete_unvalidated`: audit 输出 `Complete_unvalidated / Needs_validation`。
- `analysis_ready`: audit 输出 `Analysis_ready / Validated`。

`slurm_failure_triage.sh` 夹具测试结果：

- OOM `.err`: 输出 `Failure_Type: OOM`，退出 1。
- TIMEOUT `.err`: 输出 `Failure_Type: TIMEOUT`，退出 1。
- missing input `.err`: 输出 `Failure_Type: MISSING_INPUT`，退出 1。
- command-not-found `.err`: 输出 `Failure_Type: ENV_TOOL`，退出 1。

`scripts/slurm_preflight.sh` 回归测试：

- 正样例 `run_test.slurm`: `PASS=13 WARN=0 FAIL=0`，退出 0。
- 负样例 `bad_time.slurm`: normal 分区含 `#SBATCH --time`，`PASS=12 WARN=0 FAIL=1`，退出 1。

### caveats / 注意事项

- `project_state_audit.sh` is heuristic. It can surface multiple candidates when old logs and new scripts coexist; agent must choose the primary state from evidence.
- `slurm_failure_triage.sh` classifies common log patterns only. Unknown failures still require reading the full `.err/.out` and relevant script.
- Neither script writes `reports/workflow_status.tsv`; writing project state remains a user-confirmed action.
- Real project runs may need tuning after first false positives/false negatives appear.

### 下一步建议

1. 在真实项目上首次使用 `project_state_audit.sh` 时，把误报/漏报最小化成 `/tmp` fixture，再微调规则。
2. 后续可新增一个 `scripts/write_workflow_status.sh --dry-run`，但只有在用户确认“允许写状态表”后再做。
3. 如果 SLURM 日志命名不统一，优先在项目脚本里统一 `%j_%x.out/.err`，再依赖 resume audit。

---

## 2026-06-15 — 推进到实打实 9 分的补强

### 背景 / 目标

根据上一轮 review plan，对当前 `bio-workflow/` 做小范围但可执行的补强：把“提交前靠 agent 自觉检查”的规则固化成只读预检脚本，同时补齐藜麦全流程常见软件资源卡、任务路由和标准验收清单。目标是让后续 agent 在写 SLURM 脚本、估算资源、提交前说明和结果验收时有明确入口。

### 已完成变更

- 新增 `scripts/slurm_preflight.sh`
  - 只读检查，不修改用户脚本。
  - 输入：`--script <slurm_script>`，可选 `--mode normal|debug|fat|fat2|high`。
  - 输出：`PASS/WARN/FAIL`；有任意 `FAIL` 时退出码为 1，只有 `WARN` 不失败。
  - 覆盖检查：`#SBATCH --time`、日志绝对路径和 `%j/%x`、array `%N` 并发上限、`set -euo pipefail`、`rm -rf`、保护目录 `/data9/home/qgzeng/data/` 与 `/data9/home/qgzeng/tools/` 写入、proxy 变量、`admin2`、大计算命令缺 CPU/MEM 声明。
- 更新 `SKILL.md`
  - 新增 `Task routing`：assembly、Hi-C scaffolding、annotation、RNA-seq、SNP/INDEL/SV/synteny、pangenome、download、plotting/reporting。
  - 在资源估算段落扩展软件卡入口。
  - 在 `Preflight before submitting` 强制要求先运行 `scripts/slurm_preflight.sh --script <slurm_script>`。
  - 在结果验收段落引用 `references/validation-checklists.md`。
  - 新增 skill 维护规则：`SKILL.md` 为正式入口，`skills.md` 保持 byte-for-byte mirror。
- 同步 `skills.md`
  - 已用 `cp SKILL.md skills.md` 同步，`cmp -s SKILL.md skills.md` 通过。
- 扩展 `references/software-resource-cards.md`
  - 新增资源卡：`hifiasm`、`Juicer and 3D-DNA`、`BRAKER and MAKER`、`bcftools and GATK`、`fastp, FastQC, and MultiQC`、`MUMmer and plotsr`、`BUSCO`、`QUAST`。
  - 每张卡包含 Typical use、Parallelism、Memory drivers、Starting points、Preflight checks、Red flags。
- 新增 `references/validation-checklists.md`
  - 包含 input、environment、resource estimation、SLURM pre-submit、failure diagnosis、result acceptance、figure acceptance、skill maintenance 分层验收清单。

### 验证命令 / 结果

已运行：

```bash
bash -n scripts/slurm_preflight.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
rg -n "admin2|#SBATCH --time|proxychains|http_proxy|find /data9|MAX_PARALLEL|slurm_preflight.sh|hifiasm|Juicer|3D-DNA|BRAKER|MAKER|bcftools|GATK|fastp|FastQC|MultiQC|MUMmer|plotsr|BUSCO|QUAST|validation-checklists" SKILL.md skills.md references scripts
```

验证结论：

- `quick_validate.py` 输出 `Skill is valid!`
- `cmp -s SKILL.md skills.md` 退出 0。
- `bash -n scripts/slurm_preflight.sh` 退出 0。
- 关键规则与新增软件名均可被 `rg` 检出。

### 预检脚本样例测试

构造了 4 个 `/tmp` 小型 SLURM 文本样例，仅用于静态预检；未提交作业，未运行样例中的任何生信命令。

- `/tmp/bio_workflow_preflight_pass_20260615.slurm`
  - normal 模式无 `--time`、日志绝对路径、有 CPU/MEM、严格模式完整。
  - 结果：退出 0，`PASS=13 WARN=0 FAIL=0`。
- `/tmp/bio_workflow_preflight_time_fail_20260615.slurm`
  - normal 模式含 `#SBATCH --time=01:00:00`。
  - 结果：退出 1，正确报 `#SBATCH --time is present in normal mode`。
- 同一个 time 样例加 `--mode debug`
  - 结果：退出 0，正确降级为 `WARN`。
- `/tmp/bio_workflow_preflight_mixed_fail_20260615.slurm`
  - array 无 `%N`、日志相对路径、strict mode 不完整、proxy、保护目录写入、`samtools sort` 缺 CPU/MEM 声明。
  - 结果：退出 1，`PASS=4 WARN=1 FAIL=8`。
- `/tmp/bio_workflow_preflight_cpu_no_mem_20260615.slurm`
  - 有 CPU、无内存声明、含 `minimap2`。
  - 结果：退出 1，正确报大计算命令缺 SLURM CPU/MEM 声明。

### 当前结论

- 当前 `bio-workflow` 已有可执行的 SLURM 提交前安全闸：后续遇到 SLURM 脚本，应先跑 `scripts/slurm_preflight.sh --script <file>`，再给用户提交建议。
- `SKILL.md` 和 `skills.md` 已同步，不再是两份分叉正文。
- 资源卡覆盖从“基础常用工具”扩展到 assembly、Hi-C、annotation、variant、QC、synteny plotting、completeness/assembly evaluation，能支撑藜麦基因组全流程的起步估算。
- 验收清单已把“退出码 0 不等于成功”落成可复用检查入口。

### caveats / 注意事项

- 当前目录不是 git 仓库，无法用 git diff/status 记录变更；只能依靠文件路径、验证命令和 `cmp`/`rg` 结果追踪。
- shell 初始化会输出 `yp_bind_client_create_v3`、用户/组名解析警告，这是当前环境噪声；不影响本轮验证命令退出码。
- `scripts/slurm_preflight.sh` 是启发式静态检查，不会理解所有 Bash 动态变量、函数封装或复杂重定向；遇到 `WARN` 或疑似误报时应人工解释，而不是盲目提交。
- `/tmp` 测试样例是临时夹具，不属于 skill 正式资产。

### 下一步建议

1. 在真实项目里首次使用 `scripts/slurm_preflight.sh` 时，先对一个已知合格脚本和一个已知问题脚本各跑一次，观察是否需要微调规则。
2. 后续若出现误报/漏报，把对应 SLURM 脚本最小化成 `/tmp` 测试夹具，再补进预检脚本测试思路。
3. 若准备把当前 project skill 安装或同步到全局 skill 目录，再单独做一次目标目录 `quick_validate.py` 与 `cmp` 检查。

---

## 2026-06-14 — 服务器适配 + 辅助脚本

### 背景 / 目标

在 `bio-workflow/` 下构建个人通用生物信息学分析工作流 skill。`skills.md` 是用户提供的初版草稿（12 阶段流程 + 半自动权限边界 + 默认输出格式）。本轮工作：(1) 轻量探测服务器、把通用流程参数化为本机可直接执行的版本；(2) 把高频、易错动作固化成 `scripts/` 工具脚本。

### 决策记录（已与用户确认）

- **skill 落地位置**：全局 `~/.claude/skills/bioinformatics-analysis-workflow/`（不是项目内）。`bio-workflow/skills.md` 保留为草稿/源。
- **新建环境工具**：用 `micromamba`（不是 mamba/conda——本机 solver 已坏）。复用现成 env 用 `conda activate`。
- **拆分策略**：本轮只拆 `scripts/`（收益最高、可执行）；`templates/`、`references/` 待内容稳定后再拆。

### 探测到的服务器关键事实（作为 skill 默认值）

- 登录节点 `hnode4`：32 核 / 251G；文件系统根 `/data9`。
- 调度器 SLURM（`/opt/gridview/slurm/bin`）。账户 `--account=qgzeng`，默认 `--qos=user_qgzeng`。
- 分区（全部 `TIMELIMIT=infinite`）：
  - `debug`（18 节点）/ `normal`*默认（16×32核×257G）/ `high`（同规格，优先级高）
  - `fat` / `fat2`：各 1 节点，**384 核 / ~6T**（大内存/单机高并行）
- **⚠️ QOS `user_qgzeng` 硬上限**：已提交(排队+运行) ≤ **200** | 运行中 ≤ **100** | 运行 CPU 总和 ≤ **600**。
  - 实测当下占用样例：已提交 77/200、运行 9/100、CPU 96/600（说明已有别的作业在跑，提交需留余量）。
- **包管理现状（已实测）**：
  - `mamba`（condabin）已损坏（`import mamba.mamba` 报错）；conda 自带 solver 在 bioconda 规格上会挂死 ~50min。
  - 可用：`/data9/home/qgzeng/tools/micromamba`（v2.8.0，不在 PATH）。建环必须 `conda-forge` 优先 + `--strict-channel-priority`。
  - 已有 ~70 个 conda env（busco/gatk/snp/EDTA/orthofinder/syri2/braker3/assembly/annotation/pan/pggb/haphic 等），**优先复用**。
  - 与 memory `conda-broken-use-micromamba` 一致，memory 准确无需改。
- module 系统（environment-modules）存在但**基本无 modulefile**，不依赖 `module load`。

### 相对初版草稿的关键优化（已写入 SKILL.md）

1. **新增第 0 节「服务器环境基线」**：把上述事实作为默认值，避免每次重新发现 / 防止卡顿。
2. **新增 QOS 配额纪律**（初版完全缺失，最易翻车）：array 必须 `%N` 限并发 + 分块提交。
3. **分区决策表 + 资源决策表**：大内存→fat/fat2。
4. **包管理纠正**：复用 env 用 `conda activate`；新建用 micromamba（脚本封装）。
5. **工具发现顺序适配**：现成 env 优先，module 降级。
6. **登录节点红线**：重活一律 sbatch/srun。
7. **可直接用的 SLURM 模板**：account/qos 默认值已填，⚠️ 标注待确认字段；含 nodes/ntasks/线程变量。

### 已完成产物

- `~/.claude/skills/bioinformatics-analysis-workflow/SKILL.md` — 服务器适配版（含第 0 节基线、辅助脚本表、SLURM 模板）。
- `~/.claude/skills/bioinformatics-analysis-workflow/scripts/`（均 `chmod +x`，`bash -n` 通过，`-h` 与实跑测试通过）：

| 脚本 | 用途 | 关联阶段 | 验证 |
|---|---|---|---|
| `check_inputs.sh` | 输入清单+完整性（存在/可读/非空/gz魔数/格式首字符/可选配对/可选 gzip -t） | 第 2 步 | 实跑通过 |
| `new_env.sh` | micromamba 建环封装（固定 conda-forge 优先；--dry-run/--force） | 第 3 步 | --dry-run 通过 |
| `check_quota.sh` | QOS 占用查询+预演（200/100/600；-n/-c/-j） | 第 8 步 | 实跑通过，超限正确返回 1 |
| `submit_chunked.sh` | 大规模 array 分块提交，守住排队 ≤ 上限（默认留余量 180） | 第 9 步 | 语法+help 通过（未实提交） |

设计要点：`check_quota`/`submit_chunked` 用 `squeue -r` 展开 array 元素以匹配 MaxSubmitJobs 计数；`check_inputs` 默认只读魔数+首字符、不解压全文件（登录节点安全），gzip -t 为 opt-in；`new_env` 固定 `MAMBA_ROOT_PREFIX=anaconda3`。

### 已知小瑕疵 / 边界

- `check_inputs.sh` 把以 `#` 开头的文件（如 shell 脚本的 `#!`）判成 `vcf/hdr`——真实输入是 fastq/fasta/vcf，不影响。
- `submit_chunked.sh` 的分块提交逻辑尚未做真实大规模提交验证（仅语法/help）。首次真跑建议小 `-N` + 大 `-m` 余量观察。
- `--paired` 配对识别假设文件名用分隔符（`samp_R1.fastq.gz`），无分隔符命名不归组。

### 待办 / 下一步建议

1. **首次真实使用 `submit_chunked.sh`** 时小规模验证轮询/补提行为。
2. **待内容稳定后拆 `templates/`**（放 SLURM array 模板文件，供 submit_chunked `-s` 直接引用）与 `references/`（env→任务映射表、分区/QOS 速查、常见报错排查）。
3. 可加 `scripts/collect_run_log.sh`：自动汇总 Job ID/版本/参数到第 12 步分析记录。
4. 决定 `bio-workflow/skills.md`（草稿）与全局 SKILL.md 的同步方式（手动 / 软链 / 安装脚本，参考 paperplot-skills 的做法）。

### 复现入口

```bash
# 查看 skill
cat ~/.claude/skills/bioinformatics-analysis-workflow/SKILL.md
ls  ~/.claude/skills/bioinformatics-analysis-workflow/scripts/

# 脚本自检
for s in ~/.claude/skills/bioinformatics-analysis-workflow/scripts/*.sh; do bash -n "$s"; "$s" -h >/dev/null && echo "ok: $(basename $s)"; done
```
