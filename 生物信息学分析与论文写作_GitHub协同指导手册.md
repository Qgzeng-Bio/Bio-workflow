# 生物信息学分析与论文写作：GitHub 协同与版本管理指导手册

> **适用对象**：第一次把生物信息学分析、结果解释和论文写作纳入 Git/GitHub 管理的研究者
> **核心目标**：让每个结果、每次修改和每项写作决定都能回答三个问题——**改了什么、为什么改、证据在哪里**。
> **建议用法**：将本文件复制到项目根目录，命名为 `PROJECT_GUIDE.md`；再按照本文模板建立 `README.md`、`PROJECT_STATUS.md` 和研究日志。

---

## 1. 先理解：GitHub 不只是放代码

Git 适合管理任何**可比较的文本文件**，包括：

- Python、R、Shell、Snakemake、Nextflow 等分析代码；
- Markdown（`.md`）论文草稿和研究日志；
- LaTeX（`.tex`）稿件；
- BibTeX（`.bib`）参考文献；
- YAML、JSON、TSV、CSV 等参数和小型结果表；
- 软件环境、工作流配置与数据清单；
- 项目说明、分析计划、决策记录和修改说明。

GitHub 的基本协作对象包括 repository、branch、commit 和 pull request。Pull request 能显示两个版本之间的 diff，并允许团队逐行评论和审阅。[1]

### 1.1 最重要的认识

GitHub 的价值不是“把所有科研文件上传到网上”，而是把**适合版本控制的项目骨架**保存下来：

```text
分析问题
→ 数据来源与版本
→ 分析脚本与参数
→ 结果表和图
→ 结果解释
→ 论文中的主张
→ 修改与审查记录
```

理想状态下，论文中的每个关键结论都能沿着这条链回到分析依据。

### 1.2 Git、GitHub 和备份不是同一件事

- **Git**：记录文件版本及修改历史；
- **GitHub**：托管 Git 仓库并提供协作、diff、Issue 和 Pull Request；
- **备份系统**：防止硬盘损坏、误删和灾难性丢失。

GitHub 官方明确指出 Git 不是为备份而设计的。[3] 因此，原始数据仍应保存在实验室服务器、HPC、机构存储或合规的数据仓库中，并建立独立备份。

---

## 2. 哪些内容放 GitHub，哪些不要放

### 2.1 建议纳入 Git 的内容

| 内容 | 建议 | 原因 |
|---|---:|---|
| 分析脚本和工作流 | 必须 | 最容易复现和审查 |
| 参数与配置文件 | 必须 | 防止“代码相同但参数不同” |
| 环境文件 | 必须 | 记录软件与依赖版本 |
| `README.md` | 必须 | 说明项目目标、入口和复现方法 |
| `PROJECT_STATUS.md` | 必须 | 记录当前进度、阻塞项和下一步 |
| 分析日志 `.md` | 强烈建议 | 保存每次分析的目标、输入、输出和结论 |
| 论文草稿 `.md` / `.tex` | 强烈建议 | GitHub 可清晰显示文字 diff |
| `.bib` 参考文献库 | 强烈建议 | 便于追踪新增、删除和修正的条目 |
| 小型 CSV/TSV 结果表 | 建议 | 便于 diff 与自动检查 |
| 绘图代码 | 必须 | 图形应尽量可重新生成 |
| 最终 SVG/PDF/PNG 图 | 选择性纳入 | 方便查看，但二进制 diff 能力有限 |
| 数据清单及 SHA-256 | 强烈建议 | 记录数据身份，而不是上传数据本体 |

### 2.2 通常不要直接纳入普通 Git 仓库的内容

- FASTQ、BAM、CRAM、VCF 大文件；
- 大型 genome assembly、index、数据库缓存；
- Conda 环境目录本身；
- 中间结果、临时文件、日志洪流；
- 可由脚本重新生成的大量文件；
- API keys、密码、token、SSH 私钥；
- 受控访问、人类遗传、隐私或伦理限制数据；
- 未确认授权的合作方数据；
- 仅作为本地路径使用的凭据和配置。

GitHub 对普通 Git 仓库中的文件大小有限制：超过 50 MiB 会警告，超过 100 MiB 会阻止；更大的文件需要 Git LFS 或外部存储。[3] 对生信项目而言，更稳妥的原则通常是：**Git 管代码、配置、元数据和小型结果；数据本体放专业存储。**

