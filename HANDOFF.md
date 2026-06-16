# Bio-Workflow Skill Handoff

Last updated: 2026-06-16 — high-confidence multi-caller SV playbook + SURVIVOR/SVIM-asm 实证修正 + gap-fill 跨越脚本 + F2 两路重构

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
quick_validate.py .                          # Skill is valid!
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
quick_validate.py .            # Skill is valid!
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
