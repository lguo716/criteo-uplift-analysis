# Power BI 看板使用与度量说明

交付日期：2026-10-07。报告包含三个可编辑页面，使用原生图表和导入语义模型；不依赖自定义视觉插件或在线账户。

## 打开与刷新

- [PBIX完整报告](criteo_uplift_analysis.pbix)：已包含汇总数据和三页视觉对象，可直接打开、编辑、保存。
- [PBIP项目](Criteo.pbip)：源码由`Criteo.Report/`和`Criteo.SemanticModel/`组成，适合查看JSON、模型和版本差异。
- [主题](criteo-theme.json)、[完整DAX](measures.dax)、[模型定义](Criteo.SemanticModel/model.bim)。

在Power BI Desktop主页点击“刷新”，从`reports/tables/`读取CSV。移动项目后，通过“转换数据 → 管理参数”把`ProjectRoot`改为新的项目根目录，关闭并应用，再刷新。CSV使用UTF-8、逗号分隔，数值转换使用en-US区域设置。刷新只更新Python导出的汇总结果，不训练模型、不重新计算Bootstrap。

若修改了分析逻辑，先在项目根目录运行`python -m src.run_pipeline --stage all --sample-size 3000000 --seed 42`，再刷新Desktop。仅更新结果CSV时无需重建看板。`build_dashboard.py`用于从代码重新构建源文件，会重写自动生成的模型和视觉对象；先备份手工编辑版本。Desktop提示将PBIP升级为TMDL时，可以选择“不升级”，继续保留本项目的TMSL `model.bim`。

## 三页内容与交互

| 页面 | 图表与指标 | 切片器行为 |
|---|---|---|
| 实验效果 | 样本量、两组率、百分点差、相对提升、Wilson区间、Newcombe率差区间、12特征平衡 | 访问/转化切换预计算结果；平衡始终是同一300万样本 |
| 模型与人群 | 验证集选定模型、测试累计增量曲线、Qini比较、十分位效果、Qini区间 | 访问显示S/T/X及响应基准；转化显示S/T及响应基准 |
| 预算策略 | Uplift和响应策略增量、相对随机差、归一化成本、完整预算曲线、区间与单位触达效率 | 默认访问、20%；支持0%、5%、10%、20%、30%、50%、70%、100% |

各页指标切片器独立。预算参数表不建立关系：卡片和表格使用所选预算，曲线保留所有预算。全量策略只对应100%，不投放只对应0%；其他预算不显示不适用的策略。静态业务建议标注“20%访问情景”，不会随参数改变而冒充新结论。

## 表关系与数据粒度

模型共13张表，其中12张CSV导入表和1张度量容器Metrics。`dim_outcome`单向过滤包含outcome的事实表；`dim_model`过滤模型评估、曲线、十分位；`dim_strategy`过滤策略事实。`dim_budget`为独立参数表，不直接过滤事实表。

| 核心表 | 粒度 / 来源 |
|---|---|
| experiment_summary | 指标，完整300万抽样实验汇总 |
| experiment_groups | 指标 × 处理组 |
| feature_balance | 匿名特征；连续绝对SMD / 类别总变差 |
| model_evaluation | 指标 × 模型 × 验证/测试 |
| uplift_curves | 指标 × 模型 × 101个预算网格；仅展示测试集 |
| decile_profiles | 指标 × 模型 × 测试评分十分位 |
| budget_strategies | 指标 × 策略 × 适用预算；60万独立测试候选人 |
| selected_models | 指标；依据验证集Qini锁定的增量模型 |

## 核心度量

完整39个度量见[measures.dax](measures.dax)。下表解释显示单位及分母；区间上下限均来自Python。

| 度量 | 定义与单位 |
|---|---|
| Sample N / Treatment N / Control N | 当前指标实验样本量；不随预算变化 |
| Treatment Rate / Control Rate | 当前指标组内发生率 |
| ATE | 实验组率减对照组率，内部为0到1量纲 |
| ATE Points | ATE×100，显示为百分点（访问1.0535） |
| ATE Interval | Newcombe上下限×100的文本区间 |
| Relative Lift | ATE / 对照组率 |
| Test Qini / Test AUUC | 测试曲线面积；按模型显示，不能相加 |
| Curve Increment | 测试G(q)×10,000，分母是全部候选用户 |
| Decile Effect | 当前十分位的处理比例校正平均增量 |
| Strategy Increment / Lower / Upper | 所选预算的每万候选用户增量及95%条件区间 |
| Strategy Efficiency | 每千次触达的增量结果；0预算效率为空 |
| Uplift Budget Advantage | 选定增量策略相对随机期望的差，使用配对区间核对 |
| Normalized Cost | 所选预算比例×10,000；单位触达成本假设为1 |

统一累计增量：`Z=Y×(T/p−(1−T)/(1−p))`，`G(q)=sum(top-q Z)/N`，p取整个评估集处理比例。Qini为`∫[G(q)−qG(1)]dq`，AUUC为`∫G(q)dq`。500次处理组内Bootstrap对各模型共享抽样权重；区间以已训练模型和固定Top-K为条件。发生率、百分点、每万候选人和每千触达的单位不能混用。详见[统计口径](../docs/metric_definitions.md)。

## 验收与截图

2026-10-07使用Power BI Desktop 2.158.1177.0实际保存PBIP、另存PBIX，在新Desktop进程从PBIX打开并完成原生“刷新”。33项DAX与CSV比较通过；10项原生交互/保存记录通过，包括指标切换、预算边界与默认值。

- [DAX核对](desktop_verification.json)、[原生交互记录](desktop_interaction_verification.json)、[最终保存状态](desktop_saved_status.json)。
- [实验效果高清截图](../reports/figures/powerbi/report_experiment.png)
- [模型与人群高清截图](../reports/figures/powerbi/report_models.png)
- [预算策略高清截图](../reports/figures/powerbi/report_budget.png)

截图来自官方Desktop Bridge对实际运行报告的捕获，均为2892×1624 PNG。本地结构校验[validation_offline.json](validation_offline.json)为0错误、0告警；在线[validation.json](validation.json)为0错误、6项Schema不可访问告警，其中Desktop保存的visualContainer/2.13.0官方地址返回404。因此不把在线结果称为“全部Schema校验通过”。这不影响本轮实际Desktop打开、刷新和交互验收。

辅助命令：`powershell -File powerbi/verify_desktop.ps1 -DesktopPid <当前Criteo进程ID>`只读取指定Criteo语义模型并核对DAX；`node powerbi/capture_pages.mjs <进程ID>`重新导出三页截图。Node工具精确版本在[package.json](package.json)，先执行`npm --prefix powerbi install`。Windows程序集路径默认是本机`D:/ATools/bin`，换机时需要按实际Desktop安装目录修改核对脚本。
