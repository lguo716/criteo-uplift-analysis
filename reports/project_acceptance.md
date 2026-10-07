# 项目交付与验收记录

验收日期：2026-10-07；状态：**求职项目交付完成**。所有数值来自实际下载和运行，不是预设示例。用户另行授权发布至[GitHub公开仓库](https://github.com/lguo716/criteo-uplift-analysis)，实际简历文件未改写。

## 数据身份与可复现性

完整Criteo官方修正版v2.1文件311,422,618字节、13,979,592条记录，许可CC BY-NC-SA 4.0；SHA256为`2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`。来源、版本和校验时间见[来源清单](../data/source_manifest.json)、[许可与引用](../NOTICE.md)。

从全文件均匀不放回抽取3,000,000条，seed=42，保留零基源行号row_id，分块读取并写Parquet。抽样位置SHA256为`dd6459a50a9920fb5660969c87fca3aeae23f68b09e0e56d621b088e2b7747ed`；Parquet SHA256为`1e808ff49777311a7f606ec089a25fdb4cfc5e98c24186473803c7d31e9762fa`。来源行数、完整质量检查和抽样清单见[抽样清单](../data/sample_manifest.json)。

联合处理/访问/转化标签分层得到1,800,000/600,000/600,000互斥划分；仅f0—f11作输入。连续f0/f2/f7/f10，其余8项为匿名类别；类别字典在训练集拟合并保存，预测时使用同一字典。缺失、非有限值、非二元标签、控制组曝光、无访问转化等源数据约束均通过。相同匿名画像不删除，不据此认定重复用户。

## 程序、模型与测试

独立`.venv`、精确锁定`requirements.txt`、统一阶段入口、模型文件、配置和日志均已保存。统一命令`python -m src.run_pipeline --stage all --sample-size 3000000 --seed 42`已实际成功运行；最终评估包含500次配对分层Bootstrap。

| 验收项 | 实际结果 | 证据 |
|---|---|---|
| 合成数据和边界单元测试 | 18/18通过 | tests/；实际执行pytest输出18 passed |
| 行号重抽、划分互斥、特征无泄漏、预测和曲线一致性 | 46/46通过 | [artifact_verification.json](artifact_verification.json) |
| DuckDB独立SQL样本量、标签约束、两项率差 | 7/7通过 | [sql_verification.json](sql_verification.json)、sql/ |
| 模型选择与评估隔离 | 访问S、转化T；验证集选择，测试集最终比较 | [model_selection.json](../models/model_selection.json) |
| S/T/X访问、S/T转化及响应基准 | 全部实际训练及预测 | models/、[model_evaluation.csv](tables/model_evaluation.csv) |
| 两份Notebook | 全部代码单元执行完成，无错误输出 | [实验](../notebooks/01_experiment_analysis.ipynb)、[模型与预算](../notebooks/02_uplift_and_strategy.ipynb) |
| 实验、平衡、模型、曲线、十分位、策略统一导出 | CSV和分析图均存在 | tables/、figures/ |
| 完整实验区间 | 两指标各包含两组率、率差、相对提升的95%区间 | [experiment_effect_intervals.csv](tables/experiment_effect_intervals.csv) |
| 交付文件、文档链接、Notebook执行、原生PBIX包 | 44/44通过，保存文件SHA256 | [delivery_verification.json](delivery_verification.json) |

18项测试覆盖已知效果、85%处理分配的比例校正、排序/并列处理、0%与100%边界、曲线面积，以及任意模型在100%预算下共享相同全量估计和零配对差。Bootstrap区间以已训练模型和固定Top-K成员为条件，不包含重新训练不确定性。

相对提升区间在log风险比尺度计算后转换，零事件时不返回伪造的有限区间；增加互换两组时风险比区间互为倒数的属性测试。访问相对提升27.79%，95%区间[25.80%,29.81%]；转化57.36%，区间[46.74%,68.74%]。相对变化区间与绝对百分点区间使用不同口径。

## Power BI 实际验收

使用Desktop 2.158.1177.0完成三页原生图表，保存可编辑PBIP并实际另存为[criteo_uplift_analysis.pbix](../powerbi/criteo_uplift_analysis.pbix)。新进程25416从该PBIX重新打开，点击主页“刷新”完成所有CSV查询，页面恢复且无刷新错误；完成交互后再次保存，官方状态确认无未保存更改。

| 检查 | 结果 |
|---|---|
| 三页图表 | 实验效果、模型与人群、预算策略完整，12项平衡特征可见 |
| Python / SQL / Power BI样本量 | 3,000,000；实验组2,550,075、对照组449,925 |
| DAX数值与导出表 | 33/33核对通过，包含率、差、区间、预算和行数 |
| 实验指标切换 | 访问1.0535个百分点，[0.9914,1.1149]；转化0.1114，[0.0965,0.1256] |
| 模型指标切换 | 访问选定S-Learner，转化选定T-Learner；图表和表格切换 |
| 0%预算 | 增量0，成本0 |
| 20%访问预算 | Uplift89.59、响应97.28、相对随机68.52，成本2,000 |
| 50%访问预算 | Uplift94.90、响应103.76，成本5,000 |
| 100%访问预算 | 策略共同105.33，相对随机0.00，成本10,000 |
| 最终默认值 | 访问、20%，打开为实验效果首页 |
| 高清截图 | 实际运行报告三张PNG，2892×1624，已逐页视觉检查 |

证据：[DAX记录](../powerbi/desktop_verification.json)、[10项原生交互记录](../powerbi/desktop_interaction_verification.json)、[最终保存状态](../powerbi/desktop_saved_status.json)、[看板使用说明](../powerbi/README.md)。

本地官方结构校验0错误、0告警。在线校验0错误，记录6项Schema获取告警：其中Desktop写入的visualContainer/2.13.0官方地址返回404，其他地址在本次CLI请求中无法获取。在线结果不是完整的远程Schema验证；保留原生Desktop版本格式，未通过虚构Schema消除告警。[在线记录](../powerbi/validation.json)、[本地结构记录](../powerbi/validation_offline.json)。

## 结论一致性与求职材料

访问率差1.0535个百分点；20%预算S策略每万候选人89.59次增量访问，相对随机多68.52次，配对95%条件区间[59.92,77.12]。响应基准97.28次，S相对响应差−7.69次，配对区间[−13.22,−1.50]。业务报告、README、面试稿和三条简历描述如实保留简单基准优势。

成本采用单位触达=1的归一化假设，无真实ROI。公开数据经过非均匀抽样，结果只代表公开基准，不能还原原活动增量规模；匿名特征不解释为人口属性。中文README、业务报告、完整流程复盘、九阶段学习讲解、面试稿和简历三条已交付；路线图项目二状态已同步。
