"""Pydantic output models for Monitoring Report (דוח מעקב) extraction."""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectInfo(BaseModel):
    """Project identification, developer, and administrative details from Page 1 and Section 1."""

    model_config = ConfigDict(populate_by_name=True)

    report_number: int = Field(..., alias="reportNumber", description="Report sequence number (מספר דוח)")
    report_date: str = Field(..., alias="reportDate", description="Report date DD/MM/YYYY")
    total_units: int = Field(..., alias="totalUnits", description="Total housing units (יח\"ד)")
    address: str = Field(..., description="Project address")
    city: Optional[str] = Field(None, description="City name")
    developer_name: str = Field(..., alias="developerName", description="Developer/sponsor name (היזם)")
    developer_id: str = Field(..., alias="developerId", description="Company registration number (ח.פ.)")
    bank_account: Optional[str] = Field(None, alias="bankAccount", description="Escrow bank account number")
    bank_branch: Optional[str] = Field(None, alias="bankBranch", description="Bank branch number")
    supervisor: Optional[str] = Field(None, description="Site supervisor/inspector name")
    contractor_name: Optional[str] = Field(None, alias="contractorName", description="General contractor name")
    contractor_classification: Optional[str] = Field(
        None, alias="contractorClassification", description="Contractor classification (e.g. ג/5)"
    )
    construction_start: Optional[str] = Field(
        None, alias="constructionStart", description="Construction start date DD/MM/YYYY"
    )
    expected_completion: Optional[str] = Field(
        None, alias="expectedCompletion", description="Expected completion date DD/MM/YYYY"
    )
    permit_date: Optional[str] = Field(None, alias="permitDate", description="Building permit date DD/MM/YYYY")
    insurance_end: Optional[str] = Field(None, alias="insuranceEnd", description="Insurance policy expiry DD/MM/YYYY")
    insurance_value: Optional[int] = Field(None, alias="insuranceValue", description="Insurance coverage amount (NIS)")
    insurance_pledged: Optional[bool] = Field(
        None, alias="insurancePledged", description="Whether insurance is pledged to bank"
    )


class SalesPaceQuarter(BaseModel):
    """Quarterly sales pace entry: plan vs actual."""

    quarter: str = Field(..., description="Quarter label (e.g. Q1, Q2, מוקדמת)")
    plan: Optional[int] = Field(None, description="Planned sales for quarter")
    actual: Optional[int] = Field(None, description="Actual sales for quarter")


class SalesData(BaseModel):
    """Sales, inventory, and revenue data from Section 7 and Page 3."""

    model_config = ConfigDict(populate_by_name=True)

    total_value: Optional[int] = Field(None, alias="totalValue", description="Total project value incl. inventory (אלפי ₪)")
    sold_units: Optional[int] = Field(None, alias="soldUnits", description="Number of units sold")
    sold_value: Optional[int] = Field(None, alias="soldValue", description="Total value of sold units (אלפי ₪)")
    received_amount: Optional[int] = Field(
        None, alias="receivedAmount", description="Amount received from buyers (אלפי ₪)"
    )
    receivable_amount: Optional[int] = Field(
        None, alias="receivableAmount", description="Amount remaining to collect (אלפי ₪)"
    )
    inventory_units: Optional[int] = Field(None, alias="inventoryUnits", description="Unsold units in inventory")
    inventory_value: Optional[int] = Field(
        None, alias="inventoryValue", description="Value of unsold inventory (אלפי ₪)"
    )
    sales_this_period: Optional[int] = Field(
        None, alias="salesThisPeriod", description="New sales in this reporting period"
    )
    average_unit_value: Optional[int] = Field(
        None, alias="averageUnitValue", description="Average value per sold unit (אלפי ₪)"
    )
    non_linear_units: Optional[int] = Field(
        None, alias="nonLinearUnits", description="Units with non-linear payment schedule"
    )
    sales_pace: List[SalesPaceQuarter] = Field(
        default_factory=list, alias="salesPace", description="Quarterly sales pace: plan vs actual"
    )


class CostData(BaseModel):
    """Budget, paid, and remaining costs by category from Section 4 and Appendix A."""

    model_config = ConfigDict(populate_by_name=True)

    land_budget: Optional[int] = Field(None, alias="landBudget", description="Land cost budget (אלפי ₪)")
    land_paid: Optional[int] = Field(None, alias="landPaid", description="Land cost paid (אלפי ₪)")
    soft_costs_budget: Optional[int] = Field(
        None, alias="softCostsBudget", description="Soft costs budget - כלליות (אלפי ₪)"
    )
    soft_costs_paid: Optional[int] = Field(None, alias="softCostsPaid", description="Soft costs paid (אלפי ₪)")
    construction_budget: Optional[int] = Field(
        None, alias="constructionBudget", description="Construction budget - הקמה (אלפי ₪)"
    )
    construction_paid: Optional[int] = Field(
        None, alias="constructionPaid", description="Construction costs paid (אלפי ₪)"
    )
    total_budget: Optional[int] = Field(None, alias="totalBudget", description="Total project budget (אלפי ₪)")
    total_paid: Optional[int] = Field(None, alias="totalPaid", description="Total paid to date (אלפי ₪)")
    total_remaining: Optional[int] = Field(
        None, alias="totalRemaining", description="Total remaining to pay (אלפי ₪)"
    )
    report_zero_budget: Optional[int] = Field(
        None, alias="reportZeroBudget", description="Original budget from report zero (אלפי ₪)"
    )