> **安全提醒**：私人仓库不等于伦理或数据合规已经满足。是否允许上传，应服从知情同意、数据使用协议、合作协议和所在机构规定。

---

## 3. 推荐的生信项目目录

下面的结构兼顾分析复现、论文写作和 GitHub diff：

```text
oil-palm-genome-project/
├── README.md
├── PROJECT_STATUS.md
├── CHANGELOG.md
├── .gitignore
│
├── docs/
│   ├── analysis-plan.md
│   ├── claim-evidence-map.md
│   ├── decisions.md
│   └── research-log/
│       ├── 2026-09-03_genome-qc.md
│       └── 2026-09-05_gene-family-analysis.md
│
├── metadata/
│   ├── samples.tsv
│   ├── data_manifest.tsv
│   └── checksums.sha256
│
├── workflows/
│   ├── Snakefile
│   └── rules/
│
├── scripts/
│   ├── assembly/
│   ├── annotation/
│   ├── comparative_genomics/
│   └── plotting/
│
├── config/
│   ├── config.yaml
│   └── parameters.yaml
│
├── envs/
│   ├── environment.yml
│   └── tool_versions.tsv
│
├── results/
│   ├── README.md
│   ├── tables/
│   └── figures/
│
├── manuscript/
│   ├── outline.md
│   ├── title_abstract.md
│   ├── introduction.md
│   ├── results.md
│   ├── discussion.md
│   ├── methods.md
│   ├── references.bib
│   └── figures/
│
└── supplement/
    ├── supplementary_methods.md
    ├── supplementary_tables/
    └── supplementary_figures/
```

### 3.1 不必一次建完

初始阶段只建最小骨架即可：

```text
README.md
PROJECT_STATUS.md
.gitignore
docs/research-log/
scripts/
config/
results/
manuscript/
```

项目发展后再增加其他目录。目录不是越多越专业；真正重要的是团队知道每一类文件的唯一存放位置。

---

## 4. 为什么建议用 Markdown 写论文过程

Markdown 是纯文本，容易读写，也容易被 Git 比较。GitHub 的 README 通常使用 Markdown。[1]

### 4.1 推荐的写法：“一行一句”

```markdown
## Genome assembly and annotation

We generated a chromosome-scale assembly of *Elaeis guineensis*.
The final assembly contained [AUTHOR: insert verified value] chromosomes.
Assembly continuity was evaluated using [METHOD/REFERENCE REQUIRED].
```

在 Markdown 中，同一段内换行通常不会破坏最终显示；但 Git diff 会更精确地显示哪一句发生变化。段落之间保留一个空行。

### 4.2 不要直接写无法追溯的数字

不推荐：

```markdown
The genome contained 35,214 genes and showed superior completeness.
```

推荐：

```markdown
The annotation contained 35,214 protein-coding genes
[SOURCE: results/tables/annotation_summary.tsv; script: scripts/annotation/summarize.py; commit: pending verification].
```

定稿时可删除内部标记，但在结果尚未冻结前，应保留证据入口。

### 4.3 Word、Excel 和 PDF 怎么办

`.docx`、`.xlsx` 和多数 `.pdf` 是二进制或压缩容器。Git 可以保存它们的版本，却通常不能像 Markdown 那样给出有意义的逐句 diff。

建议采用“双轨制”：

- **可编辑源文件**：Markdown、LaTeX、BibTeX、CSV/TSV、绘图脚本；
- **交付文件**：Word、Excel、PDF；
- Word/Excel 每次导出时，同时更新对应的 Markdown/CSV/TSV 来源；
- 稿件尽量保持稳定文件名，不使用大量 `final_v2_really_final.docx`；
- 投稿冻结版可放在 `releases/` 或创建 Git tag，而不是覆盖历史。

---

## 5. 第一次建立 GitHub 项目

### 5.1 先做安全检查

在上传任何内容前，确认：

- 仓库应设为 **Private**，除非团队明确决定公开；
- 没有密码、token、账号、私钥；
- 没有受伦理、隐私、专利或合作协议限制的数据；
- 已先创建 `.gitignore`；
- 没有误加入原始大数据和整个软件环境目录；
- 合作者的 GitHub 访问权限遵循最小必要原则。

