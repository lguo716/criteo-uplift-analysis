# 阶段8：Power BI展示与指标核对

目标：把结论变成可检查的管理层展示。

源文件为powerbi/Criteo.pbip，包含Criteo.Report与Criteo.SemanticModel。重建命令：`python powerbi/build_dashboard.py`；构建会重写自动生成的报告源文件，手工编辑时先保留自己的版本。

三页依次为实验效果、模型与人群、预算策略。导入reports/tables的汇总CSV，不导入300万行原始明细。ProjectRoot是Power Query根路径参数；移动项目时修改它。

指标切片器切换访问/转化；未选时度量默认访问。预算切片器是独立参数，只影响预算卡片和策略表，默认20%；曲线始终展示全部预算。全量策略仅在100%出现，其他预算显示空值具有明确含义。

区间和模型都由Python计算，Power BI不会在切片器变化时重新训练或Bootstrap。静态解读明确标注“20%访问情景”，不跟随切片器重新解释。

实际验收需核对Desktop中的样本、发生率、主模型和预算结果，再保存PBIX、重新打开、刷新并导出截图。结构验证不是数据或视觉验收的替代。

本轮已在Desktop完成上述步骤：33项DAX数值核对和10项原生交互/保存记录通过，三页高清截图来自实际PBIX。完整操作及39个度量说明见[Power BI使用说明](../powerbi/README.md)。在线Schema获取告警与实际应用验收分开记录。

证据：powerbi/validation.json、desktop_verification.json、reports/figures/powerbi，以及[验收记录](../reports/project_acceptance.md)。该记录保留实际应用检查和远程Schema可访问性边界。

复盘问题：为什么预计算汇总表不能随便重新聚合置信区间？预算参数为什么不与曲线建立普通筛选关系？移动项目如何刷新？
