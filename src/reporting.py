import os
from pathlib import Path

from .config import ROOT

os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import nbformat
import numpy as np
import pandas as pd

from .utils import read_json, write_table

COLORS = {"s_learner": "#2563EB", "t_learner": "#D97706", "x_learner": "#16A34A", "response": "#64748B", "random": "#94A3B8", "uplift": "#2563EB"}
NAMES = {"s_learner": "S-Learner", "t_learner": "T-Learner", "x_learner": "X-Learner", "response": "响应概率排序", "random": "随机投放（期望）", "uplift": "Uplift 定向", "all_treatment": "全量投放", "no_treatment": "不投放"}


def table(name):
    return pd.read_csv(ROOT / "reports/tables" / f"{name}.csv")


def set_style():
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(path)).get_name()
            break
    plt.rcParams.update({"axes.unicode_minus": False, "figure.facecolor": "#F8FAFC", "axes.facecolor": "#FFFFFF", "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#CBD5E1", "axes.labelcolor": "#334155", "text.color": "#0F172A", "xtick.color": "#475569", "ytick.color": "#475569", "font.size": 11, "savefig.dpi": 180})


def save(fig, name, caption):
    # Reserve a separate footer band so Chinese captions never overlap axis labels.
    fig.set_layout_engine("constrained", rect=(0, 0.10, 1, 0.90))
    fig.text(0.02, 0.012, caption, fontsize=9, color="#64748B")
    fig.savefig(ROOT / "reports/figures" / f"{name}.png", bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def figures():
    set_style()
    groups, summary, curves, strategies = table("experiment_groups"), table("experiment_summary"), table("uplift_curves"), table("budget_strategies")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.7), layout="constrained")
    for ax, outcome in zip(axes, ["visit", "conversion"]):
        group = groups.loc[groups.outcome == outcome].sort_values("treatment")
        rates = group.rate.to_numpy() * 100
        errors = np.vstack([rates - group.ci_lower.to_numpy() * 100, group.ci_upper.to_numpy() * 100 - rates])
        ax.bar(group.group_label, rates, color=["#94A3B8", "#2563EB"], width=0.55, yerr=errors, capsize=5)
        for i, value in enumerate(rates):
            ax.text(i, value * 1.04, f"{value:.3f}%", ha="center")
        ax.set_ylim(0, max(rates) * 1.23)
        ax.set_title(("访问" if outcome == "visit" else "转化") + "率与 95% Wilson 区间", loc="left", fontweight="bold")
        ax.set_ylabel("发生率（%）")
    save(fig, "01_experiment_rates", "Criteo v2.1 公开样本；N=3,000,000；实验组2,550,075 / 对照组449,925；标签观察期为分组后两周")
    fig, ax = plt.subplots(figsize=(10.5, 4.4), layout="constrained")
    x = np.arange(2)
    delta = summary.ate.to_numpy() * 100
    ax.errorbar(delta, x, xerr=np.vstack([delta - summary.ci_lower.to_numpy() * 100, summary.ci_upper.to_numpy() * 100 - delta]), fmt="o", color="#2563EB", capsize=6, markersize=9)
    ax.axvline(0, color="#CBD5E1", linestyle="--")
    ax.set_yticks(x, ["访问（预设主指标）", "转化（探索性）"])
    ax.set_xlabel("实验组 − 对照组（百分点）")
    ax.set_title("公开样本的组间差异：95% Newcombe 区间", loc="left", fontweight="bold")
    save(fig, "02_experiment_increment", "N=3,000,000；经过发布者非均匀抽样，不能还原原广告活动的真实增量")
    for outcome in ["visit", "conversion"]:
        part = curves.loc[curves.outcome == outcome]
        selected = part.loc[part.selected_model == True, "model"].iloc[0]
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
        for name, group in part.groupby("model"):
            group = group.sort_values("budget_fraction")
            axes[0].plot(group.budget_fraction * 100, group.gain * 10000, label=NAMES[name], color=COLORS[name], linewidth=2.5 if name == selected else 1.6)
            axes[1].plot(group.budget_fraction * 100, group.gain_vs_random * 10000, label=NAMES[name], color=COLORS[name], linewidth=2.5 if name == selected else 1.6)
            if name == selected:
                axes[0].fill_between(group.budget_fraction * 100, group.ci_lower * 10000, group.ci_upper * 10000, color=COLORS[name], alpha=0.13)
        reference = part.loc[part.model == "response"].sort_values("budget_fraction")
        axes[0].plot(reference.budget_fraction * 100, reference.random_gain * 10000, color="#94A3B8", linestyle="--", label="随机投放期望")
        axes[1].axhline(0, color="#94A3B8", linestyle="--")
        for ax in axes:
            ax.set_xlabel("目标人群占比（%）")
            ax.set_ylabel("每万名候选用户的增量次数")
            ax.grid(axis="y", alpha=0.18)
            ax.legend(fontsize=9)
        label = "访问" if outcome == "visit" else "转化"
        axes[0].set_title(f"{label}累计增量曲线", loc="left", fontweight="bold")
        axes[1].set_title(f"{label} Qini 曲线：相对随机的增量", loc="left", fontweight="bold")
        save(fig, f"03_{outcome}_uplift_curves", f"独立测试集N=600,000；模型在验证集锁定为 {NAMES[selected]}；阴影为500次配对分层Bootstrap的条件区间")
    balance = table("feature_balance")
    fig, ax = plt.subplots(figsize=(11, 5), layout="constrained")
    ax.barh(balance.feature, balance.difference, color=["#2563EB" if kind == "continuous" else "#0D9488" for kind in balance.kind])
    ax.axvline(0.1, color="#DC2626", linestyle="--", label="描述性参考线0.1")
    ax.set_xlabel("连续特征：绝对SMD；类别特征：总变差距离（量纲不同）")
    ax.set_title("处理前特征平衡检查", loc="left", fontweight="bold")
    ax.legend()
    save(fig, "04_feature_balance", "N=3,000,000；分组约85%/15%；参考线只作描述，不能证明随机化成功或正式SRM通过")
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout="constrained")
    for ax, outcome in zip(axes, ["visit", "conversion"]):
        for strategy in ["random", "response", "uplift"]:
            part = strategies.loc[(strategies.outcome == outcome) & (strategies.strategy == strategy)].sort_values("budget_fraction")
            ax.plot(part.budget_fraction * 100, part.incremental_per_10000, marker="o", label=NAMES[strategy], color=COLORS[strategy])
            if strategy == "uplift":
                ax.fill_between(part.budget_fraction * 100, part.ci_lower_per_10000, part.ci_upper_per_10000, color=COLORS[strategy], alpha=0.12)
        ax.axvline(20, color="#CBD5E1", linestyle="--")
        ax.set_title(("访问" if outcome == "visit" else "转化") + "预算情景", loc="left", fontweight="bold")
        ax.set_xlabel("预算 / 触达人群比例（%）")
        ax.set_ylabel("每万名候选用户的增量次数")
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.18)
    save(fig, "05_budget_strategies", "独立测试集N=600,000；单位触达成本归一化为1；曲线是离线情景，不包含真实成本、金额或ROI")
    deciles = table("decile_profiles")
    part = deciles.loc[(deciles.outcome == "visit") & (deciles.selected_model == True)].sort_values("decile")
    fig, ax = plt.subplots(figsize=(11, 4.6), layout="constrained")
    ax.bar(part.decile, part.ipw_uplift * 100, color=["#2563EB" if i <= 2 else "#93C5FD" for i in part.decile])
    ax.axhline(0, color="#CBD5E1")
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("评分十分位组（1=最高）")
    ax.set_ylabel("处理比例校正的组平均增量（百分点）")
    ax.set_title("访问增量排序的人群诊断", loc="left", fontweight="bold")
    save(fig, "06_visit_deciles", "独立测试集N=600,000；每组60,000人；分组可描述排序表现，无法确定某个用户的真实反事实类型")