### 5.2 推荐方式 A：使用 GitHub Desktop

适合初学者：

1. 在 GitHub 创建一个 private repository；
2. 使用 GitHub Desktop 将其 clone 到本地；
3. 把项目骨架文件放入本地仓库；
4. 在 Changes 页面逐个查看修改；
5. 填写清楚的 commit message；
6. 点击 Commit，再 Push；
7. 较大的修改使用 branch 和 pull request；
8. 在 pull request 的 Files changed 页面逐行检查 diff。

GitHub 官方的 Hello World 教程也是按照 repository → branch → commit → pull request → merge 的路径介绍工作流。[1]

### 5.3 推荐方式 B：使用命令行

以下命令中的路径和仓库 URL 必须替换成你自己的内容：

```bash
cd /path/to/oil-palm-genome-project

git init
git branch -M main

# 必须先创建并检查 .gitignore，再添加文件
git status
git add .gitignore README.md PROJECT_STATUS.md docs scripts config envs manuscript
git status

git commit -m "chore: initialize project structure and documentation"
git remote add origin git@github.com:YOUR_ACCOUNT/YOUR_PRIVATE_REPO.git
git push -u origin main
```

不要在没有检查 `git status` 的情况下习惯性运行 `git add .`。对于生信目录，一次误加可能把大型数据、凭据或临时结果纳入历史。

---

## 6. 生信项目 `.gitignore` 模板

GitHub 建议在仓库根目录创建 `.gitignore`，并将其提交，使协作者共享同一套忽略规则。[2]

下面是一个起点，必须根据项目实际情况调整：

```gitignore
# macOS / editors
.DS_Store
*.swp
*.swo
*~
.vscode/
.idea/

# Secrets and local configuration
.env
.env.*
*.pem
*.key
secrets/
credentials/

# Python / R caches
__pycache__/
*.py[cod]
.Rhistory
.RData
.Rproj.user/

# Virtual environments
.venv/
venv/
env/
.conda/

# Workflow temporary files
.snakemake/
.nextflow/
work/
tmp/
temp/
logs/

# Raw sequencing and large alignment files
raw_data/
*.fastq
*.fastq.gz
*.fq
*.fq.gz
*.bam
*.bai
*.cram
*.crai

# Large genome/index files: adjust if small reference files must be tracked
*.mmi
*.bt2
*.bt2l
*.amb
*.ann
*.bwt
*.pac
*.sa

# Generated intermediate results
results/intermediate/
results/cache/

# Office lock files
~$*.docx
~$*.xlsx

# LaTeX generated files
*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.synctex.gz
```

### 6.1 `.gitignore` 不是保险箱

如果敏感文件已经提交，再写入 `.gitignore` 并不会自动从 Git 历史中删除。GitHub 官方文档也指出，已被跟踪的文件需要先解除跟踪。[2] 如果误提交了凭据，应立即轮换凭据，并按照 GitHub 的敏感数据清理流程处理，不能只删除当前文件。

---

## 7. 每天实际怎么工作

以下流程适合独立研究者，也适合团队合作。

### 7.1 开始工作前

```bash
git switch main
git pull --ff-only
git status
```

确认工作区干净，再创建任务分支：

```bash
git switch -c analysis/gene-family-expansion
```

推荐分支命名：

```text
analysis/genome-qc
analysis/synteny
analysis/gene-family-expansion
writing/results-assembly
writing/discussion-domestication
figure/fig3-synteny
fix/sample-metadata
review/nature-precheck
```

### 7.2 工作过程中

1. 修改分析脚本或参数；
2. 运行分析并保存日志；
3. 检查结果，不要只相信脚本退出码；
4. 更新当天的 `research-log`；
5. 如果结果进入论文，更新 `claim-evidence-map.md`；
6. 更新对应的 Results 草稿；
7. 查看 diff；
8. 提交一个目的明确的 commit。

```bash
git status
git diff
git diff --word-diff manuscript/results.md

git add scripts/comparative_genomics/gene_family.R
git add config/parameters.yaml
git add docs/research-log/2026-09-05_gene-family-analysis.md
git add manuscript/results.md

git diff --cached
git commit -m "analysis: revise gene-family expansion thresholds"
git push -u origin analysis/gene-family-expansion
```

