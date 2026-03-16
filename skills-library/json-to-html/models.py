"""Pydantic output models for JSON → HTML Dashboard Generator pipeline."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ─── Step 1: analyze_json_structure output ───────────────────────

class FieldClassification(BaseModel):
    """Classification of a single JSON field for visualization."""
    model_config = ConfigDict(populate_by_name=True)

    path: str = Field(..., description="Dot-notation path: e.g. 'financialSummary.totalRevenue'")
    field_type: str = Field(
        ...,
        alias="fieldType",
        description="One of: kpi, table, chart, timeline, status, risk, matrix, tag, text, boolean, null"
    )
    data_type: str = Field(
        ...,
        alias="dataType",
        description="JS type: number, string, boolean, object, array, null"
    )
    is_financial: bool = Field(False, alias="isFinancial")
    is_percentage: bool = Field(False, alias="isPercentage")
    is_date: bool = Field(False, alias="isDate")
    array_length: Optional[int] = Field(None, alias="arrayLength")
    sample_value: Optional[Any] = Field(None, alias="sampleValue")


class JsonAnalysis(BaseModel):
    """Output of the JSON structure analysis step."""
    model_config = ConfigDict(populate_by_name=True)

    shape: str = Field(
        ...,
        description="Detected shape: 'pipeline_output', 'valuation_report', 'zero_report', 'generic'"
    )
    top_level_keys: List[str] = Field(..., alias="topLevelKeys")
    total_field_count: int = Field(..., alias="totalFieldCount")
    has_skill_results: bool = Field(False, alias="hasSkillResults")
    has_validation: bool = Field(False, alias="hasValidation")
    has_financial_data: bool = Field(False, alias="hasFinancialData")
    has_timeline: bool = Field(False, alias="hasTimeline")
    has_risks: bool = Field(False, alias="hasRisks")
    language: str = Field("he", description="Detected primary language: 'he' or 'en'")
    all_fields: List[FieldClassification] = Field(default_factory=list, alias="allFields")
    title_candidate: Optional[str] = Field(None, alias="titleCandidate")
    subtitle_candidate: Optional[str] = Field(None, alias="subtitleCandidate")


# ─── Step 2: map_sections_and_tabs output ────────────────────────

class TabField(BaseModel):
    """A field assigned to a specific tab."""
    model_config = ConfigDict(populate_by_name=True)

    path: str
    visualization: str = Field(
        ...,
        description="Visual type: 'kpi_card', 'row_list', 'expense_table', 'pie_chart', "
                    "'bar_chart', 'progress_bar', 'checklist', 'timeline', 'risk_cards', "
                    "'matrix_grid', 'tag_list', 'text_block'"
    )
    label: str = Field(..., description="Hebrew display label")
    color: Optional[str] = Field(None, description="CSS color variable or hex")
    chart_id: Optional[str] = Field(None, alias="chartId", description="Canvas ID if chart")


class TabDefinition(BaseModel):
    """Definition of one HTML tab/panel."""
    model_config = ConfigDict(populate_by_name=True)

    tab_id: str = Field(..., alias="tabId", description="e.g. 'financials', 'legal'")
    label: str = Field(..., description="Hebrew tab label")
    icon: str = Field(..., description="Emoji icon for tab")
    skill_id: Optional[str] = Field(None, alias="skillId", description="Source skill if pipeline output")
    fields: List[TabField] = Field(default_factory=list)
    has_charts: bool = Field(False, alias="hasCharts")


class HeaderConfig(BaseModel):
    """Configuration for the dashboard header."""
    model_config = ConfigDict(populate_by_name=True)

    title: str
    subtitle: Optional[str] = None
    logo_text: str = Field("BlackEdge", alias="logoText")
    badges: List[Dict[str, str]] = Field(default_factory=list)


class FooterConfig(BaseModel):
    """Configuration for the dashboard footer."""
    model_config = ConfigDict(populate_by_name=True)

    report_date: Optional[str] = Field(None, alias="reportDate")
    appraiser: Optional[str] = None
    client: Optional[str] = None
    generation_date: str = Field(..., alias="generationDate")
    schema_version: Optional[str] = Field(None, alias="schemaVersion")
    model_used: Optional[str] = Field(None, alias="modelUsed")


class SectionMapping(BaseModel):
    """Output of the section mapping step."""
    model_config = ConfigDict(populate_by_name=True)

    tabs: List[TabDefinition]
    header: HeaderConfig
    footer: FooterConfig
    total_charts: int = Field(0, alias="totalCharts")
    direction: str = Field("rtl", description="'rtl' for Hebrew, 'ltr' for English")


# ─── Step 3a: generate_html_header output ────────────────────────

class HtmlHeader(BaseModel):
    """Generated HTML header section including DOCTYPE through tab bar."""
    model_config = ConfigDict(populate_by_name=True)

    css: str = Field(..., description="Complete CSS block for <style> tag")
    header_html: str = Field(..., alias="headerHtml", description="Header div HTML")
    tab_bar_html: str = Field(..., alias="tabBarHtml", description="Tab navigation HTML")


# ─── Step 3b: generate_html_panels output ────────────────────────

class PanelHtml(BaseModel):
    """Generated HTML for one tab panel."""
    model_config = ConfigDict(populate_by_name=True)

    tab_id: str = Field(..., alias="tabId")
    html: str = Field(..., description="Complete panel div HTML")
    canvas_ids: List[str] = Field(default_factory=list, alias="canvasIds")


class HtmlPanels(BaseModel):
    """All generated tab panels."""
    model_config = ConfigDict(populate_by_name=True)

    panels: List[PanelHtml]
    footer_html: str = Field(..., alias="footerHtml")


# ─── Step 3c: generate_html_charts output ────────────────────────

class ChartConfig(BaseModel):
    """A single Chart.js configuration."""
    model_config = ConfigDict(populate_by_name=True)

    canvas_id: str = Field(..., alias="canvasId")
    chart_type: str = Field(..., alias="chartType", description="'doughnut', 'bar', etc.")
    init_function_name: str = Field(..., alias="initFunctionName")
    tab_index: int = Field(..., alias="tabIndex", description="Which tab triggers this chart")
    config_json: str = Field(..., alias="configJson", description="Chart.js config as JSON string")


class HtmlCharts(BaseModel):
    """All generated Chart.js configurations and scripts."""
    model_config = ConfigDict(populate_by_name=True)

    chart_configs: List[ChartConfig] = Field(default_factory=list, alias="chartConfigs")
    tab_switch_js: str = Field(..., alias="tabSwitchJs", description="Tab switching JS function")
    lazy_init_js: str = Field(..., alias="lazyInitJs", description="Lazy chart init JS code")


# ─── Step 4: validate output ─────────────────────────────────────

class ValidationNote(BaseModel):
    """A single validation check result."""
    model_config = ConfigDict(populate_by_name=True)

    rule_id: str = Field(..., alias="ruleId")
    passed: bool
    message: Optional[str] = None


class ValidateOutput(BaseModel):
    """Output of the validation and assembly step."""
    model_config = ConfigDict(populate_by_name=True)

    validation_notes: List[ValidationNote] = Field(
        default_factory=list, alias="validationNotes"
    )
    all_fields_covered: bool = Field(False, alias="allFieldsCovered")
    tab_count: int = Field(0, alias="tabCount")
    chart_count: int = Field(0, alias="chartCount")
    html_valid: bool = Field(False, alias="htmlValid")
    total_size_bytes: Optional[int] = Field(None, alias="totalSizeBytes")


# ─── Top-level result ────────────────────────────────────────────

class DashboardResult(BaseModel):
    """Top-level output model aggregating all sub-skill results."""
    model_config = ConfigDict(populate_by_name=True)

    json_analysis: JsonAnalysis = Field(..., alias="jsonAnalysis")
    section_mapping: SectionMapping = Field(..., alias="sectionMapping")
    html_header: HtmlHeader = Field(..., alias="htmlHeader")
    html_panels: HtmlPanels = Field(..., alias="htmlPanels")
    html_charts: HtmlCharts = Field(..., alias="htmlCharts")
    validation_notes: ValidateOutput = Field(..., alias="validationNotes")
    assembled_html: str = Field(..., alias="assembledHtml", description="Final self-contained HTML string")
