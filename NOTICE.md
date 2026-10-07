# 第三方数据与引用

数据发布者为Criteo AI Lab，使用官方组织镜像中的Criteo Uplift v2.1：
https://huggingface.co/datasets/criteo/criteo-uplift

文件`criteo-research-uplift-v2.1.csv.gz`，SHA256：
`2716e1bf0fd157a93b5bf86924d9088419dfbac2022c6cd90030220634f616dc`。

镜像标注数据许可为[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)。原始数据、抽样行、预测明细保留为本地数据资产，不随代码公开提交。本仓库中基于该数据生成的汇总表、分析图、Notebook结果和看板数据沿用CC BY-NC-SA 4.0并保留Criteo来源；项目自写代码单独采用MIT许可，不将其许可扩展到第三方数据。复用数据相关成果时请保留本声明及数据许可要求。

数据设计：Diemert et al., *A Large Scale Benchmark for Individual Treatment Effect Prediction and Uplift Modeling*, 2021, https://arxiv.org/abs/2111.10106 。同时引用初始AdKDD 2018论文 *A Large Scale Benchmark for Uplift Modeling*。

Meta-learners：Künzel et al., *Meta-learners for Estimating Heterogeneous Treatment Effects using Machine Learning*, PNAS, 2019, https://doi.org/10.1073/pnas.1804597116 。

LightGBM：Ke et al., *LightGBM: A Highly Efficient Gradient Boosting Decision Tree*, NeurIPS 2017。

Power BI报告工具为Microsoft官方Power BI Report Authoring CLI与Desktop Bridge。报告包含Desktop使用的Microsoft基础主题资源；该第三方资源不属于项目自写代码的MIT许可范围。