### 7.3 完成一个任务后

创建 Pull Request，并回答：

- 本次科学问题是什么？
- 改了哪些文件？
- 输入数据和版本是什么？
- 修改了哪些参数？为什么？
- 生成了哪些结果？
- 哪些论文句子或图表受影响？
- 是否存在未解决风险？
- 是否需要合作者复核？

Pull request 显示分支间的增删和 diff，适合在合并到 `main` 前审查。[1]

---

## 8. Commit 应该怎么写

### 8.1 原则：一个 commit 对应一个科学或写作意图

推荐：

```text
analysis: add BUSCO summary for assembly v3
analysis: correct orthogroup filtering threshold
results: link gene-family claim to source table
figure: regenerate Fig. 3 after sample exclusion
methods: document repeat-annotation software versions
references: correct DOI for oil-palm domestication study
fix: align sample IDs across metadata and expression matrix
```

不推荐：

```text
update
修改
final
final2
latest changes
```

Commit message 要说明**为什么发生这次变化**。GitHub 官方说明每个 commit 都带有描述性消息，用来保存修改历史并让协作者理解做了什么和为什么做。[1]

### 8.2 推荐前缀

| 前缀 | 用途 |
|---|---|
| `analysis:` | 分析方法、脚本或参数变化 |
| `data:` | 元数据、数据清单或 accession 变化 |
| `results:` | 结果解释或结果表更新 |
| `figure:` | 图形代码、图注或图件更新 |
| `writing:` | 普通论文文字修改 |
| `methods:` | 方法和复现信息修改 |
| `references:` | 引文或书目信息修改 |
| `fix:` | 修正错误或不一致 |
| `docs:` | README、日志和说明文件 |
| `chore:` | 不改变科学内容的维护工作 |

---

## 9. 如何用 diff 看论文到底改了什么

### 9.1 查看尚未提交的修改

```bash
git diff
```

### 9.2 按词查看 Markdown 变化

```bash
git diff --word-diff manuscript/results.md
```

### 9.3 查看已暂存、准备提交的修改

```bash
git diff --cached
```

### 9.4 查看某一次提交

```bash
git show COMMIT_SHA
```

### 9.5 比较两个版本

```bash
git diff OLD_TAG..NEW_TAG -- manuscript/
```

GitHub 的 Compare 页面也可以比较 branch、tag 或两个 commit。[4]

### 9.6 查看历史

```bash
git log --oneline --graph --decorate --all
git log -- manuscript/results.md
git log -p -2 -- manuscript/results.md
git log --stat
```

`git log` 用于查看提交历史；`-p` 可以显示每次 commit 引入的 diff，`--stat` 可以汇总修改文件和增删行数。[5]

---

## 10. 用版本号和标签管理论文阶段

不要把“文件名中的 v37”当成唯一版本系统。Git 已经保存每次 commit；在关键里程碑处再创建 tag。

推荐标签：

```text
v0.1-analysis-plan
v0.2-data-qc-freeze
v0.3-main-results-freeze
v0.4-first-full-draft
v0.5-coauthor-review
v0.6-pre-submission-audit
v1.0-submitted
v1.1-revision-1
```

创建和推送标签：

```bash
git tag -a v0.4-first-full-draft -m "First complete manuscript draft"
git push origin v0.4-first-full-draft
```

比较两个阶段：

```bash
git diff v0.4-first-full-draft..v0.6-pre-submission-audit -- manuscript/
```

每个投稿版本都应能关联到：

- Git tag；
- commit SHA；
- 稿件 PDF/Word；
- figures 与 supplement；
- 数据和代码状态；
- 提交日期及期刊。

---

## 11. `PROJECT_STATUS.md` 模板：一页看清项目进度

将下面内容复制为项目根目录的 `PROJECT_STATUS.md`：

