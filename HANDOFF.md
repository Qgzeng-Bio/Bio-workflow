# Bio-Workflow Skill Handoff

Last updated: 2026-06-18 — L4 上线 + RagTag 归位 + 公开"已知设计弱点"清单

---

## 2026-06-18 — Self-assessment 与"已知设计弱点"清单

### 背景 / 目标

L1–L4 全部完成、RagTag 归到 scaffolding 后,做一次诚实的 self-assessment,
把还没做、但**确实是设计层(不是纯工程化)**的弱点显式记下来,避免下一次
session 误以为 skill 已经完工。

### Self-score(2026-06-18)

| 维度 | 分 | 说明 |
|---|---|---|
| 设计成熟度 | 8.5 | L1-L4 四层架构清晰;authority 二维 + 规则强度 4 档已对齐 GPT review |
| 实际可用性 | 8.0 | quinoa 项目从 survey 到 SV 全跑通,KMERIA 也跑通 |
| 安全防护 | 9.0 | preflight + triage + 闸门三件套 + claim gate |
| 领域知识真实性 | 8.5 | 11 playbook 全部锚到真项目数字,非脑补 |
| 可维护性 | 7.0 | 有 3 个 validator,但**没有自动化测试**;改规则只能手跑 fixture |
| 跨场景适应性 | 7.0 | scope 字段已就位,但实测只跑过 quinoa 一种异源四倍体 |
| 完整性 | 6.5 | Phase 3 collect_metrics.py / Phase 4 render_story_bundle.py 未做;14 条规则覆盖窄 |

**综合 8.0 / 10**。个人单项目用得很顺;离工业级跨项目 skill 还差一档。

### 已知设计弱点(按性价比从高到低)

下面 5 条**不是**纯工程化欠账(测试 / 多项目验证 / 采集器),而是
设计层面真实存在的提升点。补上其中 1–2 条会让用户感受到"质变",不补
则当前体系仍能工作但有具体盲区。

#### W1. 反馈环没闭环(最大问题)

skill 是单向流:agent 跑分析 → checker 拦下 BAD claim。但 skill 自己
**永远不知道自己有没有错过 BAD claim**(false negative),也不知道哪条
规则**误报最多**(false positive)。

具体缺:
- agent 实际下了什么 claim、跑了什么 sbatch,没有机器可读日志被回收
- 没有"过去 N 次 ASM_QV_002 触发了几次、几次被覆盖、几次事后证明是误报"
- HANDOFF.md 是人工 journal,不是 skill 能机读的

**修法**:让 `submit_and_log.sh` 已经在写的 `run_record.tsv` 多记一列
`checker_status`,每个有效 manifest 跑完追加到 `reports/claim_audit.tsv`。
3 个月后回看,这张 TSV 就是规则优化的金矿。

**价值**:skill 从"我守门"升级到"我能学守门"。

#### W2. 规则之间没拓扑

现在 14 条规则是扁平列表,每条独立跑。但规则之间有依赖:
- `ASM_BUSCO_001`(缺 provenance) 触发时,`ASM_BUSCO_002`(跨 lineage 比较)
  的 BLOCK 其实没必要再算
- `ASM_REPEAT_001`(BUSCO × LAI 正交) 依赖前两类规则都过
- `KMERIA_001`(pilot incomplete) 触发时 `KMERIA_002`(hit overlap) 的 claim
  根本不应该到达

后果:输出会同时报多条相关 issue,模型读起来嘈杂,容易抓不到根因。

**修法**:`interpretation-rules.tsv` 加一列 `requires`(rule_id 列表);
checker 按 DAG 拓扑序跑,前置 BLOCK 时下游 silently skip。

**价值**:输出从"全部 dump"变成"先告诉你最深的根因"。

#### W3. evidence grade 体系还分裂

现在:
- `program-cards/*.md` 用**线性** grade(`project_history > local_run >
  local_help > official_doc > github_readme > inferred`)
- `interpretation-rules.tsv` 用**二维**(`authority + scope + strength`)

当时为了避免 churn,我没 retrofit 5 张现有 card。诚实讲这是技术债,
不是设计选择。

