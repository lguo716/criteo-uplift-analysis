# 阶段6：独立评估与配对Bootstrap

目标：用统一口径验证排序，避免把普通AUC当增量效果。

执行：`python -m src.run_pipeline --stage evaluate --bootstrap 500`；Notebook为notebooks/02_uplift_and_strategy.ipynb。核心在src/metrics.py和evaluate.py。

整个评估集处理比例p约0.85。定义Z=Y[T/p−(1−T)/(1−p)]，G(q)=Top-q人群的Z之和/整个候选人数N。不能直接用人数不等的处理组结果数减控制组结果数。

AUUC为G的面积；Qini为G−qG(1)的面积，按101个预算点梯形积分。所有模型100%端点必须相同，并等于这个评估集的率差；它不必等于300万总样本的率差。

模型先在验证集按Qini锁定：访问S-Learner、转化T-Learner。测试集保持60万，仅做最终比较。响应基准也保留。本次响应排序的测试Qini高于Uplift模型，这是结果，不修改选择记录来隐藏它。

500次Bootstrap在两组内部重抽样，模型共享权重。固定模型和Top-K成员意味着条件区间，未覆盖重新训练或全部模型选择的不确定性。

证据：model_evaluation.csv、uplift_curves.csv、paired_uncertainty.csv、models/model_selection.json。

复盘问题：为什么必须共享重抽样权重？不同库同名Qini能直接比吗？相同分数为什么要用独立哈希打散？