```markdown
# Project Status

## 1. 当前目标

- 目标期刊：Nature / [具体子刊待确认]
- 文章类型：[Article / Analysis / Resource / 其他]
- 当前阶段：[分析 / 结果冻结 / 写作 / 合作者审阅 / 投稿前审查]
- 当前基线版本：[commit SHA 或 tag]

## 2. 本周优先事项

- [ ] 完成组装质量指标复核
- [ ] 核对 Table 1 与 Supplementary Tables
- [ ] 更新 Fig. 3 图注中的 n 和统计方法
- [ ] 核验核心引文是否支持对应主张

## 3. 分析模块进度

| 模块 | 输入版本 | 脚本/工作流 | 结果位置 | 状态 | 负责人 | 最后核验 |
|---|---|---|---|---|---|---|
| Genome assembly QC | assembly_v3 | workflows/qc | results/tables/assembly_qc.tsv | 已完成/待复核 | 姓名 | YYYY-MM-DD |
| Annotation | annotation_v2 | scripts/annotation | results/tables/annotation_summary.tsv | 进行中 | 姓名 | YYYY-MM-DD |
| Gene families | orthofinder_v1 | scripts/comparative_genomics | results/gene_family | 阻塞 | 姓名 | YYYY-MM-DD |

## 4. 论文进度

| 部分 | 状态 | 证据是否闭环 | 负责人 | 主要问题 |
|---|---|---:|---|---|
| Title/Abstract | 草稿 | 否 | 姓名 | 核心数字待冻结 |
| Introduction | 合作者审阅 | 部分 | 姓名 | novelty 引文待核验 |
| Results | 修订中 | 部分 | 姓名 | Fig. 3 与补充表待对齐 |
| Discussion | 草稿 | 否 | 姓名 | 替代解释和局限性不足 |
| Methods | 修订中 | 部分 | 姓名 | 软件版本与参数待补充 |

## 5. 阻塞项

| 编号 | 阻塞问题 | 影响 | 需要谁处理 | 截止时间 | 状态 |
|---|---|---|---|---|---|
| B-001 | 缺少某批样本的原始 QC 记录 | Fig. 2 暂不能冻结 | 姓名 | YYYY-MM-DD | Open |

## 6. 关键决策

| 日期 | 决策 | 依据 | 影响文件 | 决策人 |
|---|---|---|---|---|
| YYYY-MM-DD | 使用 assembly_v3 作为论文基线 | BUSCO/QV/Hi-C 综合结果 | Methods, Table 1, Fig. 1 | 姓名 |

## 7. 下一里程碑

- 里程碑：主结果冻结
- 目标日期：YYYY-MM-DD
- 验收条件：
  - [ ] 所有主图可由脚本重新生成
  - [ ] 主文数字与 source tables 一致
  - [ ] 核心主张均有图表或文献证据
  - [ ] 软件、数据库和参数版本完整
  - [ ] 合作者完成一次独立复核
```

原则：`PROJECT_STATUS.md` 只写“当前状态”，历史变化由 Git commits 和 `CHANGELOG.md` 保存。

---

## 12. 研究日志模板：每次分析都留下证据

每次重要分析建立一个文件，例如：

```text
docs/research-log/2026-09-05_gene-family-analysis.md
```

模板：

```markdown
# Analysis Log: Gene-family expansion

## 基本信息

- 日期：YYYY-MM-DD
- 操作者：姓名
- 分支：analysis/gene-family-expansion
- 起始 commit：COMMIT_SHA
- 关联 Issue：#编号

## 1. 科学问题

本次分析要回答的具体问题是什么？

## 2. 预先设定的判断标准

- 主要比较：
- 纳入/排除标准：
- 阈值及依据：
- 多重检验处理：
- 预期输出：

## 3. 输入

| 输入 | 路径/数据库 | 版本/accession | SHA-256 | 备注 |
|---|---|---|---|---|
| Genome annotation | 外部或内部路径 | v2 | HASH | 只记录，不上传大文件 |

## 4. 软件与参数

| 工具 | 版本 | 关键参数 | 环境 |
|---|---|---|---|
| OrthoFinder | x.y.z | `参数` | envs/orthofinder.yml |

## 5. 实际执行命令

```bash
# 粘贴真实执行命令；不得根据记忆补写
```

## 6. 输出

| 输出 | 路径 | 生成脚本 | 状态 |
|---|---|---|---|
| Summary table | results/tables/gene_family.tsv | scripts/... | 已检查 |

## 7. 质量控制

- [ ] 退出状态和日志已检查
- [ ] 输入样本数符合预期
- [ ] 缺失和异常值已检查
- [ ] 结果可在干净环境中重现
- [ ] 图形已经人工打开并查看

## 8. 结果与解释

### 已观察到的结果

只写数据直接显示的内容。

### 当前解释

区分直接结果、推断和假设。

### 替代解释与限制

记录不能由本分析排除的解释。

## 9. 对论文的影响

- 受影响主张：
- 受影响章节：
- 受影响图表：
- 是否需要更新 Methods：是/否
- 是否需要合作者确认：是/否

## 10. 结论状态

- [ ] Exploratory：探索性结果，不能写成确定结论
- [ ] Provisional：初步稳定，尚未独立复核
- [ ] Verified：脚本、输入、输出和解释均已复核
- [ ] Frozen：进入当前投稿基线
```

