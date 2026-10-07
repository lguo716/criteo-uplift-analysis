# 阶段5：S、T、X-Learner

目标：理解从响应预测到条件平均增量估计的三种方式。

执行：`python -m src.run_pipeline --stage train`；核心代码src/models.py。训练会覆盖本项目模型产物，学习时优先读已保存结果。

S-Learner训练一个输入X和随机处理T的响应模型。预测时把T设为1与0，两个概率相减。T-Learner分别在处理组和控制组训练响应模型，再作概率差。

X-Learner对控制组构造μ1(X)−Y，对处理组构造Y−μ0(X)，训练两个效应回归。使用训练组比例p组合pτ0+(1−p)τ1。本次处理不平衡，X可利用较大组的信息，但不保证比S/T好。

特征只有f0—f11。连续按数值，类别字典仅在训练集拟合，未见类别视为缺失。禁止exposure、结果标签、源位置或split作为预测变量；S中的处理T是需要比较的干预参数。

普通响应模型不输入T，预测谁会发生结果，用于排序基准。其AUC描述响应预测能力，不能代替增量排序评估。

证据：models/feature_encoder.json、training_config.json、reports/tables/training_iterations.csv。

复盘问题：S为什么可能忽略T？T为什么会受小控制组影响？为什么只看高转化概率不能判断广告增量？