后果:agent 读到 card 里的 `project_history` 和 rule 里的 `project_history`,
两者含义其实不同(card 里 = "项目历史观察";rule 里 = "这条规则的权威来源是
项目历史")。模型遇到双源冲突时分不清。

**修法**:program-card 加 `scope` 字段(目前隐含全是 `general_genomics`),
或把 card 的 grade 也改成二维。半天工作,但要改 5 张 card。

**价值**:skill 内部 evidence 词汇统一,不再有"两套真理"。

#### W4. AI 能利用 skill 的程度还很低(自动触发缺失)

现在 agent **每次开会话都重读** SKILL.md + 相关 playbook,但:
- 没有"这次会话里我已经知道哪些 anchor"的运行时记忆
- claim 闸门只在被显式调用时触发,模型不会主动想到"啊我刚说了 QV 比较,
  该跑 checker 了"
- `interpretation-rules.tsv` 是按需读的,但模型不知道按需的边界 — 经常
  在该读时没读

具体观察:你直接 `claude` 跑分析,默认不会主动调
`scripts/check_result_contract.py`,要我提示。这层"自动触发"目前靠
SKILL.md 的自然语言规则,不靠机器约束。

**修法**:
- 在 SKILL.md 加**触发短语库**("publication-grade claim"/"compare across"/
  "report Methods" → 必跑 checker)
- claim 闸门做成 hook,模型一旦输出某些模式就被拦截要求先 verify

**价值**:从"工具有但要记得用"变成"该用时自动到位"。

#### W5. 没有 "UNCERTAIN" 状态

checker 现在 4 种状态:`PASS / WARN / BLOCK / MISSING`,但缺一个:
`UNCERTAIN` — 规则没覆盖的领域。

例子:跑 annotation,manifest 里有 BRAKER 输出。checker 看不懂(没有
annotation 规则),返回 PASS 加几条 MISSING。模型读到 PASS 就敢下 claim,
但其实 skill **根本不该有意见**。

**修法**:`scope` 字段反向用 — manifest 声明 `analysis_type: annotation`,
checker 发现没有匹配的 rule,显式输出 `STATUS: UNCERTAIN`,该领域不在
合约层覆盖范围。

**价值**:skill 从"我永远有意见"变成"我知道自己不知道"。
等真扩到 annotation/RNA-seq 时再上,当前 quinoa 主线不需要。

### 工程化欠账(不计入设计弱点,但顺手记下来)

不修也行,修了能更省事:

- **没有自动化测试**:改规则只能手跑 4 个 fixture。该有
  `tests/test_check_result_contract.py` + pre-commit hook,~2 小时。
- **第二个真实项目验证缺失**:所有 anchor 都来自 quinoa。下次跑别的物种
  会暴露隐含的"quinoa 假设"。**这是真要等到再开新项目时才能补**,
  靠想象补不出来。
- **Phase 3 `collect_metrics.py` 未做**:result_manifest.yaml 现在要手编。
  从真实 BUSCO/Merqury/LAI/QUAST 输出自动产 manifest,~4-6 小时。Phase 2.1
  schema 里已经预留字段。
- **Phase 4 `render_story_bundle.py` 未做**:论文 Methods/Table1/Limitations
  自动产数据。等真要发表时再做。

### 优先级建议(下一个 session 启动时参考)

按"修了之后这个 skill 真变了一档"排:

1. **W1 反馈环** — 一行 TSV 字段 + 一段 audit 写入,~2 小时,价值最大
2. **W4 自动触发** — SKILL.md 加触发短语库,~30 分钟,直接见效
3. **W2 规则拓扑** — 等规则数到 25+ 再做,现在 14 条还看得清
4. **W3 evidence grade 统一** — 等下一次大改 program-card 时顺手
5. **W5 UNCERTAIN** — 等真扩 annotation 时再上

不要把 5 条都堆到一次会话做 — 会过度工程化,且会破坏现在已经稳的部分。

### 当前结论

8 分的 skill 不是"做完了",而是"够用了 + 知道下一步在哪"。
这条 entry 就是那个"知道下一步在哪"。

---

## 2026-06-18 — RagTag 从 finishing 移到 scaffolding

### 背景 / 目标

把"基于参考的 scaffolding"(RagTag)放在 finishing playbook 里是按
"工作流哪一步用"分类的妥协,不是按"它做什么"分类。RagTag 实际就是
scaffolding,只是 reference-based 不是 3C-based。

### 已完成变更

- `playbook-chromosome-scaffolding-cphasing.md` 现在是 scaffolding 伞,
  包含两条路:
  - **Route A** C-Phasing(3C data,de novo) — 原内容
  - **Route B** RagTag(reference-based,无 3C) — 从 finishing 搬来
  - 各自带独立的 `### Evaluation contract`(Route A vs Route B)
  - Route B 合约明确:RagTag 继承参考结构,因此**新颖 SV 的 claim 不能
    在这里下**,必须等 SV-calling 阶段
- `playbook-genome-finishing.md` 缩成只覆盖 F2 gap-filling + F3 polishing
  - 删除 `## Stage F1 — Reference-based scaffolding (RagTag)` 整段
  - 删除 QC table 里两行 F1 RagTag
  - 删除 RagTag 专属 Pitfall(已搬到 scaffolding 的 Gotchas)
  - 删除 RagTag + LAI 的 Sources(已搬到 scaffolding 的 Sources)
  - 顺便清理一处重复的 TGS-GapCloser source 条目
- `SKILL.md`
  - 第 3 阶段 routing:明说 Route A vs Route B,以及"Route A 产出参考个体,
    Route B 是 pangenome accessions 走的路"
  - 第 4 阶段 routing:明说 "reference-individual only",accessions 的
    scaffolding 在第 3 阶段

### 验证

- `validate_program_cards.py --check-drafts` → PASS (5 active, 0 drafts)
- `quick_validate.py .` → Skill is valid!
- `### Evaluation contract` 数量:scaffolding=2(Route A + Route B),
  finishing=1(F2+F3)
- 工作树外其他 RagTag 引用都正常(只是 upstream/input 提示,不需要改)

### Caveats

- HANDOFF.md 早期 entry 里仍提到 "F1 RagTag" — 那是 journal 历史记录,
  反映当时状态,不动是对的

### 提交

commit `b1949c8`,已推 GitHub `main`。

---

## 2026-06-18 — L4 Evidence-to-Claim Control Plane: Phase 1 + Phase 2

### 背景 / 目标

L1–L3(接入控制 / 执行安全 / 领域大脑)已成型。下一步问题是:跑出来一堆数字
之后,模型怎么知道"这个 claim 能下、那个不能"。和 GPT Pro 沟通后达成共识:
**不要做生信百科**——通用解读、综合推理、写作交给模型;skill 负责本地事实、
证据口径、无效比较拦截、silent traps、claim gates。把这一层命名为
**Evidence-to-Claim Control Plane(L4)**,而不是 Interpretation layer。

本轮落地 Phase 1(合约层)+ Phase 2(claim 闸门脚本)。Phase 3 采集器 /
Phase 4 故事 bundle 等合约稳定后再上。

### 已完成变更

**Phase 1 — 合约层**

- 新增 `references/interpretation-rules.tsv`:14 条机器可读规则,9 列
  (`rule_id metric condition severity claim_constraint action authority
  scope source`)。覆盖 BUSCO 三条 + Merqury QV 三条 + LAI 两条 + BUSCO×LAI
  正交一条 + N50 两条 + KMERIA 两条 + SV 一条。`severity` 取
  `BLOCK / WARN / SUGGEST / NOTE` 四档。`authority` 不做线性排序,改用
  authority+scope 二维。
- 新增 `references/project-anchors.yaml`:quinoa V2 reference frame
  (Cqu_final / hap1 / hap2 真实数字,带 `scope: quinoa_project`)。
  qv_protocol 字段明确记录 read_db_type=hifi、k=21、independence=false
  ——这正是 evaluation 阶段 Merqury(`/data9/.../7-Genome-evalution/1-QV/qv.sh`
  实测确认)和 finishing 阶段 NextPolish2 用 Illumina truth set 的差异点,
  防止后续把两组 QV 数字混用。
- 新增 5 个 playbook 的 `### Evaluation contract` 小节,固定 5 行 schema
  (Required report fields / Comparator / Invalid comparisons /
  Silent traps / Claim allowed only if):
  - `playbook-genome-quality-evaluation.md`(主战场)
  - `playbook-genome-assembly.md`
  - `playbook-genome-survey.md`
  - `playbook-chromosome-scaffolding-cphasing.md`
  - `playbook-genome-finishing.md`
- `SKILL.md` 新增 `## Result claims: source-of-truth policy` 小节
  (位于 Task routing 之后、Workflow 之前):
  - 权威顺序:本地 manifest > 项目 anchor(scope 内)> 方法论文/官方文档 > 模型常识
  - 规则强度 BLOCK / WARN / SUGGEST / NOTE 的行为定义
  - routing 指向 `scripts/check_result_contract.py`(按需运行,不每次进 context)

**Phase 2 — claim 闸门**

- 新增 `references/result-manifest-schema.md`:`result_manifest.yaml`
  字段契约,字段据真实 quinoa 输出(BUSCO `short_summary.specific.*`、
  Merqury `result_*.qv` 5 列 TSV、LAI `*.fa.out.LAI` 7 列 TSV、QUAST
  `report.tsv`)设计而非凭空。
- 新增 `scripts/check_result_contract.py`(388 行):
  - 输入 `result_manifest.yaml` + `interpretation-rules.tsv` + `project-anchors.yaml`
  - 14 个 rule 各对应一个 Python check 函数(不做通用 DSL,可读可改)
  - 输出 `Field<TAB>Value` 短报告,分块 `BLOCKED / WARNINGS / NOTES / MISSING`
  - exit code 0=PASS / 1=WARN / 2=BLOCK
  - NOTE 不闸门(只是 provenance reminder),WARN/MISSING 才升级 status

### 验证 / 命令

四个真实 quinoa 数字编出来的 fixture(全部端到端通过):

| Fixture | 触发 | STATUS | exit |
|---|---|---|---|
| A_pass | 单 assembly 全 provenance 齐全 | PASS | 0 |
| B_warn | BUSCO C 99.7% + LAI 8.4(`ASM_REPEAT_001` WARN)、HiFi independence=false(`ASM_QV_003` WARN) | WARN | 1 |
| C_block | 不同 lineage(`ASM_BUSCO_002` BLOCK)+ 不同 read_db_type(`ASM_QV_002` BLOCK) | BLOCK | 2 |
| D_missing | 故意删 lineage/mode/db_version/k/read_db_type/total_LTR_RT_pct/intact_LTR_RT_pct | WARN | 1 |

回归命令:

```bash
python3 scripts/validate_program_cards.py                    # PASS (5 active)
python3 scripts/validate_program_cards.py --check-drafts     # PASS (5 active, 0 drafts)
/data9/home/qgzeng/anaconda3/bin/python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .   # Skill is valid!
PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/check_result_contract.py scripts/validate_program_cards.py scripts/program_card_lookup.py scripts/program_onboard.py scripts/menu.py
```

工具引用真实路径:`/data9/home/qgzeng/projects/2-C_quinoa/7-Genome-evalution/{0-QUAST,1-QV,2-BUSCO,3-LAI}` 实地勘探确认了输出文件名与列结构(bounded ls/read,未做广扫)。`1-QV/qv.sh` 第 13 行确认 evaluation 用 HiFi reads 建 read.meryl,与 finishing 阶段的 short-read truth 不可比 —— 这条事实进了 anchors `qv_protocol.independence: false` 与 `interpretation-rules.tsv ASM_QV_003`。

### 当前结论

- L4 已经从"概念"做成"可执行 claim 闸门":跑完 evaluation 之后,
  `python3 scripts/check_result_contract.py --manifest …` 给一段短报告,
  下游 LLM 不用再凭记忆决定哪些 claim 能下。
- skill 不替模型说生物学结论;skill 只挡"会让 claim 静默错"的 4 类问题:
  缺 provenance、跨口径比较、silent trap、anchor 越界。
- 现有 5 张 program card 的 evidence grade 不动,继续管"本地事实"轴;
  新的 interpretation-rules.tsv 用 authority+scope+strength 二维独立体系。

### Caveats / 风险

- 14 条规则只是首批;遇到下一类生物学场景(annotation 完整性、SNP-GWAS
  cross-check 等)再扩。规则增加时 `check_result_contract.py` 必须同步加
  对应函数(`CHECKS` 字典),validator 会在缺函数时打 WARN 不沉默。
- `result_manifest.yaml` 当前是手工或上游产生;Phase 3 `collect_metrics.py`
  做完后才能从原始输出自动产 manifest。
- KMERIA / SV 三条规则依赖 manifest 里的 `kmeria` / `sv` 顶层块 —— manifest
  schema 在那两块尚未真实跑过(留到 Phase 3 接入时补)。
- ASM_LAI_002 是 NOTE 级,只要有 LAI 块就触发,不闸门 —— 是有意为之
  (永远提醒不要跨物种用 LAI 等级),不算"误报"。

### 交付物

新增:
- `references/interpretation-rules.tsv`(15 行,14 规则)
- `references/project-anchors.yaml`(quinoa V2 reference frame)
- `references/result-manifest-schema.md`
- `scripts/check_result_contract.py`(executable)

改动:
- `SKILL.md`(+ `## Result claims: source-of-truth policy`,~22 行)
- 5 个 playbook 各 `+### Evaluation contract`(每个 7 行)
- `HANDOFF.md`(本条目)

不改 conda env、不联网、不广扫数据目录、不提交 SLURM job。

---

## 2026-06-17 — skill 优化: program onboarding 交互与口径收敛


### 背景 / 目标

用户暂停 KMERIA 实测,优先优化 bio-workflow skill。核心问题是:未知软件接入时不能把 `probe`
误说成"测试";需要把"安装位置 / 来源 / pilot 输入"做成可复用的交互式选择,并把当前进度分层报告清楚。

### 已完成变更

- `scripts/program_onboard.py`:
  - 新增通用子命令 `choose <program>`。
  - 记录三组选项:install location, source type, minimal pilot input。
  - 真实终端优先 curses 上下键/Enter;非 TTY 或 `--plain` 时使用编号输入。
  - 支持 `Type something` 自定义输入,`--print-options`,`--defaults`,`--default-source github`。
  - 默认输出 `config/program-onboarding/<program_key>_choice.json`;项目外输出默认阻断,仅
    `--allow-external-output` 供 smoke test。
  - 修复 `install` 成功后打印 `capture` 下一步时引用未定义变量的问题。
- `SKILL.md`:
  - program-level route 增加 `python3 scripts/program_onboard.py choose <program_name>`。
  - 明确当前聊天 UI 不能假设有原生弹窗;需要本地终端选择器或 `--plain` 兜底。
  - 增加进度层级口径:
    `L0 choice/intake`, `L1 probe`, `L2 install proposal`, `L3 installed+captured`,
    `L4 pilot script/preflight`, `L5 pilot/run validated`, `L6 active card`。
  - 明确不能把 `probe` 或 `plan-install` 描述为程序已可运行测试。
- `references/program-cards/program-onboarding.md` / `README.md`:
  - 同步 `choose` 命令和输出位置。
  - 补 L0-L6 分层说明和 `--default-source github` 使用场景。

### 验证 / 命令

- `PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/program_onboard.py scripts/program_card_lookup.py scripts/validate_program_cards.py scripts/kmeria_onboarding_wizard.py`
- `python3 scripts/program_onboard.py choose KMERIA --print-options --default-source github`
- `python3 scripts/program_onboard.py choose KMERIA --defaults --default-source github --output /tmp/kmeria_choice_generic.json --allow-external-output`
- `printf '\n\n\n' | python3 scripts/program_onboard.py choose BUSCO --plain --output /tmp/busco_choice_plain.json --allow-external-output`
- `printf 'x\n' | python3 scripts/program_onboard.py choose BUSCO --plain --output /tmp/invalid_choice.json --allow-external-output`
  - 按预期输出 `invalid choice: x`,不抛 Python traceback。
- `python3 scripts/program_onboard.py choose KMERIA --defaults --output /tmp/blocked_choice.json`
  - 按预期阻断:输出路径必须在 `config/` 下。
- `python3 scripts/validate_program_cards.py`
- `python3 scripts/validate_program_cards.py --check-drafts`
- `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`

### 当前结论

- 现在未知程序接入的"交互确认"不是 KMERIA 专用脚本了;通用入口是
  `python3 scripts/program_onboard.py choose <program>`。
- `choose` 只记录选择,不安装、不 clone、不联网、不扫数据、不提交 SLURM。
- 后续向用户汇报时必须说明当前 L0-L6 层级,避免把轻量探测说成实际运行测试。

### Caveats / 下一步

- `choose` 只解决确认项收集;真实 GitHub/source 安装仍要单独写 reviewed manual plan。
- KMERIA 专用 `scripts/kmeria_onboarding_wizard.py` 仍保留,但通用流程应优先使用 `program_onboard.py choose KMERIA --default-source github`。
- 后续可以把 `choose` 输出自动并入 evidence bundle,但当前版本先保持 project-local config,避免污染证据目录。

---

## 2026-06-17 — KMERIA onboarding 测试: GitHub source proposal-only

### 背景 / 目标

用户准备测试/接入 KMERIA: <https://github.com/Sh1ne111/KMERIA>。按 bio-workflow program-level route
执行第三版 unknown-program onboarding:先查 registry/card,再本地轻量 probe,再基于 GitHub 官方文档生成
proposal-only evidence,不安装、不 clone、不写 Conda env、不提交 SLURM。

### 已完成动作

- 新增 `scripts/kmeria_onboarding_wizard.py`:
  - 解决当前聊天 UI 不能弹 `request_user_input` 选择框的问题。
  - 在真实终端里优先使用 `curses` 上下键/Enter 菜单;不支持 TTY 时回退到编号输入。
  - 选项含 `Type something` 自定义输入。
  - 默认输出 `config/kmeria_onboarding_choice.json`,供下一步自动读取。
  - 验证命令:
    - `PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/kmeria_onboarding_wizard.py`
    - `python3 scripts/kmeria_onboarding_wizard.py --print-options`
    - `python3 scripts/kmeria_onboarding_wizard.py --defaults --output /tmp/kmeria_onboarding_choice.json`
- `python3 scripts/program_card_lookup.py KMERIA`
  - 返回 `Status UNKNOWN`;当前 registry 没有 KMERIA active card。
- `python3 scripts/program_onboard.py probe KMERIA`
  - evidence bundle: `reports/program-onboarding/kmeria/20260617T145205/`
  - `intent.tsv`: `Status=UNKNOWN`
  - `local_discovery.tsv`: `command -v KMERIA` 和 `command -v kmeria` 均未命中。
  - Conda env 列表里发现已有 `/data9/home/qgzeng/anaconda3/envs/kmeriaenv`。
- 窄范围检查已有 env:
  - `ls -1 /data9/home/qgzeng/anaconda3/envs/kmeriaenv/bin`
  - `test -x .../bin/kmeria`, `test -x .../bin/perl`, `test -x .../bin/kmc`
  - 结论:该 env 不完整,没有 `kmeria`,没有 `perl`,没有 `kmc`;不能直接作为可运行 KMERIA 环境。
- 浏览官方 GitHub/README/Wiki:
  - KMERIA 最新 README 显示 v2.0.4 (2026-06-12)。
  - 安装方式是 clone GitHub 仓库,用仓库 `kmeria_env.yaml` 建 env,设置 `LD_LIBRARY_PATH`,给
    `bin/`, `external_tools/`, `bimbamAsso/` 加执行权限,再加入 `PATH`。
  - 主入口推荐 `scripts/kmeria_wrapper.pl`;workflow 为 `count -> kctm -> filter -> m2b -> asso`。
  - KMERIA GWAS 的 k-mer 不建议超过 31;`kmeria count` v2.0.4 虽支持 2-63,但 GWAS 场景仍需保守。
- `python3 scripts/program_onboard.py plan-install KMERIA --package KMERIA --source github`
  - evidence bundle: `reports/program-onboarding/kmeria/20260617T145326/`
  - 写入 `install_proposal.json`, `install_proposal.md`, `intent.tsv`, `local_discovery.tsv`
  - proposal 为 `github_proposal_only`;`Command=PROPOSAL_ONLY`;没有自动安装命令。
- 安全门测试:
  - `python3 scripts/program_onboard.py install --proposal reports/program-onboarding/kmeria/20260617T145326/install_proposal.json --yes`
  - 按预期阻断: automatic install only supports `source_type=conda`;GitHub source 不会被本工具自动执行。

### 当前结论

- KMERIA 当前不能直接跑:PATH 没有 `kmeria`,已有 `kmeriaenv` 也不是完整运行环境。
- KMERIA 不是普通 Conda 包接入;应走 GitHub source/manual install 流程,先确认安装位置,再 clone/建 env/设置 PATH。
- 本次没有安装、没有 clone、没有联网下载数据、没有提交 SLURM job;只做了网页读取和本地轻量检查。
- `SKILL.md` 里已有 "K-mer GWAS / KMERIA" 路由提示,但 registry/card 仍缺 KMERIA active card;后续应在真实 pilot 后补 draft/active card。

### Caveats / 风险

- 官方 wrapper 会生成 scheduler 脚本,可能自带 `--time`/queue/memory 参数;接入到本服务器时必须先审阅,不能直接提交。
- KMERIA pipeline 对输入命名、sample list、depth file、phenotype/covariate 格式敏感;还没做输入 preflight。
- `kmeria_env.yaml` 来自 GitHub raw,需要用户确认后才可用于建 env;真实安装会联网并写 Conda/env/tool path。
- README/Wiki 文档存在版本变动;正式接入时应固定 commit/release,不要只依赖 moving `main`。

### 下一步

- 用户可先运行交互选择器确认安装/pilot 方案:
  - `python3 scripts/kmeria_onboarding_wizard.py`
  - 若终端不支持上下键菜单,用 `python3 scripts/kmeria_onboarding_wizard.py --plain`
  - 生成后读取 `config/kmeria_onboarding_choice.json` 继续执行。
- 确认后再执行:
  1. clone 指定 release/commit 到确认路径
  2. 用官方 `kmeria_env.yaml` 建 env 或修复已有 `kmeriaenv`
  3. 设置 `LD_LIBRARY_PATH` 和 `PATH`,捕获 `kmeria --help`/`kmeria_wrapper.pl --help`
  4. `capture` + `draft-card`
  5. 用 1-2 个样本做最小 pilot,先验证 `count/kctm/filter/m2b/asso` 的格式链路
  6. wrapper 生成的 SLURM 脚本必须先过 `slurm_preflight.sh`/`prepare_submission.sh`,再由用户确认是否提交。

---

## 2026-06-17 — program-card v3 hardening: proposal/path/evidence/draft 修复

### 背景 / 目标

根据系统性 review 修复第三版 onboarding 的安全和证据问题:proposal 不能靠字符串标记伪装成可信输入,
evidence/draft 写入不能默认越过项目边界,失败的 help/version 不能升级成 `local_help`,大小写展示名要能命中
小写 executable,draft 不能静默覆盖或越级声明 run 级证据。

### 已完成修复

- `scripts/program_onboard.py`:
  - 新增项目路径边界校验。默认 evidence 只能写在 `reports/program-onboarding/`,draft 只能写在
    `references/program-cards/drafts/`;`--allow-external-paths` 只给 `probe`/`capture`/`draft-card`
    非安装 smoke 使用。
  - `install` 要求 proposal 位于合法 evidence bundle 且文件名为 `install_proposal.json`;
    proposal 内 `evidence_dir` 必须等于 proposal 所在目录,`install.log` 不再信任 JSON 重定向。
  - `install` 从 proposal 字段重建 Conda argv,要求 `command_argv` 和 `commands` 完全一致;校验
    env/package/version/channel token,禁止路径/option-like/shell 控制符绕过。
  - `command_attempts.tsv` 记录所有 help/version 尝试;只有 exit code 0 且有输出时才写 `version.txt`/
    `help.txt`,draft 才能使用 `local_help`。
  - `probe BUSCO` 这类展示名会依次尝试原始名、normalized key、小写名,并在 `local_discovery.tsv`
    记录每个候选。
  - `draft-card` 默认不覆盖已有 draft;需要显式 `--force`,覆盖时输出 `Status OVERWRITTEN`。
- `scripts/validate_program_cards.py --check-drafts`:
  - draft 现在必须声明未登记、引用 evidence bundle,且不能包含 `local_run` 或 `project_history`。
- 文档同步:
  - `install-proposal-template.md` 补齐 `proposal_schema_version`/`created_by`/`command_argv`/
    `program_name`/`evidence_dir`/`reuse_existing` 等实际必填字段。
  - `evidence-bundle-schema.md` 补 `command_attempts.tsv`,明确失败 help/version 不算 `local_help`。
  - `program-onboarding.md`,`README.md`,`SKILL.md` 补路径边界、draft 不覆盖和确认 gate 说明。

### 验证 / 命令

- 基础验证通过:
  - `PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/program_onboard.py scripts/program_card_lookup.py scripts/validate_program_cards.py`
  - `python3 scripts/validate_program_cards.py` → `Program card validation: PASS (4 active cards)`
  - `python3 scripts/validate_program_cards.py --check-drafts` →
    `Program card validation: PASS (4 active cards, 0 draft cards)`
  - `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`
    → `Skill is valid!`
- 安全 smoke 已跑:
  - `probe --out-root /tmp/...` 默认阻断;带 `--allow-external-paths` 的非安装 smoke 允许。
  - PATH 里只有小写 `/tmp/.../busco` 时,`probe BUSCO` 成功命中。
  - fake executable 的 help/version exit code 2 时,只生成 `command_attempts.tsv`,draft 为 `inferred`,
    不写 `help.txt`/`version.txt`。
  - fake executable 的 help/version exit code 0 时,draft 为 `local_help`,摘要显示真实输出而不是
    `[stdout]`/`[stderr]`。
  - 已有 draft 默认阻断;`--force` 后输出 `OVERWRITTEN`。
  - 篡改 `command_argv` 的 proposal 即使带 `--yes` 也阻断。
  - 篡改 `evidence_dir` 指向 `/tmp` 的 proposal 即使带 `--yes` 也阻断。
  - 项目外 proposal path 带 `--yes` 也阻断。
  - unsafe target env path 和已有 `base` env 默认阻断。
  - 临时含 `local_run` 的 draft 被 `validate_program_cards.py --check-drafts` 拒绝。
  - `program_card_lookup.py unknown_tool_example` 仍指向 `program_onboard.py probe unknown_tool_example`。
- 本轮没有执行真实安装,没有联网下载,没有提交 SLURM job。repo 内 smoke artifacts 已清理;仅保留空的
  `reports/program-onboarding/` 目录。

### 当前结论

- v3 onboarding 的执行面已从"proposal 字符串可信"收紧为"字段重建+完全一致校验"。
- evidence grade 不再被失败 help/version 误升级。
- draft promotion 仍是人工流程;validator 会拒绝 draft 中的 run/project 级证据。

### Caveats / 下一步

- `plan-install` 仍不联网查询包是否存在;它只是生成可审阅 proposal。
- 真实安装仍需要用户显式确认并通过外部审批,因为会联网并写 Conda env/cache。
- 工作区仍包含本轮之前已有的未提交/未跟踪改动;本次未回退这些无关改动。

---

## 2026-06-17 — program-card v3: unknown-program onboarding 工具链

### 背景 / 目标

把未知程序接入从手工 `program-onboarding.md` 流程推进到半自动工具链:先做便宜本地探测,再生成安装提案,
用户确认后才允许 Conda/Mamba 安装,安装后捕获环境证据,最后生成 draft program card。核心安全边界不变:
不默认联网、不默认安装、不写 `/data9/home/qgzeng/tools/`、不提交 SLURM、不扫大目录。

### 已完成变更

- `scripts/program_onboard.py`:新增统一入口,支持 5 个子命令:
  `probe`, `plan-install`, `install`, `capture`, `draft-card`。
  - `probe` 只做 `command -v`、显式路径、help/version 尝试、Conda/Mamba env 列表,证据写入
    `reports/program-onboarding/<program_key>/<timestamp>/`。
  - `plan-install` 只生成 `install_proposal.json` / `install_proposal.md`,默认独立 env:
    `bio_<program_key>`。
  - `install` 只接受本工具生成的 proposal,只正式支持 Conda/Mamba route,且无 `--yes` 必须阻断。
  - `capture` 捕获 `which`/version/help/env proof。
  - `draft-card` 写 `references/program-cards/drafts/<program_key>.md`,并复制到 evidence bundle
    `card_draft.md`;不自动登记 `registry.tsv`。
- `scripts/program_card_lookup.py`:未知程序分支从"只读 onboarding 文档"改为提示:
  `python3 scripts/program_onboard.py probe <program>`。
- `scripts/validate_program_cards.py`:新增 `--check-drafts`;active card 校验仍保持 registry-only,同时把
  `install-proposal-template.md` 和 `evidence-bundle-schema.md` 视为参考文档而不是待登记 card。
- `references/program-cards/install-proposal-template.md`:记录 proposal JSON 必填字段、默认 Conda 命令模板、
  `install --yes` 执行门禁和 proposal-only source 类型。
- `references/program-cards/evidence-bundle-schema.md`:记录 evidence bundle 文件布局、允许的轻量探测、
  draft evidence grade 上限。
- `references/program-cards/program-onboarding.md` / `references/program-cards/README.md` / `SKILL.md`:
  接入第三版路径:lookup 未命中 → probe → plan-install → 用户确认 → install → capture → draft-card →
  人工审阅和真实 pilot 后再 promotion/registry。

### 验证 / 命令

- `PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/program_onboard.py scripts/program_card_lookup.py scripts/validate_program_cards.py`
  通过。
- `python3 scripts/validate_program_cards.py` → `Program card validation: PASS (4 active cards)`。
- `python3 scripts/validate_program_cards.py --check-drafts` →
  `Program card validation: PASS (4 active cards, 0 draft cards)`。
- `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`
  → `Skill is valid!`。
- 离线 smoke 已跑:
  - `python3 scripts/program_onboard.py probe BUSCO`:当前 PATH 未发现 BUSCO,生成 `UNKNOWN` evidence bundle。
  - `python3 scripts/program_onboard.py probe unknown_tool_example`:生成未知程序 evidence bundle。
  - `python3 scripts/program_onboard.py plan-install unknown_tool_example --package unknown_tool_example --source conda`:
    生成 proposal,未执行安装。
  - `python3 scripts/program_onboard.py install --proposal <json>`:无 `--yes` 正常阻断,并打印 target env、
    expected writes、network required、完整命令。
  - `/tmp/program_onboard_fake_tool` fake executable:用 `capture` 捕获 version/help/env proof,再用
    `draft-card` 生成 draft;`validate_program_cards.py --check-drafts` 对该 draft 通过。
  - `--target-env /tmp/unsafe_env`:proposal 阶段阻断,因为 target env 不是简单 Conda env 名。
  - `--target-env base`:默认阻断已有 env,提示需显式 `--reuse-existing`。
  - `program_card_lookup.py unknown_tool_example`:未知程序下一步指向
    `python3 scripts/program_onboard.py probe unknown_tool_example`。
- smoke 生成的 `reports/program-onboarding/`, fake draft card, `scripts/__pycache__/` 已清理。
- 本轮没有执行实际安装,没有联网下载,没有提交 SLURM job。

### 当前结论

- 第三版已把未知程序 onboarding 变成可探测、可提案、可确认执行、可留证据、可生成 draft card 的闭环。
- 安装执行面目前故意很窄:只支持 Conda/Mamba proposal;container/source/GitHub/binary 只生成提案,不自动执行。
- Draft card 默认最高只写 `local_help` 或 `inferred`;`local_run`/`project_history` 仍必须等真实 pilot/run 证明后人工升级。

### Caveats / 风险

- 工作区仍未提交,且包含本轮之前已有的未提交/未跟踪改动,包括多个 playbook、`agents/openai.yaml`,
  `scripts/build_cqu_blobdir.py` 等;本次未回退这些无关改动。
- `probe` 的 help/version 尝试是轻量启动测试,仍可能遇到个别工具启动慢或 flag 语义特殊;输出会被截断保存。
- `plan-install` 不联网查询包是否存在;它生成的是安装提案,不是包可用性证明。
- `install` 真正执行会联网并写 Conda env/package cache,仍需要用户在命令层面明确 `--yes` 和外部审批。

### 下一步

- 最终提交前再跑:
  `PYTHONPYCACHEPREFIX=/tmp/bio_workflow_pycache python3 -m py_compile scripts/program_onboard.py scripts/program_card_lookup.py scripts/validate_program_cards.py`,
  `python3 scripts/validate_program_cards.py --check-drafts`,以及
  `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`。
- 真实接入新程序时,按 `probe` → `plan-install` → 用户确认 → `install --yes` → `capture` →
  `draft-card` 走完整链路;pilot 成功后再人工 promotion 到 active card 和 `registry.tsv`。

---

## 2026-06-17 — program-card v2: registry + lookup + validator

### 背景 / 目标

在 v1 "程序卡文档层" 之后推进第二版:让"我要跑某个程序"不只靠人工翻 Markdown,而是先用机器可查
registry 做程序名/别名路由,再用 validator 保证每张 card 结构一致。仍保持安全边界:不安装、不联网、不提交
SLURM、不扫大目录。

### 已完成变更

- `references/program-cards/registry.tsv`:新增程序卡索引,记录 `Program_Key` / `Display_Name` /
  `Aliases` / `Card_Path` / `Modes` / `Status`。当前 4 张 active card:
  `busco`, `minimap2-samtools`, `syri`, `biser`。
- `scripts/program_card_lookup.py`:新增轻量查询入口。输入程序名或 alias 后返回匹配 card、支持 modes;
  未收录程序返回 `UNKNOWN` 并指向 `references/program-cards/program-onboarding.md`。
- `scripts/validate_program_cards.py`:新增结构校验器,检查 registry 表头、重复 key/alias、card 是否存在、
  固定标题是否齐全、registry mode 是否写入 card、是否包含 evidence grade 和 resource-card 引用。
- `SKILL.md`:program-level route 增加优先调用
  `python3 scripts/program_card_lookup.py <program_name>`;修改 program cards 后要求跑
  `python3 scripts/validate_program_cards.py`。
- `references/program-cards/README.md`:把 `registry.tsv` 设为 authoritative card index,补 lookup/validator
  使用方式。
- `references/program-cards/template.md`:新增"新建 card 后必须登记 registry 并跑 validator"规则。
- 两个新增 Python helper 已设为 executable,与现有 `scripts/` 风格一致。

### 验证 / 命令

- `python3 -m py_compile scripts/program_card_lookup.py scripts/validate_program_cards.py` 通过。
- `python3 scripts/validate_program_cards.py` → `Program card validation: PASS (4 active cards)`。
- `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`
  → `Skill is valid!`。
- `scripts/program_card_lookup.py BUSCO` → 命中 `references/program-cards/busco.md`,
  modes=`genome,protein,transcriptome`。
- `scripts/program_card_lookup.py minimap2` → 命中
  `references/program-cards/minimap2-samtools.md`,返回 5 个 mode。
- `scripts/program_card_lookup.py unknown_tool_example` → `Status UNKNOWN`,下一步为
  `references/program-cards/program-onboarding.md`。退出码为 1,这是未知程序分支的预期行为。
- 语法检查产生的 `scripts/__pycache__/` 已清理;最终 `find scripts -maxdepth 2 -type f -name '*.pyc' -print`
  无输出。
- 本轮没有提交 SLURM job,没有安装软件,没有联网下载。

### 当前结论

- 第二版已经把 program-level workflow 从"文档可读"推进到"可路由、可校验"。
- 已知程序入口现在可先查 registry/card;未知程序会稳定落到 onboarding,不会直接安装或盲跑。
- program card 新增/修改有了最小 CI 式本地检查:先登记 `registry.tsv`,再跑 `validate_program_cards.py`。

### Caveats / 风险

- 工作区仍未提交,且包含本轮之前已有的未提交改动:`HANDOFF.md`,多个 playbook,
  `agents/openai.yaml`,新增 centromere/SD playbook,`scripts/build_cqu_blobdir.py` 等。
- `program_card_lookup.py` 是轻量别名匹配,不是自然语言 intent classifier;复杂句子仍需 agent 先抽取程序名。
- validator 只检查结构契约,不证明 card 内所有命令能跑;真实环境证据仍要靠 `local_help`/`local_run`/`project_history`
  逐步升级。
- 目前 registry 只有 4 个 active card;后续新增程序要同步补 registry。

### 下一步

- 最终提交前跑一次:
  `python3 scripts/validate_program_cards.py` 和
  `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`。
- 可选补充 smoke:分别模拟 `我要跑 BUSCO`、`我要跑 SyRI`、未知程序三类 prompt,确认 agent 路由行为符合预期。
- 后续新增程序卡时,先复制 `template.md`,再登记 `registry.tsv`,最后跑 validator。

---

## 2026-06-17 — focused review polish

### 背景 / 目标

对本轮未提交改动做最终 focused review,只看会导致 copy-paste 失败、配置契约不一致或旧坑残留的点。

### 补充修复

- `playbook-genome-quality-evaluation.md`:snailplot BUSCO 路径从旧 `busco_odb12/...` 对齐到当前 BUSCO
  循环产物 `busco_embryophyta_odb12/run_embryophyta_odb12/full_table.tsv`;snailplot 小节标题改为
  `Bonus`,避免和 read mapping 的 `## 5` 重号。
- `playbook-centromere-chipseq.md`:补 `mkdir -p` 输出目录;把 `samtools index BAM1 BAM2` 拆成两条明确命令;
  Stage B 改为 `for S in IP IN` 循环生成两份 CPM bigWig,不再保留不可执行的 `# + IN` 注释。
- `SKILL.md`:centromere 路由改成 "primary-only filtering with no MAPQ cutoff",避免把 `bwa mem -a`
  后又 `-F 2308` 的主分支误写成保留 secondary/multimapper 记录。
- `playbook-segmental-duplications.md`:SD raw filter 从 `NF>=8` 收紧为 `NF>=14`,与实际 raw schema/输出字段一致。
- `SKILL.md`/`HANDOFF.md`:quick_validate 命令统一为
  `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`,因为该脚本无
  executable bit,直接运行会 `Permission denied`。

### 验证

- `git diff --check` 通过。
- `python3 -m py_compile scripts/build_cqu_blobdir.py` 通过。
- `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .` → `Skill is valid!`。
- Focused pattern scan 未在当前 `SKILL.md` / `references/` / `scripts/` 中发现:
  `samtools index BAM1 BAM2`,不可执行 `# + IN`,旧 `busco_odb12/run_embryophyta_odb12`,旧 snailplot `## 5`
  重号,或 `multimappers kept` 过度简写。

### 仍待办

- 工作区仍未提交;下一步是检查最终 diff 后提交。

---

## 2026-06-17 — /code-review max 中小项 + B 批整合遗留修复

### 背景 / 目标

继续处理 `/code-review max` 的中/小项 #7-15,以及 2026-06-16 snailplot/centromere/SD 整合留下的 B 批核对项。

### 已完成修复

- **#7 BUSCO 覆盖风险**:`playbook-genome-quality-evaluation.md` 改为三套 lineage 循环分别输出
  `busco_${LINEAGE}`,不再用单个 `-o busco_odb10 -f` 覆盖前一次结果。
- **#8 scaffolding orient 过度声称**:`playbook-chromosome-scaffolding-cphasing.md` 明确 Cq3B 历史假易位主要来自
  per-query RagTag/HiFi-only 样本;C-Phasing orient/name 只修 reference 个体本身,不能替代每次 SyRI 的 query
  orientation check。并清掉"finishing via name.txt"旧说法。
- **#9 phased haplotype BUSCO D 诊断**:`playbook-genome-assembly.md` 补充 hifiasm hap1/hap2 各自仍包含 A+B,
  低 BUSCO D 不一定更好,可能是 over-purging/subgenome loss。
- **#10 survey heterozygosity 交接**:`playbook-genome-survey.md` QC 表新增 heterozygosity 行,并说明从
  GenomeScope2 `-p 4` model 记录;handoff 到 assembly 时带上该值。
- **#11 mapping 99.74/99.80 口径**:`playbook-genome-quality-evaluation.md` 改为 primary ONT 99.74;hap1
  ONT 99.74;hap2 ONT 99.80,不再写成"两个 hap 一样"。
- **#12 Illumina mapping**:evaluation mapping 示例补 `bwa index Cqu_final.fa`,并把 `bwa mem ref R1 R2 |
  flagstat` 改为 sort 后 `samtools flagstat illumina.bam`。
- **#13 downsample FASTQ 扩展名**:`seqtk sample "$HIFI"` 输出改为 `${ID}_70x.fq.gz`,不再误标 `.fa.gz`。
- **#14 SKILL 编号**:两条 SV 子路由改成 `⑥a`/`⑥b`,保留同属第 6 阶段但不再像重复编号。
- **#15 survey 生物学锚**:survey 的 quinoa biological frame 加 QQ74-V2 N50 66.9 Mb / BUSCO ~98.4%。

### B 批整合遗留

- **snailplot 自洽**:已 vendor `scripts/build_cqu_blobdir.py`,playbook 改为 bundled helper,不再依赖真实项目脚本。
- **BISER 列/坐标核对**:读取真实 LM134 `SDs_output` / `SD_out_filter`;确认 raw `SDs_output` chr2 在 `$4`,
  canonical `SD_out_filter` 插入 `len1` 后 chr2 在 `$5`;长度为 `end-start`,不是 `+1`;`score<=10` 是项目
  filter key,尾部 `ID=` 仅保留作 audit/provenance。
- **centromere 坐标制**:读取真实 final BED/TSV;确认 final BED/TSV 是 0-based half-open,`length_bp=end-start`。
  playbook 去掉 coordinate `〔verify〕`,保留 TRASH monomer 输入会被 `to_half_open()` 规范化的说明。
- **quick_validate 来源**:确认不是漏提交脚本,而是 skill-creator 内置校验器;
  `SKILL.md` 改为 `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`。

### 验证

- `python3 -m py_compile scripts/build_cqu_blobdir.py` 通过。
- `scripts/build_cqu_blobdir.py` 用 `/tmp` 合成 seqkit/BUSCO 输入 smoke test 成功,生成 minimal BlobDir summary。
- SD smoke:真实 `SDs_output` 前 100 行跑 playbook awk,首条 filtered 输出 `NF=15`,chr2 在 `$5`,len1/len2 为
  `end-start`。
- Centromere smoke:真实 final TSV 全部满足 `$4 == $3-$2`,bad_count=0。
- `python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .` → `Skill is valid!`。
- `git diff --check` 通过。

### 仍待办

- 本轮所有改动仍在工作区未提交;建议再跑一次 focused review 后提交。

---

## 2026-06-16 (cont.2) — /code-review max 红色高危项修复

### 背景 / 目标

按用户要求先处理 `/code-review max` 留下的"会失败/静默出错"红色 1-6 项,不扩展到中/小项和 B 批整合遗留。

### 已完成修复

- **scaffolding ↔ finishing 契约断裂**:
  - `references/playbook-chromosome-scaffolding-cphasing.md` 明确 `cqu_chrom.oriented.fa` 是下游契约:
    final `Cq*A/B` ID + 已按 reference 修正方向。
  - `references/playbook-genome-finishing.md` 改为 reference 个体流程
    `cqu_chrom.fa` → orient/name → `cqu_chrom.oriented.fa` → F2 → F3;F2 `get_gaps.py`
    使用 `cqu_chrom.oriented.fa`;Step 6 改为 preserve final IDs/orientation,禁止再跑旧
    `combined/name.txt` 的 `Chr01-18 -> Cq*A/B` 二次 rename。
- **LAI 两处硬错误**:
  - `gt ltrharvest` 增加 `-tabout`,避免默认 GFF3 被 `LTR_retriever -inharvest` 误解析。
  - `LTR_retriever -infinder` 改为 `Cqu_final.fa.finder.combine.scn`,匹配
    `LTR_FINDER_parallel -seq Cqu_final.fa` 的真实输出前缀。
- **Merqury truth set 不一致**:
  - evaluation 的 `read.meryl` 从 HiFi 改为 Illumina short reads(`sr_1.fq.gz sr_2.fq.gz`),
    并显式说明与 finishing/NextPolish2 的 short-read truth-set 口径一致,不能把 HiFi-built
    `read.meryl` 和 short-read QV 配方当同一结果引用。
- **seqkit 静默失败风险**:
  - `seqkit grep -n` 改为默认 ID 匹配(`seqkit grep -f flip.ids`),避免带描述 header 时裸 `flip.ids`
    匹配 full name 失败。
  - `seqkit replace` 增加 `-U`,并加 `comm` 预检:flip IDs 必须存在于 FASTA,rename old IDs 必须覆盖全部
    chromosome IDs。这样漏 key 会在 rename 前失败,不会把 header 清空或让方向修复丢失。

### 验证

- `seqkit grep -h`:本机 v2.10.1 帮助确认默认 match sequence ID,`-n/--by-name` 才 match full name。
- `seqkit replace -h`:本机 v2.10.1 帮助确认 `-U/--keep-untouch` 是 key 缺失时不改 sequence name。
- 静态 grep 旧红项模式:未再匹配到 `seqkit grep -n`、缺 `.fa` 的 `Cqu_final.finder.combine.scn`、
  HiFi-built Merqury `read.meryl` 注释、旧 finishing `Chr01-18 → ancestral` 复命名段。

### 仍待办

- `/code-review max` 的中/小项 #7-15 尚未处理。
- B 批整合遗留仍待核对:是否 vendor `build_cqu_blobdir.py`;BISER 坐标/score/ID;centromere BED 坐标制;
  centromere/SD smoke test;`quick_validate.py` 来源。
- 本次新增 playbook/snailplot 改动 + 红项修复均未提交。

---

## 2026-06-16 (cont.) — snailplot 落地 + 基因组结构"伞"(centromere ChIP-seq + SDs)+ codex 修复

### 背景 / 目标

把三个跑通的真实流程整合进 skill,并新开"基因组结构"分析伞(在已完成+评估的基因组上做的下游结构分析):
snailplot(评估的 bonus 轴)、着丝粒 CENH3 ChIP-seq 定位、片段重复 SD(BISER)。仅学习 LM134 单样本。

### 已完成变更

- **snailplot 落地**(`playbook-genome-quality-evaluation.md` §5 重写):真实流程**不是**经典 blobtools 三步,而是
  `seqkit fx2tab` → 自建最小 BlobDir(项目脚本 `build_cqu_blobdir.py`,仅 size+BUSCO)→ **Rust `blobtk plot --view
  snail`**。已验证可跑(18 seq / 1.27Gb / BUSCO embryophyta_odb12 2026)。dashboard / pitfall 同步更新。
- **新增** `playbook-centromere-chipseq.md`(LM134 CENH3 ChIP-seq):`bwa mem -a` → samtools 过滤分支(主分支
  repeatAware.primary = proper-pair primary,无 MAPQ 过滤)→ deeptools log2(IP/Input) → 域调用(log2≥1 / merge 5kb /
  ≥5kb)→ MACS2(辅助)→ TRASH 40bp 单体 + HOR 评分 → 每条染色体着丝粒坐标(结构调用经 CENH3 确认/微调,仅 Cq7B 扩展)。
- **新增** `playbook-segmental-duplications.md`(LM134 BISER):RepeatModeler+RepeatMasker `-xsmall` 软屏蔽 →
  BISER v1.4(`--gc-heap 2G`,内存重 fat)→ 过滤(≥1kb / score≤10≈≥90% id / 18 chr)→ intra/inter + A2A/A2B/B2B 亚基因组
  → NR 区域 + EDTA TE 组分。结果:14,464 对 → ~60.6Mb NR ≈ 4.7% 基因组。
- **SKILL.md**:新增"Genome structure(基因组结构)伞"路由块(centromere / SDs);description 关键词加
  segmental duplication / genome structure。

### 复审 / 验证

- **codex 只读 review**(scoped 到本批 4 处改动,显式禁扫 `2-C_quinoa` GB 目录;exit 0,只读 repo):报 10 条全采纳并修:
  ① SDs intra/inter split `$5→$4`(我 Stage C 整行透传,chr2 在 $4)② 着丝粒 `bwa -a`+`-F 2308` 措辞订正(实为
  primary-only 无 MAPQ 过滤,非"保留多比对")③ IP/IN 改 `for S in IP IN` 循环(原 `# + IN` 注释不可跑)④ 分支 BAM 补
  `samtools index`(deeptools 需 .bai)⑤ 清理命令块字面省略号 ⑥ SDs `-o` 是输出**文件**,可写工作目录才是 `./results` 坑
  ⑦ `bedtools merge` 加 `-i -`(本机 2.31.1 实测不加也读 stdin,仅可移植性)⑧ SDs TE 剥离占位行改伪代码 ⑨ snailplot 加
  `mkdir -p results` ⑩ "clear results/" 软化为只删指定产物。SKILL.md 路由块 codex 判干净。

### ⏳ 待办(明早一起处理)— 两批

**A. `/code-review max` 发现(本地审 35b054f vs origin/main;15 条按严重度;原始记录)**

> 更新:红色 1-6 已在 2026-06-16 (cont.2) 修复;中/小项 7-15 和 B 批整合遗留已在 2026-06-17 修复。

🔴 会失败/静默出错(已修复):
1. **scaffolding↔finishing 染色体 ID/方向契约断裂**:scaffolding 新 "orient & name" 出 `cqu_chrom.oriented.fa`(改名
   Cq*A/B + 反向互补),但 finishing 仍按原始 Chr01-18 faidx + name.txt 改名且不反向互补 → 要么改名后 key 对不上,要么方向
   修复被丢。(scaffolding:112-141 + finishing:184/242)— 最高影响
2. LAI `-infinder Cqu_final.finder.combine.scn` 少 `.fa` → 应 `Cqu_final.fa.finder.combine.scn` → 文件找不到。(eval ~98)
3. LAI `gt ltrharvest` 少 `-tabout` → 默认 GFF3,但 `-inharvest` 要 tabular → LTR_retriever 解析不了。(eval ~95)
4. Merqury QV truth set 用 HiFi,但 finishing 用 Illumina 短读(Merqury 规范);两处引同一 QV → eval 配方复现不出。(eval:53)
5. `seqkit grep -n` 匹配整条 header → 带描述的 header 用裸 flip.ids 会漏 → 染色体没反向互补 = 它要防的假 INVTR。(scaffolding ~138)
6. `seqkit replace` 少 `-U` → rename.txt 漏 key 会把 header 清空成 `>`。(scaffolding ~140)

🟠 中:
7. BUSCO `-o busco_odb10` 写死 + `-f` → 三套 lineage 互相覆盖。(eval ~71)
8. orient 步骤用在 SV 参考个体上,但出假易位的是 per-query 个体(HiFi-only/RagTag,没走 CPhasing)→ 过度声称(已软化)。(scaffolding ~144)

🟡 小/内容/nit:
9. 拆分丢了 "phased haplotype 低 duplication 才是意外" 诊断句(assembly)。
10. heterozygosity 列为 survey→assembly 交接值但 survey 没给读数(survey ~125)。
11. ONT hap2 99.80% 与正文 "99.74% 两个 hap" 不一致(eval ~165)。
12. `bwa mem` 例子缺 `bwa index` 前置(eval ~115)。
13. `seqtk sample $HIFI | gzip > *.fa.gz` 把 FASTQ 误标 .fa.gz(assembly:43)。
14. SKILL.md 两条 ⑥ 连号像笔误(实为两个 SV 子 playbook,故意)(SKILL ~170)。
15. survey 生物学框丢了 66.9Mb N50 / 98.4% BUSCO 锚(assembly 表里还在)(survey ~24)。

**B. 本次整合遗留(原始记录)**

> 更新:以下 B 批已在 2026-06-17 核对并修复;保留原始列表用于追溯。
- snailplot 的 `build_cqu_blobdir.py` 是项目脚本(未进 repo):要不要 vendor 进 `bio-workflow/scripts/`(去硬编码路径)让 playbook 自洽可跑?
- BISER 坐标系 / `score` 与 `ID=` 确切含义、≥1kb 用 `end-start` 还是 `+1`:对真实 `SDs_output` 核一眼。
- 着丝粒最终 BED 的 0-based/1-based 约定(playbook 已标 verify),发表前确认。
- centromere/SDs 命令是从子代理读到的脚本提炼的,建议跑一遍单步 smoke test 再定稿(尤其 SD 列布局 $4/$5、HOR 脚本参数)。
- `quick_validate.py`:SKILL.md:531 与旧 HANDOFF 都引用它,但 repo 现在找不到该文件 → 确认是 Claude Code 内置校验器还是漏提交脚本。

**未提交(历史记录;后续已扩大为 2026-06-17 顶部所列全部改动)**:本次 4 处改动(snailplot 重写、2 个新 playbook、SKILL umbrella + codex 10 修)均在工作区**未提交**,
等明早 review 后再连同 A 批一起决定提交策略。

---

## 2026-06-16 — Genome-assembly 管线对齐:survey/assembly 拆分 + evaluation playbook + scaffolding orient 步骤

### 背景 / 目标

把 skill 的 de-novo 管线按用户的规范 6 阶段对齐:**survey → assembly → scaffolding → gap-fill & polish →
evaluation → SV calling**,并新增系统质量评估这一阶段。

### 已完成变更

- **拆分**:`playbook-genome-survey-and-assembly.md`(已删)→ `playbook-genome-survey.md`(Read QC + k-mer
  survey)+ `playbook-genome-assembly.md`(hifiasm primary + 组装 QC)。用交叉引用保住 "survey ploidy →
  BUSCO duplication → subgenome sizes" 贯穿线索(survey 末尾 handoff、assembly 开头接续 + Stage C 三方一致性)。
- **新增** `playbook-genome-quality-evaluation.md`(从真实 `7-Genome-evalution/` 提炼):6 核心(QUAST 连续性 /
  Merqury QV / BUSCO / LAI / mapping rate / tidk telomere)+ 1 bonus(BlobToolKit snail plot,真实项目仅 staged
  未运行,如实标注)。对 primary + hap1/hap2 打分;真实数字:18 contig / N50 70.1Mb / 0 gap、QV 66.9/65.8/63.2、
  BUSCO odb12 C 99.7%、LAI 16.09/10.28/9.99、mapping 100/99.74/99.98%、telomere 36/36。
- **scaffolding** 新增 "Orient & name to a reference (synteny dot plot)" 一节:挂载后用 MUMmer(或 minimap2)
  点图判染色体名 + 方向,再 `seqkit` 改 ID + 反向互补;用真实 Cq3B rc 事故说明为什么必须在此修(否则下游 SyRI
  出假 INVTR)。
- **SKILL.md** Task routing:顶部加 6 阶段流水线总览;survey/assembly 拆成两条;新增 evaluation 路由;6 个管线阶段
  连续编号 ①–⑥(SV calling 紧跟 evaluation,非管线路由后置)。交叉引用(scaffolding/finishing)改指 assembly。

### 复审 / 验证

- 一轮 codex 只读 review(scoped 到本批小文件,禁漫扫 GB):修了 BUSCO `-m geno→genome`、scaffolding flip 顺序
  bug(先翻转再 rename)、eval "三套全跑"表述收紧、mapping hap 列展开、scaffolding "prevents that" 软化、SKILL
  ⑥ 重排。
- **BUSCO `geno` 查证(教训)**:codex 说 `geno` 错;我先怀疑(对)→ 读半截 `update_mode` 源码"确认"codex(错)
  → `busco --help` + 实跑证明 **v6.0.0 仍接受 `geno`**(等价 genome)。playbook 注释已订正为中性。教训入 memory
  `verify-tool-cli-by-help-not-source-fragment`。`-m genome` 保留(有效、匹配真实脚本)。
- `quick_validate.py` → `Skill is valid!`;7 个 playbook 全在路由。

### 下一步

- 本提交后用 `/code-review ultra` 云端复审本批;按发现修复后再 push。

---

## 2026-06-16 — 今日新增 playbook 模块：两轮 Codex 只读 review + 修复

### 背景 / 目标

对今天新增/重构的模块(`playbook-variant-synteny-syri.md`、`playbook-high-confidence-sv-multicaller.md`、
finishing F2、`scripts/fill_gap_from_spanning_alignment.py`)做两轮 codex 只读复审并逐条修复。
经验:codex **只锁这几个小文件、禁止漫扫 GB 级数据**(prompt 经 `- < file`、`-s read-only`、`touch HANDOFF`
压 stop guard)——两轮各几分钟出结果,远好过此前漫扫 33 分钟无果。

### Round 1 修复

- **P1**:`SKILL.md` 高置信路由 SURVIVOR 仍 `type=0`→`1000 1 1 0 0 50`;high-conf large-event awk 的 `c` 没传进
  awk→`-v caller="$c"`;gap-fill 脚本缺 identity 阈值 + 锚定只看 ref span;多 gap 重建无重叠检测;finishing join
  验证误用 `asm5` 比 HiFi reads→`map-hifi`。
- **P2/P3**:SVIM-asm 被误称 read-based;run-state 0/19 vs 2/19 口径;plotsr cfg "exactly 12 keys" 不准;`cat`
  拼 FASTA 歧义;SVLEN=END-POS+1 约定 caveat——全修。

### Round 2 修复(脚本加固为主)

- **P1**:gap-fill splice 用候选 `r_left/r_right`(比对锚点)而非原 gap 边界 → donor 在 gap 边缘有 deletion 时会静默
  删非 gap 碱基。**重构**:要求 donor 恰好锚定到 gap 两边沿(`r_left==gap_s0-1 且 r_right==gap_e0+1`,否则拒绝),
  splice 改按**原 gap 坐标** `ref[..gap_s0-1]+fill+ref[gap_e0+1..]`,只换 N 段。
- **P2/P3**:per-flank 分别统计 aligned 列数 + identity;overlap 跳过标 `skipped_overlap`(report 与 FASTA 一致);
  `--min-identity` 加 [0,1] 校验;tie-break 改 fill 长度+qname+fill;high-conf large BED awk 加 `SVTYPE=(DEL|INV|DUP)`;
  C2 list `: >` 清空 + 写 `callers_order`;finishing RagTag awk 用 `sub(/_RagTag.*/,"")` 保 `Cq..` 前缀;variant
  sources 行 SVIM-asm 改 assembly-based。

### 验证

- gap-fill 脚本每轮改动后跑**合成数据端到端测试**:正向 contig / 反向 read / 重复 gff 去重 / identity 拒绝 /
  双 gap 拼回——全部与预期一致。`quick_validate.py` → `Skill is valid!`;`py syntax OK`。
- codex 全程 `-s read-only`;HANDOFF 经 snapshot+touch 保护未被改写。本次只动 skill 文件,未碰用户真实项目。

---

## 2026-06-16 — high-confidence SV playbook + gap-fill 跨越脚本 + finishing F2 两路重构

### 背景 / 目标

继续补领域大脑:① 把"读段层高置信 SV(SyRI+SVIM-asm+Sniffles2 三 caller)"提炼成第 5 个 playbook;
② 把 finishing 的人工 gap-filling 从"IGV 肉眼挑跨越序列"升级成可复现的 pysam 脚本并重构 F2。
关键工具语义**全部实证**(读源码/帮助 + 受控小实验),不凭记忆。

### 已完成变更

- **新增 `references/playbook-high-confidence-sv-multicaller.md`(METHOD DRAFT)** + `SKILL.md` 新增
  "High-confidence SV(multi-caller consensus)"路由。同一参考 Cqu_final.fa 上三 caller 正交
  (SyRI 复用 + SVIM-asm 装配 + Sniffles2 读段),per-sample SURVIVOR union 合并,read∩assembly = 高置信轴。
- **SURVIVOR / SVIM-asm 参数实证修正**(写进 playbook):
  - SURVIVOR `type=0→1`:实测 `type=0` 把 DEL+INS+DEL 并成一条 `SUPP=3`、SVTYPE 取少数派
    (`SVTYPE=INS`/`SVLEN=-500` 自相矛盾)→ 虚高一致性;`est_dist` 在 1.0.7 标 "Disabled"(无效);
    大 SV under-merge(`max_dist=1000` 固定、两端都要进窗;实测 100kb DEL 断点差 1.5kb 就并不上)
    → 定"保持 1000 + 大事件单独 reciprocal-overlap"。
  - SVIM-asm `--max_sv_size`:帮助原文是"DEL/INV vs translocation 分界",默认 100kb 把大倒位
    **误报成 translocation**(非"丢弃");override 1e8 才报成 INV;准确性靠后续确认而非放开 cap。
  - 纠正旧错句 "type kept in INFO"(实为 SURVIVOR 的 FORMAT `TY` 字段)。
- **新增 skill 脚本 `scripts/fill_gap_from_spanning_alignment.py`(pysam)**:把"IGV 挑跨越 reads/contigs"
  程序化——单条线性 PRIMARY 跨越;锚定 contig 50kb/read 1kb;MAPQ≥30(优先≥50);两翼 identity(排除 N)
  + 决定性次序(可复现);反向由 BAM 参考向 SEQ + pysam 自动处理;只换 N 段。**合成数据端到端验证通过**
  (正向 contig + 反向 read 都正确填入真值)。
- **`references/playbook-genome-finishing.md` F2 重构**:三种方法 → **两条路**(A=TGS-GapCloser,
  `--racon/--ne` 是其参数;B=上面脚本的跨越法),删掉对半成品 `7-Auto_gapsfilling/` 的误导引用。

### 验证

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .   # Skill is valid!
grep -oE 'playbook-[a-z-]+\.md' SKILL.md     # 5 条 playbook 路由
# SURVIVOR / svim-asm / pysam gap-fill 脚本均跑了受控小实验,结果与预期一致
```

### caveats

- high-confidence SV playbook 标 **METHOD DRAFT**(真实运行当时读段侧未跑完;方法/命令/版本已坐实)。
- 应用户要求也改了**真实项目** `2-C_quinoa/.../6-high_quality_sv_calling/scripts/`(16_ type=1、
  14_ 注释校准、新增 19_large_event_concordance.sh,已合成验证)——这些**不在本 repo**,未纳入本次提交。
- gap-fill 脚本只做进 skill,未动用户项目 `5-Gaps_filling/`。

---

## 2026-06-16 — variant+synteny SyRI playbook + yak 修正 + skills.md 清理 + 直推

### 背景 / 目标

继续把 bio-workflow 往"生信副驾"领域大脑方向补：新增第 4 个领域 playbook（结构变异 + 共线性），
并顺手修掉两处历史遗留（finishing playbook 的 yak 误用、冗余的 skills.md 镜像）。本轮还纠正了
"必须临时 clone push"的过时做法——当前目录 `.git` 已恢复正常，直接 `git push` 即可。

### 已完成变更

- **新增 `references/playbook-variant-synteny-syri.md`（260 行，DRAFT）**
  - 从真实藜麦目录提炼：链式 SyRI（`6-Comparation/7-pangenome`，20 基因组成链）vs all2ref
    （`3-syri_analysis/all2ref`，19 材料比 Cqu）两种拓扑；共享 `minimap2 -ax asm5 --eqx → syri -F S -k`。
  - 三大坑为主轴：① minimap2 峰值 100–113G 需 ≥150G（80G OOM）；② 染色体反向互补（Cq3B；
    8/9 非 LM 样本，QQ74 十条非 Cq3B）→ SyRI `No syntenic region found` 或倒位被误画成 INVTR；
    ③ SyRI VCF 缺 SVLEN+SVTYPE 必须双补（只补一个会丢全部 INS 或塌成 NA）。
  - all2ref 下游：SURVIVOR `merge 50 1 1 1 0 50` → 群体 SV 集（实测 202,406 条，类型完整）→ SV 热点
    （100kb/50kb 窗、SUPP≥2、top10%，25,430→2,586）。plotsr 两种布局 + 18 列后期 PIL 拼图坑。
  - `SKILL.md` 路由：原 "SNP/INDEL/SV and synteny" 拆成「装配层 SV+共线性 → 新 playbook（主入口）」+
    「读段层变异 → 卡片」两条。
- **定点核对复审（取代 codex 漫扫）**：codex 漫扫 GB 级真实目录跑 33 min 无果（rg 卡在 syri.out/vcf）；
  改用只读子代理点名小文件 + 对合并 VCF 一次计数，4 min 出 P1/P2/P3。约 40 项断言精确命中（含实测
  202,406）；7 处偏差全修（版本号未证标注、两版 VCF 分布加"需重数"脚注、方向修正样本数说精确、
  热点 `parse_vcf_weighted` 只认 4 类的坑加重、base.cfg 补全 12 key、breakpoint marker 颜色不一致、
  Cqu==LM134 坐标注明）。经验写入项目 memory `codex-review-no-broad-dir-scan`。
- **`references/playbook-genome-finishing.md` yak 修正**：`yak count -b37` 是两遍 bloom filter，两个位置
  参数是"两份相同的流"非"R1,R2"。改成 `<(zcat sr_1 sr_2) <(zcat sr_1 sr_2)`，并加 pitfalls 告警
  （原归档脚本 R1 喂两次、playbook 旧写法 R1/R2 拆开，两种都错）。
- **删除 `skills.md`**（不再维护逐字镜像）：仅 `SKILL.md` 被 loader 加载，全局/`.codex` 配置均不引用小写
  skills.md。清理 `SKILL.md`/`README.md`/`validation-checklists.md` 里"保持镜像 + cmp"的指令。

### 验证 / 命令

```bash
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py .   # Skill is valid!
grep -oE 'playbook-[a-z-]+\.md' SKILL.md | sort -u   # 4 条 playbook 路由
git ls-remote --heads origin   # 远端可达，main=adce445，本地无分叉 → 直接 fast-forward push
```

### caveats

- variant-synteny playbook 仍是 DRAFT：`syri 1.7.1` 版本号未证（需现场 `--version`）；SVLEN-only/SVTYPE-only
  两版的类型分布数字未在交接留痕（已加"需重数"脚注，总数 199,343 有据）。
- **本轮起改为直推**：`.git` 正常、`origin` SSH 可达、本地 main 跟踪 origin/main 且同步于 adce445；
  无需再走 `/tmp` 临时 clone。HANDOFF 旧条目里"必须临时 clone"的说法已作废。

---

## 2026-06-16 — 领域 playbook ×3：从真实藜麦流程提炼"生信副驾"大脑

### 背景 / 目标

把 bio-workflow 从"安全运维 harness"往用户初衷"**生信副驾**"拉回:安全层是地基,领域大脑才是
主角。从用户**真实跑通**的藜麦(异源四倍体 AABB, 2n=4x=36)流程提炼领域 playbook,联网查证关键
事实,经两轮 Codex 复审后整合进 SKILL.md 任务路由。

### 已完成变更

- 新增 `references/playbook-genome-survey-and-assembly.md`
  - Read QC(NanoPlot/seqkit）→ k-mer survey(KMC+GenomeScope2 `-p 4` + FastK+Smudgeplot)→
    hifiasm primary(HiFi-only 铺量 / HiFi+ONT `--ul` 参考级)→ QUAST/BUSCO(eudicots_odb10)/TIDK QC。
  - 多倍体解读:GenomeScope p4 ≈ 单倍体染色体组(~0.5Gb ≈ 一个亚基因组),primary ≈ 1C 配子(A+B ~1.3Gb);
    BUSCO 高重复(~94%)是亚基因组、正常;survey 尺寸 ≠ 组装尺寸。降采样 50–70× 为**可选**。
- 新增 `references/playbook-chromosome-scaffolding-cphasing.md`
  - CPhasing + Pore-C:`-n` 决策(异源 `-n 18` 折叠 / 同源 `-n 基数:倍性` 相位);酶 HindIII(AAGCTT);
    Juicebox 人工校正;资源右配(实测峰值 25G,300G 严重过申);**锚定 ~96.9% 入 18 染色体,~303 小 contig 未定位**。
- 新增 `references/playbook-genome-finishing.md`
  - RagTag 参考挂载(dotplot + LAI <10/10-20/>20)给无 3C 样本;TGS-GapCloser+ONT **逐 gap 手动填**
    (切 200kb 窗口→填→拼回;`--racon`/`--ne`/HiFi-contig 跨越;**端粒 = reads/contigs overlap 延伸**,
    nextdenovo 仅供体来源);NextPolish2+HiFi polish + merqury QV(merged ≈63.2,hap1/hap2 66.9/65.8)。
- `SKILL.md` / `skills.md`:`Task routing` 新增/改写 3 条路由指向上述 playbook(领域 playbook 当主入口、
  资源卡退为细节层)。

### 两轮 Codex 复审（只读沙箱,REVIEW ONLY 压 Stop hook,快照还原兜底）

- 端粒措辞先纠正:不是"nextdenovo 延伸端粒",本质是 reads/contigs overlap 延伸。
- Round 1:0 P1 + 7 P2 + 2 P3 → 全修(gfatools 前缀、CPhasing 子命令标简化、yak R1 用两次警示、
  QV 归属、端粒 minimap2 方向、18 组 vs 亚基因组、端粒非 T2T、dotplot awk、gap 窗口可加宽)。
- Round 2:8/9 CLOSED + 又抓 4 个(QV 残留绑定 `Cqu_final.fa`→merged 63.2;anchoring 100%→96.9%;
  survey cov 静默 fallback 40 危险→改 fail;gap re-splice 坐标重叠会重复 flank→改连续不重叠)→ 全修。
- Codex 全程实地交叉核对真实 AGP/fai/summary，数字对账。

### 验证 / 命令

```bash
grep -oE 'playbook-[a-z-]+\.md' SKILL.md   # 3 条路由
cmp -s SKILL.md skills.md                   # PASS 镜像
python3 .../quick_validate.py .             # Skill is valid!（需带 yaml 的 python）
```

### caveats

- 三条流程的真实运行均已确认**跑通**(survey 10/10、CPhasing 流程完整跑通且锚定 ~96.9% 入 18 染色体、
  finishing scaffold/gap/polish 成功);但 Chr04 gap 故意留空、RagTag lm270/lm411 的 LAI 未完成。
- playbook 是领域知识草稿,部分手动步骤(gap 提取/拼接、`--racon↔--ne` 选择)仍需人工判断。
- 已 push 到 GitHub `Qgzeng-Bio/Bio-workflow`(commit `adce445`,远端 `main`,经临时 clone fast-forward,
  非强推);当前目录 `.git` 异常,后续 push 仍走临时 clone。本条 HANDOFF 微调将随下次 push 同步到远端。

---

## 2026-06-15 — Executor 三件套补全：gen_sbatch + submit_and_log（含 slurm_preflight 深修）

### 背景 / 目标

在 `prepare_submission.sh`（提交闸门）基础上把 executor 三件套补齐：前端 `gen_sbatch.sh`
负责"造 preflight-clean 脚本"，后端 `submit_and_log.sh` 负责"确认后提交 + 记账"，闸门居中。
分工：生成器/提交器只管 SLURM 信封与安全壳，工具命令交给使用者填。

### 已完成变更

- 新增 `scripts/gen_sbatch.sh`（前端，零确认生成脚本）
  - 按参数拼 sbatch 骨架：绝对 `%j_%x` 日志、`set -euo pipefail`、`THREADS=${SLURM_CPUS_PER_TASK}`
    转发、array manifest 读行；normal/fat/fat2/high 默认不加 `--time`（debug 或 `--allow-time` 才加）。
  - **preflight-by-construction**：生成后先跑 `bash -n` 再跑 `slurm_preflight.sh`，任一不过就不吐脚本。
  - 校验：log-dir/chdir/out 经 `resolve_safe`（realpath 失效/残留 `..` → fail-closed）后查保护目录；
    array 须为合法 range/list + `%[1-9][0-9]*`（拒 `foo%4`/`%0`/`:0`）；mem 拒 `0`；`--out` 默认不覆盖。
- 新增 `scripts/submit_and_log.sh`（后端，确认后提交）
  - **复用** `prepare_submission.sh` 当最终闸门（不重造检查）。默认 dry-run，只有 `--yes` 才 `sbatch`。
  - 阻断：NO-GO、缺 `--yes`、record 不可写、脚本指纹自闸门后变化（TOCTOU，sha256/stat，拿不到则 fail-closed）。
  - 提交后写 `reports/run_record.tsv`（Job_ID/Job_Name/Script/Partition/CPUs/Mem/Array/Submit_Time/User，
    `whoami` 有 fallback）；**无 `--array` 旗标**（array 必须在脚本里，闸门才看得到）。
- 深修 `scripts/slurm_preflight.sh`（惠及 preflight / prepare_submission / gen_sbatch 全体）
  - `rm` 递归+强制检测改 awk token 扫描：认 `-rf`/`-fr`/`-r -f`/`--recursive --force`/`-Rf`/`/bin/rm`，剥行内注释避免误报。
  - protected 路径检查改为扫**所有**引用行（不再只看首行）；write_pattern 加入 `rm`、`-delete`。
- `SKILL.md` / `skills.md`：第 6 节加 `gen_sbatch.sh`，第 7 节加 `submit_and_log.sh`。

### Codex 复审（只读沙箱，REVIEW ONLY 压住其 Stop hook）

- 三件套首轮：7 个发现（`--cmd` 注入删保护目录、realpath fail-open、`--array` 绕过闸门、TOCTOU、
  提交后才记账、生成物无语法检查、array/mem 校验松）→ 全修。
- 确认轮：6 CLOSED + 5 新发现 → 修了 5 个可行动项（protected 全引用、`-delete`、`:0`、行内注释误报、
  指纹 fail-closed）。
- **明确不追**（静态启发式固有极限，非威胁模型）：`$RM -rf` / `bash -c "rm -rf"` / `eval` 等变量间接/
  动态求值；反向区间 `10-1`（SLURM 提交时自拒）。真正防线是文件系统权限 + 人工确认闸门。

### 命令 / 测试结果

```bash
bash -n scripts/{slurm_preflight,gen_sbatch,submit_and_log}.sh
python3 .../quick_validate.py .../bio-workflow   # 需带 yaml 的 python (anaconda3)
cmp -s SKILL.md skills.md
```

夹具回归（`/tmp/bio_prepare_sub_fixtures`，`--yes` 全用假 sbatch，**未提交任何真实作业**）：

- gen→gate→submit 闭环：生成物 preflight `PASS=18 FAIL=0` → 闸门 GO → dry-run 显示命令 → `--yes` 假 sbatch 提交 + 记账。
- 拦截全绿：`rm -r -f /protected`、`/bin/rm -rf`、`find /protected -delete`、先读后写 protected、`--cmd` 引号未闭合、
  realpath 失效路径、`--conc/%0/:0`、`mem=0`、NO-GO 拒提交、record 不可写拒提交、TOCTOU、`--array` 旗标已删。
- 无误报：含 `rm` 良性词 / 行内注释 `# rm -rf` 不触发；`good.sbatch` 仍 `PASS=18`。

### caveats / 注意事项

- preflight 是抓**常见误操作**的安全网，不是安全沙箱；动态求值类删除无法静态穷尽（见上"不追"）。
- 项目 `check_quota.sh` 比全局副本多一行 `STATUS=`；`new_env.sh` 仍只在全局。
- 本轮改动已 push 到 GitHub `Qgzeng-Bio/Bio-workflow`（commit `ab6d5bc`，远端 `main`，经临时 clone fast-forward，非强推）；当前目录 `.git` 仍异常，后续 push 仍需走临时 clone 或重新 clone。
- `codex exec` 的 Stop hook 会自动写 HANDOFF；本会话所有 Codex 复审均加 "REVIEW ONLY" 压住 hook，并快照还原兜底。

### 下一步

1. （已完成）executor 三件套 + slurm_preflight 深修已 push（`ab6d5bc`）；本条 HANDOFF 微调将随下次 push 同步到远端。
2. 视情况把 `check_quota.sh` 的 `STATUS=` 行同步回全局副本。
3. 真实项目首次用三件套时，把任何误报/漏报最小化成 `/tmp` 夹具再微调。

---

## 2026-06-15 — Executor 闸门 prepare_submission.sh（创建 + 两轮 Codex 复审修复）

### 背景 / 目标

给 `bio-workflow` 补 "executor" 成分：把"提交前靠 agent 自觉逐项检查"固化成一个只读
"绿灯包"脚本——一条命令跑完 输入 / preflight / array-manifest / 配额 / 覆盖 检查，给出
GO / NO-GO，并打印未执行的 `sbatch` 命令。它绝不提交；"按提交键"仍是用户确认动作。

### 已完成变更

- 新增 `scripts/prepare_submission.sh`（只读编排闸门）
  - 编排已有只读 helper：`check_inputs.sh`（输入）→ `slurm_preflight.sh`（SBATCH 规则）→
    `parallelization_audit.sh`（array 任务数 + manifest 表头）→ `check_quota.sh`（配额 dry-run）
    → 输出目录 保护/覆盖 检查。
  - 硬阻断（NO-GO，exit 1）：preflight FAIL、输入缺失/空、manifest 表头、`--output` 落在
    `/data9/home/qgzeng/data` 或 `/data9/home/qgzeng/tools`、配额超提交上限、`--output` 无法
    规范化为绝对路径。
  - WARN（需确认，不拦）：preflight WARN、输出目录非空、配额/表头未知、helper 缺失降级。
  - 自带 `array_task_count()`（范围/步长/逗号列表，前导零强制十进制）、`audit_col()`（按 TSV
    表头名取列）。
  - helper 跨"项目 `scripts/` + 全局 skill `scripts/`"两处查找，缺失即 WARN 降级，绝不挂。
- 把 `check_inputs.sh`、`check_quota.sh`、`submit_chunked.sh` 拷入项目 `scripts/`，使项目自包含。
- `check_quota.sh` dry-run 分支新增机器可读状态 `STATUS=SUBMIT_LIMIT_EXCEEDED` / `STATUS=OK`，
  供 `prepare_submission.sh` 稳定解析（不再依赖中文文案）。
- `SKILL.md` / `skills.md`：第 7 节 "Preflight before submitting" 新增 `prepare_submission.sh`
  作为一键提交前闸门入口。

### 两轮 Codex 复审（只读沙箱）→ 11 个问题全部修复

- Round-1（7 个）：protected `--output` 仍判 GO、manifest 表头仍 GO、`--conc 0` 生成非法 `%0`、
  已有 array 任务数误算、TSV 列号硬编码、配额中文文案匹配、死代码 `n_files`。
- Round-2（4 个）：表头硬阻断被"脚本自带 array"分支绕过、`array_task_count` 前导零按八进制误算、
  `audit_col` 缺列 fail-open 默认成无表头、`realpath` 失效时保护路径 fail-open。
- 全部已修，并夹具回归验证（见下）。

### 命令 / 测试结果

已运行：

```bash
bash -n scripts/prepare_submission.sh
bash -n scripts/check_quota.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
```

夹具回归（`/tmp/bio_prepare_sub_fixtures`，只读，未提交任何作业）：

- 干净路径 → 🟢 GO，自动出 `sbatch --array=1-2%2 ...`（未提交）。
- manifest 表头（含自带 array 的脚本）→ 🔴 NO-GO，表头硬阻断不被绕过。
- `--conc 0` → exit 2。
- `--output /data9/home/qgzeng/data | /tools | 相对保护路径` → 🔴 NO-GO。
- `realpath` 失效 + 相对路径 → 🔴 NO-GO（保守拒绝）；`realpath` 正常 + 相对非保护 → 不误拦。
- `array_task_count`：`10-20%2→11`、`001-010→10`、`08-10→3`、`1-5,10-20%2→16`、`abc→WARN`。
- `check_quota.sh -n 2 → STATUS=OK`；`-n 500 → STATUS=SUBMIT_LIMIT_EXCEEDED`。

### caveats / 注意事项

- 项目 `check_quota.sh` 比全局副本多一行 `STATUS=`（向后兼容，无害）；`new_env.sh` 仍只在全局。
- 当前目录 `.git` 异常，本轮所有改动只在本地，尚未推到 GitHub `Qgzeng-Bio/Bio-workflow`。
- `codex exec` 的 Stop hook 会自动往 `HANDOFF.md` 写复审记录；本轮已回退它写的两条过时记录，
  换成本条准确合并记录。再跑 Codex 前需先处理该 hook（禁用或跑完即回退）。
- `prepare_submission.sh` 是闸门，不提交作业；`sbatch` 仍需用户确认。

### 下一步

1. 补全三件套：`gen_sbatch.sh`（造 preflight-clean 脚本）、`submit_and_log.sh`（确认后提交 + 记账）。
2. 择机把本轮改动 push 到 GitHub（需先处理异常 `.git/` 或重新 clone）。
3. 视情况把 `check_quota.sh` 的 `STATUS=` 行同步回全局副本。

---

## 2026-06-15 — Review fixes：protected SBATCH、失败 time log、manifest 表头

### 背景 / 目标

根据整体 review 发现的 3 个内部使用风险做修复：`#SBATCH` 日志路径可绕过 protected path 检查；失败的 `/usr/bin/time -v` 日志会被误用于降 CPU/内存；array manifest 表头可能被当成第一个任务执行。

### 已完成变更

- `scripts/slurm_preflight.sh`
  - `#SBATCH --output` / `--error` 若指向 `/data9/home/qgzeng/data` 或 `/data9/home/qgzeng/tools`，现在直接 `FAIL`。
  - 新增 `#SBATCH --chdir` 检查，禁止作业工作目录指向 protected path。
- `scripts/resource_usage_audit.sh`
  - 解析 `/usr/bin/time -v` 的 `Exit status`。
  - 非 0 exit status 分类为 `RUN_FAILED`，`Recommended_CPUs=NA`，提示先 triage，不再给降 CPU/内存建议。
  - TSV 输出新增 `Exit_Status` 列。
- `scripts/parallelization_audit.sh`
  - 检测 manifest 第一条非注释记录是否为 `Sample_ID/Input_1/Chunk_ID` 等表头。
  - 有表头时任务数自动扣除表头，并在 `Recommended_Action` 中提示默认模板要求无表头。
  - TSV 输出新增 `Manifest_Header` 列。
- `assets/slurm-templates/per_sample_array.sbatch` / `per_chunk_array.sbatch`
  - 增加 manifest 表头 fail-fast 检查，避免把表头当样本或 chunk 跑。
- `SKILL.md` / `skills.md` / `references/validation-checklists.md`
  - 同步说明：非 0 time log 不能用于资源下调； bundled array templates 默认使用无表头 manifest；preflight 应检查 SBATCH 日志/chdir protected path。

### 命令 / 测试结果

已运行：

```bash
bash -n scripts/resource_usage_audit.sh
bash -n scripts/parallelization_audit.sh
bash -n scripts/slurm_preflight.sh
bash -n scripts/project_state_audit.sh
bash -n scripts/slurm_failure_triage.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
```

关键夹具结果：

- `protected_sbatch_log.sbatch`：`#SBATCH --output=/data9/home/qgzeng/data/%j_%x.out` 被 preflight 阻断，`FAIL=1`。
- `protected_chdir.sbatch`：`#SBATCH --chdir=/data9/home/qgzeng/tools` 被 preflight 阻断，`FAIL=1`。
- `failed.time`：`Exit status: 1` 输出 `Classification=RUN_FAILED`、`Recommended_CPUs=NA`。
- `manifest_with_header.tsv`：`parallelization_audit.sh` 输出 `Estimated_Tasks=2`、`Manifest_Header=1`、`#SBATCH --array=1-2%2`，并提示默认模板要求无表头。
- 原正常夹具仍通过：`array_ok.sbatch` preflight `PASS=18 WARN=0 FAIL=0`；成功 `pilot_count.time` 仍推荐 `Recommended_CPUs=4`。

### caveats / 注意事项

- 本轮仍未提交、取消或重提任何 SLURM 作业。
- 这些修复只增强审计和模板保护；正式项目脚本生成或提交仍需用户确认。

---

## 2026-06-15 — 资源反馈闭环与 SLURM array 泛化优化

### 背景 / 目标

上一轮 KMERIA pilot 暴露出一个更通用的问题：脚本可能申请很多 CPU，但实际工具只用到少数 CPU；多个独立样本/文件也可能被写成串行命令。本轮目标是把这个问题固化成 `bio-workflow` 的通用能力：提交前审计 CPU 传递和串行瓶颈，pilot 后用真实 `/usr/bin/time -v` / `sacct` 证据反推更合理的 `--cpus-per-task`、`--mem` 和 SLURM array `%N` 并发上限。

### 已完成变更

- `SKILL.md` / `skills.md`
  - 新增 `Resource feedback loop`：未知工具先做小 pilot/benchmark，再解析 `Percent of CPU`、`MaxRSS`、walltime 和 SLURM accounting。
  - 明确判定规则：CPU efficiency `<50%` 视为 `CPU_OVERREQUEST`；4/8/16 线程 walltime 改善 `<15%` 时选接近最快的最小线程数；内存使用 `<35%` 只 WARN，不自动降内存。
  - 明确独立样本/染色体/文件默认优先用 SLURM array，而不是一个大 CPU 串行 job。
- `scripts/resource_usage_audit.sh`
  - 新增只读资源审计脚本。
  - 输出 TSV：`Requested_CPUs`、`Estimated_Used_CPUs`、`CPU_Efficiency`、`Requested_Mem_GB`、`MaxRSS_GB`、`Mem_Efficiency`、`Classification`、`Recommended_CPUs`、`Recommended_Action`。
  - 不写 `reports/resource_usage.tsv`，只打印建议。
- `scripts/parallelization_audit.sh`
  - 新增只读并行审计脚本。
  - 检测重复串行大计算命令、循环内大计算、`--cpus-per-task >4` 但未传线程参数。
  - 输出候选并行单元、估计任务数、推荐 array 结构、每任务 CPU、array `%N` 并发上限和模板路径。
- `scripts/slurm_preflight.sh`
  - 增加 WARN：高 CPU 申请但无 `--threads/-t/-p/-@/--cpus` 或 `$SLURM_CPUS_PER_TASK`。
  - 增加 WARN：多个独立-looking 大计算命令串行执行时，建议运行 `parallelization_audit.sh`。
  - 保留原 FAIL 逻辑：相对日志、array 无 `%N`、未保护 `| head`、`rm -rf`、保护目录写入等仍为阻断。
- 新增模板资产
  - `assets/slurm-templates/per_sample_array.sbatch`
  - `assets/slurm-templates/per_chunk_array.sbatch`
  - 模板包含绝对日志路径占位、`%A_%a_%x`、manifest 行读取、每任务独立输出/临时目录、可按失败 array index 单独重跑的结构。

### 命令 / 测试结果

已运行静态检查：

```bash
bash -n scripts/resource_usage_audit.sh
bash -n scripts/parallelization_audit.sh
bash -n scripts/slurm_preflight.sh
python3 /data9/home/qgzeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data9/home/qgzeng/projects/3-Biotools_create/bio-workflow
cmp -s SKILL.md skills.md
```

验证结果：

- `quick_validate.py` 输出 `Skill is valid!`。
- `cmp -s SKILL.md skills.md` 退出 0。
- 当前目录不是正常 git repo，`git status --short` 返回 `fatal: not a git repository`。

`/tmp/bio_workflow_audit_fixtures/` 夹具测试：

- `cpu_no_forward.sbatch`：preflight 正确 WARN `--cpus-per-task=16` 但未传线程参数。
- `cpu_forward.sbatch`：使用 `${SLURM_CPUS_PER_TASK}` 后不触发 CPU 未传递 WARN。
- `serial_multi.sbatch`：8 条串行 `kmeria count` 被 preflight WARN，`parallelization_audit.sh` 推荐 `#SBATCH --array=1-8%2` 和 `assets/slurm-templates/per_sample_array.sbatch`。
- `array_ok.sbatch`：`#SBATCH --array=1-8%2` 通过 array cap 检查，preflight `PASS=17 WARN=0 FAIL=0`。
- `pilot_count.time`：`Percent of CPU=306%` + requested CPU 16 解析为 `Estimated_Used_CPUs=3.06`、`CPU_Efficiency=19.1`，分类 `CPU_OVERREQUEST;MEM_OVERREQUEST`，推荐 `Recommended_CPUs=4`。
- 4/8/16 benchmark 夹具：扩展性差时推荐 4 CPU；8 明显快于 4 且 16 无收益时推荐 8 CPU。

### 当前结论

- 说人话就是：skill 现在不会只看“申请了多少 CPU”，而会追问“工具到底用了多少 CPU”和“样本是不是其实可以 array 跑”。
- `resource_usage_audit.sh` 负责 pilot 后用真实日志反推资源。
- `parallelization_audit.sh` 负责提交前找串行瓶颈并给出 array 模板。
- `slurm_preflight.sh` 负责把明显浪费 CPU 或串行独立任务的问题提前 WARN 出来。

### caveats / 注意事项

- 本轮没有提交、取消或重提任何 SLURM 作业。
- 本轮没有修改 KMERIA 真实项目脚本、结果目录或 `reports/resource_usage.tsv`。
- 新审计脚本是启发式工具；它们给出建议，不自动改正式分析脚本，也不自动下调内存。
- `/tmp/bio_workflow_audit_fixtures/` 是临时测试夹具，不是项目正式数据。
- array `%N` 推荐仍需结合真实内存、I/O、数据库竞争和当前队列压力人工确认。

### 下一步建议

1. 在真实 KMERIA pilot/benchmark 终态后，用 `scripts/resource_usage_audit.sh --script <sbatch> --time-log <time.log> --stage <name>` 复查资源效率。
2. 对真实批处理脚本先跑 `scripts/slurm_preflight.sh --script <file>`；若出现串行或 CPU 未传递 WARN，再跑 `scripts/parallelization_audit.sh --script <file> --manifest <manifest.tsv> --mode auto`。
3. 若用户确认要改真实项目脚本，再基于 `assets/slurm-templates/per_sample_array.sbatch` 生成项目专用 array 脚本；生成和提交必须分开确认。
4. 如后续要发布到 GitHub，需先处理当前目录异常 `.git/` 或重新 clone 官方远端。

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