---

## 13. `claim-evidence-map.md`：把论文主张与结果绑定

这是整个系统最重要的文件之一。

```markdown
# Claim–Evidence Map

| Claim ID | 稿件中的主张 | 证据图表 | Source data | 分析脚本/工作流 | 关键假设 | 替代解释 | 状态 |
|---|---|---|---|---|---|---|---|
| C-001 | [准确填写] | Fig. 1; Table 1 | results/tables/... | scripts/... | [填写] | [填写] | Verified |
| C-002 | [准确填写] | Fig. 3 | results/tables/... | workflows/... | [填写] | [填写] | Provisional |
```

建议规则：

- Abstract 中的每个实质性结论都应有 Claim ID；
- 每张主图至少对应一个明确主张；
- “首次”“显著优于”“揭示机制”“导致”等强主张必须单独审查；
- 文献存在不等于文献支持该主张；
- 若没有直接证据，必须降调、补证据或明确写成假设。

---

## 14. Results 写作模板：从分析到论文，而不是从印象到论文

建议在 `manuscript/results.md` 中按以下结构写每个小节：

```markdown
## [结果小节标题：表达发现，不夸大解释]

<!-- CLAIM: C-00X -->
<!-- EVIDENCE: Fig. X; Supplementary Table X -->
<!-- SOURCE DATA: results/tables/xxx.tsv -->
<!-- ANALYSIS: scripts/xxx.py; config/xxx.yaml -->

### 1. 本段科学问题

[一句话说明本段要回答什么。]

### 2. 分析设计

[样本、比较、主要方法和预先定义的指标。]

### 3. 直接结果

[只描述图表和统计结果直接支持的内容。]

### 4. 有限解释

[给出与研究设计相称的解释，并保留不确定性。]

### 5. 与下一段的连接

[说明为什么下一个分析是必要的。]
```

最终投稿前可以删除 HTML 注释，但这些注释在写作和内审阶段非常有价值，而且不会出现在正常渲染的 Markdown 中。

---

## 15. 用 Issue 管任务，用 Pull Request 管证据完整的改动

### 15.1 一个 Issue 对应一个可验收任务

Issue 标题示例：

```text
[Analysis] Re-evaluate expanded gene families after filtering
[Figure] Align Fig. 3 labels with Supplementary Table 8
[Writing] Restrict causal language in the Discussion
[Reproducibility] Record database and software versions
[Citation] Verify references supporting domestication claims
```

Issue 内容应写：

- 背景；
- 要解决的问题；
- 输入；
- 验收条件；
- 负责人；
- 关联图、表和稿件章节；
- 是否阻断投稿。

### 15.2 Pull Request 模板

```markdown
## 目的

本次改动要解决什么科学或写作问题？

## 修改内容

- [ ] 分析代码
- [ ] 参数/配置
- [ ] 结果表
- [ ] 图件
- [ ] 稿件文字
- [ ] Methods
- [ ] Supplement

## 证据

- 输入版本：
- 脚本/工作流：
- 输出：
- 受影响 Claim ID：
- 受影响图表：

## 风险与限制

- 尚未解决的问题：
- 不能由本分析支持的结论：

## 合并前检查

- [ ] `git diff` 已逐项检查
- [ ] 没有加入敏感信息或大数据
- [ ] 图已实际打开并检查
- [ ] 主文数字与 source table 一致
- [ ] Methods 与实际执行流程一致
- [ ] 关键结论由合作者复核
```

即使只有一个人，也可以使用 Pull Request：它迫使你在合并前重新阅读自己的 diff，并形成阶段性记录。

