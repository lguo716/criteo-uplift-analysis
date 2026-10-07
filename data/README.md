# 数据资产

- `raw/`：经大小和SHA256校验的官方压缩CSV，约311MB。
- `processed/sample.parquet`：完整文件均匀抽样300万条，含源行号、12个匿名特征、4个标签与固定数据集划分。
- `processed/predictions_visit.parquet`及`predictions_conversion.parquet`：验证、测试预测和真实标签，用于复核曲线；不含训练集评分。
- `source_manifest.json`：来源、版本、许可、文件校验记录。
- `sample_manifest.json`：抽样方法、种子、位置指纹、划分数量和Parquet指纹。

row_id是源行位置，不是用户身份；不作为模型输入。重复匿名记录保留并在清单中计数。源数据没有时间戳、收入和实际成本，不能用行号解释时间或计算真实ROI。

使用许可与引用见`../NOTICE.md`。原始和行级派生数据只作为本地可复现资产，代码仓库忽略它们。