def findings():
    manifest, selection = read_json(ROOT / "data/sample_manifest.json"), read_json(ROOT / "models/model_selection.json")
    exp, model, budget = table("experiment_summary"), table("model_evaluation"), table("budget_strategies")
    visit, conversion = exp.set_index("outcome").loc["visit"], exp.set_index("outcome").loc["conversion"]
    relative_intervals = table("experiment_effect_intervals").query('metric == "relative_lift"').set_index("outcome")
    target = budget.loc[(budget.outcome == "visit") & (budget.strategy == "uplift") & (budget.budget_fraction == 0.2)].iloc[0]
    random = budget.loc[(budget.outcome == "visit") & (budget.strategy == "random") & (budget.budget_fraction == 0.2)].iloc[0]
    response = budget.loc[(budget.outcome == "visit") & (budget.strategy == "response") & (budget.budget_fraction == 0.2)].iloc[0]
    paired = table("paired_uncertainty")
    response_difference = paired.loc[(paired.outcome == "visit") & (paired.model == selection["visit"]["model"]) & (paired.budget_fraction == 0.2)].iloc[0]
    winner = selection["visit"]["model"]
    delta_sentence = "在20%预算情景中，相对随机投放的条件区间下限大于0，支持继续开展独立线上验证。" if target.vs_random_ci_lower_per_10000 > 0 else "在20%预算情景中，相对随机投放的条件区间未排除0，尚不足以证明定向策略有稳定优势。"
    content = f"""# 广告投放增量评估与精准营销：业务分析报告

## 数据与决策问题

使用Criteo v2.1公开基准，扫描完整{manifest['source_rows']:,}条记录后均匀随机抽取{manifest['sample_size']:,}条，种子42。每行代表一个匿名用户在一次实验中的记录；标签表示分组后两周内是否访问、转化。实验组{int(visit.n_treatment):,}人，对照组{int(visit.n_control):,}人。数据没有真实成本、收入、时间戳、广告主编号或可解释的人口属性。

回答三个问题：公开样本中是否存在增量差异；模型能否把增量较高的人群排在前面；固定预算下定向策略是否优于随机选择。访问为预设主指标，转化为探索性辅助指标。

## 实验结果

| 指标 | 实验组 | 对照组 | 绝对差（百分点） | 95%区间（百分点） | 相对提升 | 相对提升95%区间 |
|---|---:|---:|---:|---:|---:|---:|
| 访问 | {visit.rate_treatment:.3%} | {visit.rate_control:.3%} | {visit.ate*100:.4f} | [{visit.ci_lower*100:.4f}, {visit.ci_upper*100:.4f}] | {visit.relative_lift:.2%} | [{relative_intervals.loc['visit','ci_lower']:.2%}, {relative_intervals.loc['visit','ci_upper']:.2%}] |
| 转化 | {conversion.rate_treatment:.3%} | {conversion.rate_control:.3%} | {conversion.ate*100:.4f} | [{conversion.ci_lower*100:.4f}, {conversion.ci_upper*100:.4f}] | {conversion.relative_lift:.2%} | [{relative_intervals.loc['conversion','ci_lower']:.2%}, {relative_intervals.loc['conversion','ci_upper']:.2%}] |

![实验发生率](figures/01_experiment_rates.png)

两项公开样本组间差异的区间均高于0。访问是主要推断；转化结果属于辅助探索，不据此把真实平台收益外推为确定值。组率用Wilson区间，率差用Newcombe区间，不能把各组区间简单相减。

相对提升使用log风险比正态近似区间再减1。四类估计与区间统一导出至[experiment_effect_intervals.csv](tables/experiment_effect_intervals.csv)；计算方法及来源见[统计口径](../docs/metric_definitions.md)。

## 数据质量与平衡

完整原始文件通过缺失、有限值、二元标签、控制组不得曝光、无访问不得转化及行数检查。连续变量使用绝对SMD，匿名类别使用总变差距离；12个特征的描述性差异均小于0.1。类别参考线为项目描述性约定，量纲不同于SMD。公开约85%/15%比例不等于原始实验的预设分流方案，不能宣称正式SRM检验通过。

![特征平衡](figures/04_feature_balance.png)

## 模型与独立评估

训练/验证/测试={manifest['split_counts']['train']:,}/{manifest['split_counts']['validation']:,}/{manifest['split_counts']['test']:,}，按处理组、访问和转化的联合标签分层。类别字典只在训练集拟合，未见类别按缺失处理；曝光、结果标签及行号均不是模型输入。

访问比较S/T/X-Learner，转化比较S/T-Learner。普通响应概率模型只作为排序对照。LightGBM使用预先固定参数和验证集早停；主模型按验证集Qini选择，访问锁定为**{NAMES[winner]}**，转化锁定为**{NAMES[selection['conversion']['model']]}**。不根据测试结果更换主模型。

![访问模型曲线](figures/03_visit_uplift_curves.png)

完整模型数值见 [model_evaluation.csv](tables/model_evaluation.csv)，所有模型均保留验证集和测试集结果。

## 20%预算情景与业务建议

| 策略 | 每万名候选用户的增量访问 | 95%条件区间 | 归一化触达成本 |
|---|---:|---:|---:|
| 随机选择20% | {random.incremental_per_10000:.2f} | [{random.ci_lower_per_10000:.2f}, {random.ci_upper_per_10000:.2f}] | 2,000 |
| 响应概率选择20% | {response.incremental_per_10000:.2f} | [{response.ci_lower_per_10000:.2f}, {response.ci_upper_per_10000:.2f}] | 2,000 |
| Uplift选择20% | {target.incremental_per_10000:.2f} | [{target.ci_lower_per_10000:.2f}, {target.ci_upper_per_10000:.2f}] | 2,000 |

定向相对随机的增量差为每万人{target.vs_random_per_10000:.2f}次，配对95%条件区间[{target.vs_random_ci_lower_per_10000:.2f}, {target.vs_random_ci_upper_per_10000:.2f}]。{delta_sentence}选择20%预算来自预设展示情景，不是从测试集挑选出的最优预算。

**普通响应概率排序优于本次选定的访问Uplift模型。** 同预算下，{NAMES[winner]}相对响应排序的差为每万人{target.incremental_per_10000-response.incremental_per_10000:.2f}次，配对95%条件区间[{response_difference.paired_vs_response_ci_lower*10000:.2f}, {response_difference.paired_vs_response_ci_upper*10000:.2f}]。这说明不能因为使用了因果模型就认定策略更好，也不依据测试结果重新选择Uplift主模型。

![预算情景](figures/05_budget_strategies.png)

建议将响应排序与访问增量排序共同作为下一轮独立实验候选，并同时观察转化。本轮没有证明S-Learner优于响应基准。匿名特征无法转化为“高收入”“年轻用户”等命名人群；十分位组只表示评分层级。未掌握实际触达成本和收入时，不把归一化效率称为真实ROI。

## 局限与下一步

发布者非均匀抽样改变了原始活动的增量规模；本报告只能讨论公开基准样本。无法观察同一个人的两个潜在结果，预测评分也无法证明某个用户一定被广告说服。没有用户或广告主标识，无法做跨活动验证、聚类置信区间或核查同一人在多个实验中的关联性。

500次Bootstrap在处理组内抽样，模型间共享抽样权重。区间以已训练模型和固定Top-K成员为条件，未包含重新训练、模型选择和上线环境漂移的全部不确定性。未来真实实施需要新实验、预设主要指标、实际成本记录和独立策略验证。

## 复现与证据

- [指标与评估口径](../docs/metric_definitions.md)
- [完整学习复盘](../docs/project_complete_walkthrough.md)
- [模型选择记录](../models/model_selection.json)
- [评估协议](evaluation_protocol.json)
- [SQL核对](sql_verification.json)
- [验收记录](project_acceptance.md)
"""
    (ROOT / "reports/findings.md").write_text(content, encoding="utf-8")
    return target