---

## 16. 生信分析的可复现性最低要求

每个进入论文的关键分析至少记录：

1. 输入数据的名称、版本、accession、路径或不可变标识；
2. 输入文件的 checksum；
3. 软件、数据库及参考基因组版本；
4. 完整参数和配置；
5. 实际执行命令或工作流入口；
6. 软件环境或容器；
7. 随机种子（如适用）；
8. 样本纳入、排除和质量控制规则；
9. 输出文件及生成关系；
10. 结果被写入哪一段、哪一图、哪一表；
11. 谁在何时进行独立复核；
12. 当前结果状态：Exploratory / Provisional / Verified / Frozen。

### 16.1 建议采用“结果冻结”制度

一项结果只有满足以下条件后才可标记 `Frozen`：

- 输入和参数已确定；
- 脚本可重新运行；
- 核心输出已人工检查；
- 图和 source table 一致；
- Methods 与实际流程一致；
- 论文表述没有超过证据；
- 至少一名作者完成交叉核验；
- 已创建对应 Git commit 或 tag。

---

## 17. 大文件、Git LFS 与外部数据仓库

如果确实需要在 GitHub 管理较大的二进制文件，可以评估 Git LFS；但不要把它理解为无限数据存储。GitHub 官方对普通 Git 文件和仓库体积有明确限制，也建议大型数据库使用其他共享方式。[3]

适合 Git LFS 的例子：

- 少量高分辨率最终图；
- 需要与特定 manuscript commit 绑定的二进制交付件；
- 合作者必须共同管理、且符合许可与隐私要求的文件。

更适合外部存储的例子：

- FASTQ/BAM/CRAM；
- 大型基因组和索引；
- 数十 GB 的中间结果；
- 可由工作流重新生成的缓存；
- 受控访问数据。

无论文件在哪里，Git 仓库内应保存 `metadata/data_manifest.tsv`：

```tsv
file_id	logical_name	storage_location	version	sha256	access_policy	used_by
D001	Oil palm assembly	[internal path or accession]	v3	[hash]	controlled/public	Fig1;Table1
```

---

## 18. 常见错误及修正办法

### 错误 1：只上传最终 Word 和 PDF

**问题**：GitHub 无法提供清晰的逐句 diff，也无法连接分析与写作。
**修正**：保留 Markdown/LaTeX、BibTeX、CSV/TSV 和分析脚本作为 source of truth；Word/PDF 只作为导出件。

### 错误 2：把 GitHub 当网盘

**问题**：仓库膨胀、clone 缓慢、误传敏感数据。
**修正**：大数据放专业存储，Git 只记录 manifest、checksum、代码、配置和小型结果。

### 错误 3：所有修改都提交成一个 commit

**问题**：无法判断某个结果变化是代码、参数还是写作造成的。
**修正**：一个 commit 对应一个明确意图，提交前查看 `git diff --cached`。

### 错误 4：只记录“做了什么”，不记录“为什么”

**问题**：几个月后无法重建科学决策。
**修正**：在 commit、research log 和 decision log 中写依据与影响。

### 错误 5：手工修改最终表格和图片

**问题**：改动无法复现，正文数字容易与分析输出漂移。
**修正**：尽量由脚本生成表和图；必须手工处理时记录处理步骤、原始文件和操作者。

### 错误 6：同一个 Markdown 文件多人同时改同一段

**问题**：产生冲突且难以裁决。
**修正**：按章节分文件、按任务建 branch、通过 Pull Request 合并。

### 错误 7：误以为 private repository 可以上传一切

**问题**：private 只是访问控制，不自动满足伦理、合作、专利和数据使用协议。
**修正**：上传前做数据治理审查，只给必要成员访问权。

### 错误 8：没有在每次工作前同步

**问题**：在过期版本上修改，最终产生冲突。
**修正**：开始前 `git pull --ff-only`，再建任务分支。

---

## 19. 一个适合你的最小执行方案

如果不想一开始学太多，只做下面七件事：

