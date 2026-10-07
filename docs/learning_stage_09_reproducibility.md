# 阶段9：复现与验收

目标：独立重现分析流程，核对数据、计算结果和看板指标的一致性。

先读README的复现说明、reports/findings.md和reports/project_acceptance.md。在Python 3.12独立虚拟环境中安装锁定依赖，执行`python -m src.run_pipeline --stage all --sample-size 3000000 --seed 42`。首次运行会下载并校验官方数据，然后完成抽样、实验分析、训练、评估与汇总报告。

分阶段检查：对照data/source_manifest.json验证源文件SHA256；对照data/sample_manifest.json核对抽样位置指纹和180万/60万/60万划分。确认输入只有f0—f11，类别编码在训练集拟合，验证集锁定模型，测试集用于最终评估。

执行`python -m pytest -q`检查已知效果、处理比例校正、预算边界与曲线。执行`python -m src.run_pipeline --stage verify`复核行号、互斥划分及预测，并通过DuckDB独立SQL比较样本量、标签约束和两项率差。具体证据分别位于reports/artifact_verification.json和reports/sql_verification.json。

运行`python -m src.execute_notebooks`复核两份Notebook，运行`python tools/check_delivery.py`检查文档链接、导出表、截图与原生PBIX包。更换项目目录后，修改Power BI的ProjectRoot参数，刷新汇总CSV；参考powerbi/README.md核对指标和预算切片器。

通过标准：样本量和指标在Python、SQL与Power BI中一致；20%预算保留响应基准优于选定Uplift模型的实际结果；只报告公开样本的离线估计与归一化成本，并准确说明非均匀抽样和条件区间的局限。