def notebooks():
    intro = "# Criteo公开实验：访问与转化\n\n这是项目分析程序的学习入口。核心逻辑在src中，此Notebook读取实际结果并复核关键计算。"
    initialization = "from pathlib import Path\nimport sys\nROOT = Path.cwd()\nif ROOT.name == 'notebooks': ROOT = ROOT.parent\nsys.path.insert(0, str(ROOT))\nimport pandas as pd\nfrom IPython.display import display, Image\nfrom src.experiment import difference_ci\nfrom src.metrics import gain_curve\nfrom src.utils import read_json\nprint('项目根目录:', ROOT)"
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(intro), nbformat.v4.new_code_cell(initialization), nbformat.v4.new_markdown_cell("## 1. 文件身份与随机抽样\n读来源清单及抽样清单。row_id是原始文件位置，不是公开用户ID；不会被用作模型特征。"), nbformat.v4.new_code_cell("display(read_json(ROOT/'data/source_manifest.json'))\ndisplay(read_json(ROOT/'data/sample_manifest.json'))"), nbformat.v4.new_markdown_cell("## 2. 两组发生率和置信区间\n随机分组treatment定义处理。exposure是分组后变量，不能据此筛选实验样本。"), nbformat.v4.new_code_cell("summary = pd.read_csv(ROOT/'reports/tables/experiment_summary.csv')\ndisplay(summary)\ndisplay(pd.read_csv(ROOT/'reports/tables/experiment_effect_intervals.csv'))\nfor r in summary.itertuples():\n    lo, hi = difference_ci(r.positive_treatment, r.n_treatment, r.positive_control, r.n_control)\n    print(r.outcome, '复核95%率差区间:', lo, hi)"), nbformat.v4.new_markdown_cell("## 3. 平衡和质量\n连续SMD与类别总变差的量纲不同，参考线仅作描述。不存在原始分流方案时，不能用四舍五入的85%做正式SRM结论。"), nbformat.v4.new_code_cell("display(pd.read_csv(ROOT/'reports/tables/feature_balance.csv'))\ndisplay(pd.read_csv(ROOT/'reports/tables/data_quality_checks.csv'))\ndisplay(Image(filename=str(ROOT/'reports/figures/01_experiment_rates.png')))"), nbformat.v4.new_markdown_cell("## 4. 结论边界\n公开数据经过非均匀抽样。样本内组间差异可以支持基准研究，不能恢复原活动真实增量，也没有真实ROI。访问为主，转化为探索性辅助指标。")])
    nb.metadata.kernelspec = {"display_name": "Python (project .venv)", "language": "python", "name": "python3"}
    nbformat.write(nb, ROOT / "notebooks/01_experiment_analysis.ipynb")
    nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell("# Uplift模型、评估与预算\n\n读取已经训练的实际模型结果；核心训练方法见src/models.py。所有选择先在验证集锁定，再看测试结果。"), nbformat.v4.new_code_cell(initialization), nbformat.v4.new_markdown_cell("## 1. S、T、X-Learner\nS把处理变量加入响应模型；T分别拟合两个处理组；X利用另一组的响应预测构造效应伪标签。输入只有12个处理前特征。"), nbformat.v4.new_code_cell("display(read_json(ROOT/'models/model_selection.json'))\ndisplay(pd.read_csv(ROOT/'reports/tables/training_iterations.csv'))\ndisplay(pd.read_csv(ROOT/'reports/tables/model_evaluation.csv'))"), nbformat.v4.new_markdown_cell("## 2. 复核处理比例校正的测试集曲线\nG(q)=Σ(top-q)Y[T/p−(1−T)/(1−p)]/N；p取整个评估集的处理比例，不能在每个Top-K子集重估后混用。"), nbformat.v4.new_code_cell("pred = pd.read_parquet(ROOT/'data/processed/predictions_visit.parquet')\npred = pred.loc[pred.split == 'test']\nselected = read_json(ROOT/'models/model_selection.json')['visit']['model']\ncurve = gain_curve(pred.visit.to_numpy(), pred.treatment.to_numpy(), pred['score_'+selected].to_numpy(), pred.row_id.to_numpy())\nprint('测试Qini:', curve['qini'], '测试AUUC:', curve['auuc'])\nprint('100%预算端点:', curve['gain'][-1])\ndisplay(Image(filename=str(ROOT/'reports/figures/03_visit_uplift_curves.png')))"), nbformat.v4.new_markdown_cell("## 3. 预设20%预算的策略比较\n随机策略使用期望表现，所有策略在同一预算下比较。全量投放只作为100%成本参照。"), nbformat.v4.new_code_cell("strategies = pd.read_csv(ROOT/'reports/tables/budget_strategies.csv')\ndisplay(strategies.loc[(strategies.outcome == 'visit') & (strategies.budget_fraction == .2)])\ndisplay(pd.read_csv(ROOT/'reports/tables/paired_uncertainty.csv'))\ndisplay(Image(filename=str(ROOT/'reports/figures/05_budget_strategies.png')))"), nbformat.v4.new_markdown_cell("## 4. 条件区间与业务使用\n500次处理组内Bootstrap对所有模型使用相同权重；区间以模型及Top-K成员固定为条件，不包括重新训练和全部选择不确定性。匿名十分位人群不是已知的个体反事实类型。")])
    nb.metadata.kernelspec = {"display_name": "Python (project .venv)", "language": "python", "name": "python3"}
    nbformat.write(nb, ROOT / "notebooks/02_uplift_and_strategy.ipynb")