1. 新建一个 **private GitHub repository**；
2. 创建 `README.md`、`PROJECT_STATUS.md` 和 `.gitignore`；
3. 将脚本、配置、环境、Markdown 稿件、BibTeX 和小型结果纳入 Git；
4. 不上传原始测序数据、敏感数据和大型中间文件；
5. 每完成一个分析，写一份 `docs/research-log/YYYY-MM-DD_topic.md`；
6. 每次提交前看 `git diff`，commit message 写清“为什么”；
7. 在数据冻结、完整初稿、合作者审阅和正式投稿时创建 tag。

你不需要一次掌握全部 Git 命令。先把下面的循环用熟：

```text
同步 main
→ 创建任务分支
→ 做一个明确任务
→ 写研究日志
→ 查看 diff
→ 提交 commit
→ push
→ Pull Request 审查
→ 合并 main
→ 更新 PROJECT_STATUS.md
```

---

## 20. 第一个月的逐步落地计划

### 第 1 周：只管理文档和脚本

- 建 private repository；
- 写 README；
- 建 `.gitignore`；
- 上传脚本、配置和环境文件；
- 用 `PROJECT_STATUS.md` 管当前进度。

### 第 2 周：加入研究日志

- 每个重要分析写一份日志；
- 记录真实命令、软件版本、输入和输出；
- 给所有进入论文的结果标记状态。

### 第 3 周：把论文拆成 Markdown

- 按 Title/Abstract、Introduction、Results、Discussion、Methods 分文件；
- 采用一行一句；
- 建立 `claim-evidence-map.md`；
- 每次写作修改都通过 diff 检查。

### 第 4 周：开始 branch 和 Pull Request

- 一个分析或一组相关写作修改使用一个 branch；
- 合并前填写 PR 模板；
- 创建第一个阶段性 tag；
- 用 `git diff TAG1..TAG2 -- manuscript/` 回顾论文变化。

---

## 21. 投稿前 GitHub 冻结检查表

### 数据与分析

- [ ] 所有主结果都能定位到输入、脚本、参数和输出；
- [ ] 原始数据未误传 GitHub；
- [ ] 数据清单和 checksum 完整；
- [ ] 软件、数据库和参考基因组版本完整；
- [ ] 样本纳入、排除和 QC 规则可复核；
- [ ] 主图可由保存的代码和配置重新生成；
- [ ] 所有手工处理均有日志。

### 论文

- [ ] Abstract 中所有主张均进入 claim–evidence map；
- [ ] 正文、主图、Extended Data、补充图表的数字一致；
- [ ] 图注中的 `n`、误差线、统计检验和重复类型完整；
- [ ] Methods 与真实执行流程一致；
- [ ] 引文存在且真正支持对应主张；
- [ ] Data/Code Availability 与实际访问方式一致；
- [ ] 没有未解决的 `[AUTHOR CHECK]`、`[SOURCE REQUIRED]` 或临时占位符。

### 版本

- [ ] 工作区干净：`git status` 无意外修改；
- [ ] 最终 diff 已人工审查；
- [ ] 创建投稿 tag；
- [ ] 记录最终 commit SHA；
- [ ] Word/PDF、图件和 supplement 与同一 commit 对应；
- [ ] GitHub 之外另有合规备份。

---

## 22. 你现在最应该做的第一步

不要立即把现有整个生信目录执行 `git add .`。

更安全的顺序是：

1. 先建立一个新的 private repository；
2. 先创建 `.gitignore`；
3. 只加入 README、项目状态、脚本、配置、环境和 Markdown 稿件；
4. 运行 `git status`，逐项确认待提交文件；
5. 完成第一次小型 commit；
6. 确认没有敏感信息和大文件后再 push；
7. 再逐步迁移结果表、绘图代码和论文记录。

这样既能获得 GitHub 的 diff 与版本管理优势，又不会因为第一次操作不熟练而把大数据、凭据或未授权内容写入仓库历史。

## Sources

[1] https://docs.github.com/en/get-started/using-github/hello-world — Hello World - GitHub Docs
[2] https://docs.github.com/en/get-started/git-basics/ignoring-files — Ignoring files - GitHub Docs
[3] https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github — About large files on GitHub - GitHub Docs
[4] https://docs.github.com/en/pull-requests/how-tos/commit-changes/comparing-commits — Comparing commits - GitHub Docs
[5] https://git-scm.com/book/en/v2/Git-Basics-Viewing-the-Commit-History — Viewing the Commit History - Pro Git