class ProgressData(BaseModel):
    """Physical and financial construction progress from Section 5."""

    model_config = ConfigDict(populate_by_name=True)

    physical_progress_pct: Optional[float] = Field(
        None, alias="physicalProgressPct", description="Physical completion percentage"
    )
    financial_progress_pct: Optional[float] = Field(
        None, alias="financialProgressPct", description="Financial completion percentage"
    )
    physical_progress_value: Optional[int] = Field(
        None, alias="physicalProgressValue", description="Physical progress value (אלפי ₪)"
    )
    financial_progress_value: Optional[int] = Field(
        None, alias="financialProgressValue", description="Financial progress value (אלפי ₪)"
    )


class CreditData(BaseModel):
    """Credit utilization, guarantees, and equity position from Section 9."""

    model_config = ConfigDict(populate_by_name=True)

    credit_utilized: Optional[int] = Field(
        None, alias="creditUtilized", description="Current credit utilization (אלפי ₪)"
    )
    credit_limit: Optional[int] = Field(None, alias="creditLimit", description="Approved credit facility (אלפי ₪)")
    guarantee_balance: Optional[int] = Field(
        None, alias="guaranteeBalance", description="Outstanding sale-law guarantees (אלפי ₪)"
    )
    guarantee_limit: Optional[int] = Field(
        None, alias="guaranteeLimit", description="Approved guarantee facility (אלפי ₪)"
    )
    equity_required: Optional[int] = Field(None, alias="equityRequired", description="Required equity (אלפי ₪)")
    equity_current: Optional[int] = Field(None, alias="equityCurrent", description="Current equity (אלפי ₪)")
    equity_surplus: Optional[int] = Field(
        None, alias="equitySurplus", description="Equity surplus/(deficit) (אלפי ₪)"
    )
    max_credit_expected: Optional[int] = Field(
        None, alias="maxCreditExpected", description="Maximum expected credit drawdown (אלפי ₪)"
    )


class SurplusData(BaseModel):
    """Surplus calculations, extraction formula, and profitability from Sections 8, 9, 11."""

    model_config = ConfigDict(populate_by_name=True)

    deposits_balance: Optional[int] = Field(
        None, alias="depositsBalance", description="Deposits balance - פק\"מ (אלפי ₪)"
    )
    surplus_project: Optional[int] = Field(
        None, alias="surplusProject", description="Surplus for project (100% weights) (אלפי ₪)"
    )
    surplus_after_margins: Optional[int] = Field(
        None, alias="surplusAfterMargins", description="Surplus after margin adjustments (אלפי ₪)"
    )
    extraction_total: Optional[int] = Field(
        None, alias="extractionTotal", description="Extraction formula result (אלפי ₪)"
    )
    vat_balance: Optional[int] = Field(
        None, alias="vatBalance", description="VAT receivable/(payable) balance (אלפי ₪)"
    )
    profit_amount: Optional[int] = Field(None, alias="profitAmount", description="Profit amount (אלפי ₪)")
    profit_pct: Optional[float] = Field(None, alias="profitPct", description="Profit as percentage of costs")


class Footnote(BaseModel):
    """Source citation for an extracted data point."""

    number: int = Field(..., description="Sequential footnote number [1]-[N]")
    type: str = Field(..., description="source or calculation")
    reference: str = Field(..., description="Page/section reference or calculation formula")
    verified: bool = Field(True, description="Whether the reference was verified against report")


class MonitoringReportResult(BaseModel):
    """Complete structured extraction from a monitoring report (דוח מעקב)."""

    model_config = ConfigDict(populate_by_name=True)

    project_info: ProjectInfo = Field(..., alias="projectInfo", description="Project identification and details")
    sales_data: SalesData = Field(
        default_factory=SalesData, alias="salesData", description="Sales, inventory, and revenue data"
    )
    costs: CostData = Field(default_factory=CostData, description="Budget, paid, and remaining costs")
    progress: ProgressData = Field(default_factory=ProgressData, description="Physical and financial progress")
    credit_and_guarantees: CreditData = Field(
        default_factory=CreditData, alias="creditAndGuarantees", description="Credit, guarantees, and equity"
    )
    surplus_analysis: SurplusData = Field(
        default_factory=SurplusData, alias="surplusAnalysis", description="Surplus, extraction, and profitability"
    )
    notes: List[str] = Field(default_factory=list, description="Key notes and highlights from the report")
    footnotes: List[Footnote] = Field(default_factory=list, description="Source citations for every data point")
    validation_score: Optional[int] = Field(
        None, alias="validationScore", description="Data validation score 0-100"
    )
