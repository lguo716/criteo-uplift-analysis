"""Build genuine editable PBIP/PBIR and a CSV-refreshable semantic model."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
REPORT = ROOT / "Criteo.Report"
MODEL = ROOT / "Criteo.SemanticModel"
PAGES = REPORT / "definition/pages"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def lit(value):
    return {"expr": {"Literal": {"Value": str(value).lower() if isinstance(value, bool) else "'" + value.replace("'", "''") + "'" if isinstance(value, str) else str(value) + "D"}}}


def color(value):
    return {"solid": {"color": lit(value)}}


def col(table, name):
    return table, name, "column"


def met(name):
    return "Metrics", name, "measure"


def field(spec, alias=False):
    table, name, kind = spec[:3]
    return {"Measure" if kind == "measure" else "Column": {"Expression": {"SourceRef": {"Source": "s"} if alias else {"Entity": table}}, "Property": name}}


def filter_in(spec, values):
    key = hashlib.sha1((str(spec) + str(values)).encode()).hexdigest()[:20]
    literals = [{"Literal": {"Value": str(v).lower() if isinstance(v, bool) else "'" + str(v).replace("'", "''") + "'"}} for v in values]
    return {"name": key, "field": field(spec), "type": "Categorical", "filter": {"Version": 2, "From": [{"Name": "s", "Entity": spec[0], "Type": 0}], "Where": [{"Condition": {"In": {"Expressions": [field(spec, True)], "Values": [[v] for v in literals]}}}]}}


def visual(page_id, key, kind, title, position, roles=None, objects=None, filters=None, sort=None):
    x, y, width, height = position
    content = {"$schema": SCHEMA + "visualContainer/2.9.0/schema.json", "name": key, "position": {"x": x, "y": y, "z": 0, "height": height, "width": width, "tabOrder": 0}, "visual": {"visualType": kind, "drillFilterOtherVisuals": True, "visualContainerObjects": {"title": [{"properties": {"show": lit(bool(title)), "text": lit(title), "fontSize": lit(12), "fontFamily": lit("Microsoft YaHei"), "fontColor": color("#0F172A")}}], "subTitle": [{"properties": {"show": lit(False)}}], "background": [{"properties": {"show": lit(True), "color": color("#FFFFFF"), "transparency": lit(0)}}], "border": [{"properties": {"show": lit(False)}}]}}}
    if roles:
        content["visual"]["query"] = {"queryState": {role: {"projections": [{"field": field(spec), "queryRef": spec[0] + "." + spec[1], "nativeQueryRef": spec[1], "displayName": spec[3] if len(spec) > 3 else spec[1]} for spec in specs]} for role, specs in roles.items()}}
        if sort:
            content["visual"]["query"]["sortDefinition"] = {"sort": [{"field": field(sort[0]), "direction": sort[1]}], "isDefaultSort": True}
    if objects:
        content["visual"]["objects"] = objects
    if filters:
        copied = json.loads(json.dumps(filters))
        for item in copied:
            item["name"] = hashlib.sha1((page_id + key + item["name"]).encode()).hexdigest()[:20]
        content["filterConfig"] = {"filters": copied}
    write(PAGES / page_id / "visuals" / key / "visual.json", content)
    return content


def text(page_id, key, content, position, size=12, foreground="#475569", bold=False):
    value = visual(page_id, key, "textbox", "", position)
    value["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": content, "textStyle": {"fontFamily": "Microsoft YaHei", "fontSize": f"{size}pt", "color": foreground, "fontWeight": "bold" if bold else "normal"}}]}]}}]}
    value["visual"]["visualContainerObjects"]["background"][0]["properties"]["transparency"] = lit(100)
    write(PAGES / page_id / "visuals" / key / "visual.json", value)


def card(page_id, key, measure, label, position):
    visual(page_id, key, "card", label, position, {"Values": [(*met(measure), label)]}, {"labels": [{"properties": {"fontSize": lit(25), "labelDisplayUnits": lit(1), "color": color("#2563EB")}}], "categoryLabels": [{"properties": {"show": lit(False)}}]})


def matrix(page_id, key, title, position, rows, measures):
    visual(page_id, key, "pivotTable", title, position, {"Rows": rows, "Values": [(*met(name), label) for name, label in measures]}, {"grid": [{"properties": {"textSize": lit(10)}}], "rowHeaders": [{"properties": {"fontSize": lit(10)}}], "columnHeaders": [{"properties": {"fontSize": lit(10)}}], "values": [{"properties": {"fontSize": lit(10)}}], "subTotals": [{"properties": {"rowSubtotals": lit(False), "columnSubtotals": lit(False)}}]})


def slicer(page_id, key, spec, title, position):
    objects = {"data": [{"properties": {"mode": lit("Dropdown")}}], "header": [{"properties": {"show": lit(False)}}], "selection": [{"properties": {"singleSelect": lit(True)}}]}
    if spec == col("dim_outcome", "outcome_label"):
        objects["general"] = [{"properties": {"filter": {"filter": filter_in(spec, ["访问"])["filter"]}}}]
    visual(page_id, key, "slicer", title, position, {"Values": [spec]}, objects)


def page(name, title, subtitle):
    write(PAGES / name / "page.json", {"$schema": SCHEMA + "page/2.1.0/schema.json", "name": name, "displayName": title, "displayOption": "FitToPage", "height": 900, "width": 1600, "objects": {"background": [{"properties": {"color": color("#F1F5F9"), "transparency": lit(0)}}]}})
    text(name, "heading", title, (24, 8, 1180, 56), 24, "#0F172A", True)
    text(name, "subtitle", subtitle, (24, 64, 1180, 44), 11)
    slicer(name, "outcome_slicer", col("dim_outcome", "outcome_label"), "指标（默认访问）", (1250, 12, 326, 72))
    return name


def build_model():
    input_names = ["experiment_summary", "experiment_groups", "feature_balance", "model_evaluation", "uplift_curves", "budget_strategies", "decile_profiles", "selected_models", "dim_outcome", "dim_model", "dim_strategy", "dim_budget"]
    tables = []
    for name in input_names:
        frame = pd.read_csv(PROJECT / "reports/tables" / f"{name}.csv")
        columns, conversions = [], []
        for column in frame:
            dtype = "boolean" if pd.api.types.is_bool_dtype(frame[column]) else "int64" if pd.api.types.is_integer_dtype(frame[column]) else "double" if pd.api.types.is_numeric_dtype(frame[column]) else "string"
            m_type = {"boolean": "type logical", "int64": "Int64.Type", "double": "type number", "string": "type text"}[dtype]
            item = {"name": column, "dataType": dtype, "sourceColumn": column, "summarizeBy": "none"}
            if dtype == "double":
                item["formatString"] = "0.0000%" if column in ["rate", "ate", "rate_treatment", "rate_control", "budget_fraction", "ci_lower", "ci_upper", "relative_lift"] else "0.0000"
            if dtype == "int64":
                item["formatString"] = "#,0"
            if name in ["dim_outcome", "dim_model", "dim_strategy"] and column == name.removeprefix("dim_"):
                item["isKey"] = True
            if name == "dim_budget" and column == "budget_label":
                item["sortByColumn"] = "budget_fraction"
            columns.append(item)
            conversions.append('{"' + column + '", ' + m_type + '}')
        expression = 'let\n    Source = Csv.Document(File.Contents(ProjectRoot & "\\reports\\tables\\' + name + '.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n    Typed = Table.TransformColumnTypes(Headers, {' + ', '.join(conversions) + '}, "en-US")\nin\n    Typed'
        tables.append({"name": name, "columns": columns, "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": expression}}]})
    metric_table = {"name": "Metrics", "columns": [{"name": "Placeholder", "type": "calculatedTableColumn", "dataType": "string", "isHidden": True, "sourceColumn": "[Placeholder]"}], "partitions": [{"name": "Metrics", "mode": "import", "source": {"type": "calculated", "expression": 'DATATABLE("Placeholder",STRING,{{""}})'}}], "measures": []}
    measure_text = []
    def measure(name, expression, fmt="#,0.00"):
        metric_table["measures"].append({"name": name, "expression": expression, "formatString": fmt, "displayFolder": "增量评估"})
        measure_text.append(name + " =\n" + expression + "\n")
    def current(expression, table):
        return 'VAR Outcome = SELECTEDVALUE(dim_outcome[outcome], "visit") RETURN CALCULATE(' + expression + ', ' + table + '[outcome] = Outcome)'
    measure("Current Outcome", 'SELECTEDVALUE(dim_outcome[outcome_label],"访问（默认）")', "")
    measure("Selected Budget", 'SELECTEDVALUE(dim_budget[budget_fraction],0.2)', "0%")
    for label, column, fmt in [("Sample N", "n", "#,0"), ("Treatment N", "n_treatment", "#,0"), ("Control N", "n_control", "#,0"), ("Treatment Rate", "rate_treatment", "0.000%"), ("Control Rate", "rate_control", "0.000%"), ("ATE", "ate", "0.0000%"), ("ATE Lower", "ci_lower", "0.0000%"), ("ATE Upper", "ci_upper", "0.0000%"), ("Relative Lift", "relative_lift", "0.00%")]:
        measure(label, current(f"MAX(experiment_summary[{column}])", "experiment_summary"), fmt)
    measure("ATE Points", "[ATE]*100", "0.0000")
    measure("ATE Interval", '"[" & FORMAT([ATE Lower]*100,"0.0000") & ", " & FORMAT([ATE Upper]*100,"0.0000") & "]"', "")
    measure("Group Rate", current("DIVIDE(SUM(experiment_groups[positive]),SUM(experiment_groups[n]))", "experiment_groups"), "0.000%")
    for label, column, fmt in [("Group N", "n", "#,0"), ("Group Positive", "positive", "#,0"), ("Group Lower", "ci_lower", "0.000%"), ("Group Upper", "ci_upper", "0.000%")]:
        measure(label, current(f"MAX(experiment_groups[{column}])", "experiment_groups"), fmt)
    measure("Balance Difference", "MAX(feature_balance[difference])", "0.0000")
    measure("Selected Model", current("SELECTEDVALUE(selected_models[selected_model_label])", "selected_models"), "")
    for label, column, fmt in [("Test Qini", "qini", "0.000000"), ("Test AUUC", "auuc", "0.000000"), ("Test Qini Lower", "qini_ci_lower", "0.000000"), ("Test Qini Upper", "qini_ci_upper", "0.000000"), ("Test Gain20", "incremental_per_10000_at_20", "0.00")]:
        measure(label, current(f'CALCULATE(MAX(model_evaluation[{column}]),model_evaluation[split]="test")', "model_evaluation"), fmt)
    measure("Curve Increment", current("MAX(uplift_curves[gain])*10000", "uplift_curves"))
    measure("Curve Random", current("MAX(uplift_curves[random_gain])*10000", "uplift_curves"))
    measure("Decile Effect", current("MAX(decile_profiles[ipw_uplift])", "decile_profiles"), "0.000%")
    measure("Decile N", current("MAX(decile_profiles[n])", "decile_profiles"), "#,0")
    for label, column in [("Strategy Increment", "incremental_per_10000"), ("Strategy Lower", "ci_lower_per_10000"), ("Strategy Upper", "ci_upper_per_10000"), ("Strategy vs Random", "vs_random_per_10000"), ("Strategy Efficiency", "incremental_per_1000_targeted")]:
        expression = f"VAR Budget = [Selected Budget] RETURN CALCULATE(MAX(budget_strategies[{column}]),budget_strategies[budget_fraction]=Budget)"
        measure(label, current(expression, "budget_strategies"))
    measure("Strategy Curve", current("MAX(budget_strategies[incremental_per_10000])", "budget_strategies"))
    measure("Uplift Budget Gain", 'CALCULATE([Strategy Increment],REMOVEFILTERS(dim_strategy),budget_strategies[strategy]="uplift")')
    measure("Uplift Budget Advantage", 'CALCULATE([Strategy vs Random],REMOVEFILTERS(dim_strategy),budget_strategies[strategy]="uplift")')
    measure("Response Budget Gain", 'CALCULATE([Strategy Increment],REMOVEFILTERS(dim_strategy),budget_strategies[strategy]="response")')
    measure("Normalized Cost", "[Selected Budget]*10000", "#,0")
    tables.append(metric_table)
    relationships = []
    for table in tables:
        name = table["name"]
        fields = {column["name"] for column in table["columns"]}
        for key, dimension in [("outcome", "dim_outcome"), ("model", "dim_model"), ("strategy", "dim_strategy")]:
            if key in fields and name != dimension and not (key == "model" and name == "budget_strategies"):
                relationships.append({"name": name + "_" + key, "fromTable": name, "fromColumn": key, "toTable": dimension, "toColumn": key, "crossFilteringBehavior": "oneDirection"})
    model = {"name": "Criteo", "compatibilityLevel": 1606, "model": {"culture": "zh-CN", "defaultPowerBIDataSourceVersion": "powerBI_V3", "sourceQueryCulture": "en-US", "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True}, "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}, {"name": "PBI_QueryOrder", "value": json.dumps(input_names)}, {"name": "PBI_ProTooling", "value": '["DevMode"]'}], "expressions": [{"name": "ProjectRoot", "kind": "m", "expression": '"' + str(PROJECT) + '" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}], "tables": tables, "relationships": relationships}}
    write(MODEL / "model.bim", model)
    write(MODEL / "definition.pbism", {"version": "4.2", "settings": {"qnaEnabled": False}})
    (ROOT / "measures.dax").write_text("\n".join(measure_text), encoding="utf-8")


def main():
    build_model()
    write(ROOT / "Criteo.pbip", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "Criteo.Report"}}], "settings": {"enableAutoRecovery": True}})
    write(REPORT / "definition.pbir", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json", "version": "4.0", "datasetReference": {"byPath": {"path": "../Criteo.SemanticModel"}}})
    write(REPORT / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json", "metadata": {"type": "Report", "displayName": "Criteo广告增量分析"}, "config": {"version": "2.0", "logicalId": "90913d1b-d4af-424e-83b0-62d2d906b9de"}})
    write(MODEL / ".platform", {"$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json", "metadata": {"type": "SemanticModel", "displayName": "Criteo增量分析模型"}, "config": {"version": "2.0", "logicalId": "8d0f3b6d-9a3b-4f26-8f7f-ec129f2b436b"}})
    write(REPORT / "definition/version.json", {"$schema": SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    old_resources = PROJECT.parent / "olist-ecommerce-analysis/powerbi/Olist.Report/StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU09.json"
    base_path = REPORT / "StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU09.json"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    if not base_path.exists():
        shutil.copyfile(old_resources, base_path)
    theme = {"name": "Criteo_Portfolio", "dataColors": ["#2563EB", "#64748B", "#D97706", "#16A34A", "#0D9488"], "background": "#FFFFFF", "foreground": "#0F172A", "tableAccent": "#2563EB"}
    write(ROOT / "criteo-theme.json", theme)
    write(REPORT / "StaticResources/RegisteredResources/Criteo_Portfolio.json", {**theme, "name": "Criteo_Portfolio.json"})
    write(REPORT / "definition/report.json", {"$schema": SCHEMA + "report/3.3.0/schema.json", "themeCollection": {"baseTheme": {"name": "Fluent2-CY26SU09", "reportVersionAtImport": {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}, "type": "SharedResources"}, "customTheme": {"name": "Criteo_Portfolio.json", "reportVersionAtImport": {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}, "type": "RegisteredResources"}}, "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": "BaseTheme"}]}, {"name": "RegisteredResources", "type": "RegisteredResources", "items": [{"name": "Criteo_Portfolio.json", "path": "Criteo_Portfolio.json", "type": "CustomTheme"}]}], "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True}})
    ids = []
    p = page("experiment", "01 实验效果", "Criteo v2.1 · 随机样本300万人 · 分组后两周发生率 · 访问为预设主指标，转化为探索性辅助指标"); ids.append(p)
    for i, (name, label) in enumerate([("Sample N", "样本人数"), ("Treatment Rate", "实验组发生率"), ("Control Rate", "对照组发生率"), ("ATE Points", "绝对差（百分点）"), ("Relative Lift", "相对提升")]):
        card(p, "kpi_" + str(i), name, label, (24 + i * 312, 118, 296, 112))
    visual(p, "group_rates", "clusteredColumnChart", "实验组与对照组发生率", (24, 248, 738, 390), {"Category": [col("experiment_groups", "group_label")], "Y": [met("Group Rate")]}, {"labels": [{"properties": {"show": lit(True)}}]})
    visual(p, "balance_chart", "clusteredBarChart", "特征平衡：连续为绝对SMD，类别为总变差", (778, 248, 798, 390), {"Category": [col("feature_balance", "feature")], "Y": [met("Balance Difference")]}, sort=(met("Balance Difference"), "Descending"))
    matrix(p, "group_table", "样本量与95% Wilson发生率区间", (24, 654, 1006, 152), [(*col("experiment_groups", "group_label"), "实验分组")], [("Group N", "人数"), ("Group Positive", "结果发生人数"), ("Group Rate", "发生率"), ("Group Lower", "区间下限"), ("Group Upper", "区间上限")])
    card(p, "evidence", "ATE Interval", "率差95%区间（百分点）", (1050, 654, 510, 86))
    text(p, "data_limit", "曝光仅作描述。发布者非均匀抽样，\n结果限于公开基准，不能恢复真实增量。", (1050, 750, 510, 58), 11)
    text(p, "footnote", "指标切片器切换已计算的访问/转化结果；未选时默认访问。平衡图始终描述同一300万样本，0.1仅为描述性参考。", (24, 824, 1552, 52), 11)
    p = page("models", "02 模型与人群", "训练180万 / 验证60万 / 测试60万 · 模型在验证集锁定 · 此页曲线与人群图均为独立测试结果"); ids.append(p)
    card(p, "chosen", "Selected Model", "验证集选定的Uplift模型", (24, 118, 466, 108))
    text(p, "model_note", "模型与响应基准完整比较；Qini/AUUC定义统一。普通响应概率排序在本次评估中表现更高，保留这一结果。", (514, 124, 1060, 96), 13)
    visual(p, "gain_curves", "lineChart", "累计增量曲线：每万名候选用户的增量次数", (24, 246, 1004, 294), {"Category": [col("uplift_curves", "budget_fraction")], "Y": [met("Curve Increment")], "Series": [col("dim_model", "model_label")]}, {"legend": [{"properties": {"show": lit(True)}}]}, sort=(col("uplift_curves", "budget_fraction"), "Ascending"))
    visual(p, "qini", "clusteredBarChart", "独立测试集Qini（高于随机的面积）", (1044, 246, 532, 294), {"Category": [col("dim_model", "model_label")], "Y": [met("Test Qini")]}, sort=(met("Test Qini"), "Descending"))
    visual(p, "deciles", "clusteredColumnChart", "评分十分位：处理比例校正的组平均增量", (24, 556, 1004, 272), {"Category": [col("decile_profiles", "decile")], "Y": [met("Decile Effect")], "Series": [col("dim_model", "model_label")]}, sort=(col("decile_profiles", "decile"), "Ascending"))
    matrix(p, "model_table", "测试结果与95%条件区间", (1044, 556, 532, 272), [(*col("dim_model", "model_label"), "模型")], [("Test Qini", "Qini"), ("Test Qini Lower", "下限"), ("Test Qini Upper", "上限")])
    text(p, "footnote", "1为评分最高的十分位组。匿名特征无法解释成人口属性；预测排序不能证明单个用户的真实反事实。转化人群结果为探索性。", (24, 844, 1552, 40), 10)
    p = page("budget", "03 预算策略", "预设预算情景 · 单位触达成本归一化为1 · 结果为公开基准离线估计，未包含真实收入或广告成本"); ids.append(p)
    slicer(p, "budget_slicer", col("dim_budget", "budget_label"), "预算比例（默认20%）", (24, 116, 350, 72))
    for i, (name, label) in enumerate([("Uplift Budget Gain", "Uplift增量 / 每万人"), ("Response Budget Gain", "响应排序增量 / 每万人"), ("Uplift Budget Advantage", "Uplift相对随机差"), ("Normalized Cost", "归一化触达成本")]):
        card(p, "budget_kpi_" + str(i), name, label, (390 + i * 298, 116, 282, 100))
    visual(p, "budget_curves", "lineChart", "完整预算曲线：随机、响应概率、Uplift定向", (24, 236, 1552, 304), {"Category": [col("budget_strategies", "budget_fraction")], "Y": [met("Strategy Curve")], "Series": [col("dim_strategy", "strategy_label")]}, {"legend": [{"properties": {"show": lit(True)}}]}, filters=[filter_in(col("dim_strategy", "strategy"), ["random", "response", "uplift"])], sort=(col("budget_strategies", "budget_fraction"), "Ascending"))
    matrix(p, "strategy_table", "所选预算：增量、95%条件区间与触达效率", (24, 556, 1060, 266), [(*col("dim_strategy", "strategy_label"), "策略")], [("Strategy Increment", "增量 / 每万人"), ("Strategy Lower", "区间下限"), ("Strategy Upper", "区间上限"), ("Strategy Efficiency", "增量 / 千次触达")])
    text(p, "decision", "20%访问情景\nUplift：89.59次 / 每万人\n随机：21.07次 / 每万人\n响应排序：97.28次 / 每万人\n\n保留响应基准的优势，\n用新实验继续验证候选策略。", (1100, 572, 470, 244), 14)
    text(p, "footnote", "500次配对分层Bootstrap，区间以模型和Top-K成员固定为条件。预算切片器影响卡片与表格；曲线展示全部预算。全量策略仅对应100%。", (24, 844, 1552, 40), 10)
    write(PAGES / "pages.json", {"$schema": SCHEMA + "pagesMetadata/1.1.0/schema.json", "pageOrder": ids, "activePageName": ids[0]})
    print("Created editable PBIP:", ROOT / "Criteo.pbip")


if __name__ == "__main__":
    main()