def powerbi_inputs():
    selections = read_json(ROOT / "models/model_selection.json")
    dimensions = pd.DataFrame([{"outcome": "visit", "outcome_label": "访问", "role": "预设主指标"}, {"outcome": "conversion", "outcome_label": "转化", "role": "探索性辅助指标"}])
    write_table("dim_outcome", dimensions)
    model_names = sorted(table("model_evaluation").model.unique())
    write_table("dim_model", pd.DataFrame([{"model": name, "model_label": NAMES[name]} for name in model_names]))
    write_table("dim_strategy", pd.DataFrame([{"strategy": name, "strategy_label": NAMES[name]} for name in ["no_treatment", "all_treatment", "random", "response", "uplift"]]))
    write_table("dim_budget", pd.DataFrame({"budget_fraction": [0, .05, .1, .2, .3, .5, .7, 1], "budget_label": ["0%", "5%", "10%", "20%", "30%", "50%", "70%", "100%"]}))
    choice_rows = []
    for outcome, value in selections.items():
        choice_rows.append({"outcome": outcome, "selected_model": value["model"], "selected_model_label": NAMES[value["model"]], "criterion": "验证集Qini"})
    write_table("selected_models", pd.DataFrame(choice_rows))


def report():
    figures()
    findings()
    notebooks()
    powerbi_inputs()
