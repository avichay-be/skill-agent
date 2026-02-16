"""Pydantic output model for Israeli zero-stage appraisal report extraction (דו"ח אפס)."""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ── Nested models for projectInfo ────────────────────────────────────────────


class ParcelDetail(BaseModel):
    """Land parcel with optional plot and area info."""

    model_config = ConfigDict(populate_by_name=True)

    parcel: Optional[str] = Field(None, description="חלקה number or identifier")
    plot: Optional[Union[int, str]] = Field(None, description="מגרש number")
    area: Optional[float] = Field(None, description="Area in sqm")


class TenderDetail(BaseModel):
    """Structured tender information."""

    model_config = ConfigDict(populate_by_name=True)

    tender_type: Optional[str] = Field(None, alias="tenderType", description="Type of tender (e.g. מכרז רמ\"י)")
    tender_year: Optional[int] = Field(None, alias="tenderYear", description="Tender year")
    tender_number: Optional[str] = Field(None, alias="tenderNumber", description="Tender number")
    winning_company: Optional[str] = Field(None, alias="winningCompany", description="Winning company name")


class ProjectInfo(BaseModel):
    """Project identification and key parameters."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., description="Project name in Hebrew")
    developer: str = Field(..., description="Developer/entrepreneur company")
    company_id: Optional[str] = Field(None, alias="companyId", description="ח.פ. registration number")
    contractor_license: Optional[str] = Field(None, alias="contractorLicense", description="Contractor license number")
    contractor_classification: Optional[str] = Field(None, alias="contractorClassification", description="e.g. ג/5 בלתי מוגבל")
    location: Optional[str] = Field(None, description="Neighborhood, city")
    block: Optional[Union[int, str]] = Field(None, description="גוש")
    parcels: Optional[Union[str, List[Union[str, int, ParcelDetail]]]] = Field(None, description="חלקות")
    plots: Optional[Union[str, int, List[Union[str, int]]]] = Field(None, description="מגרשים")
    land_area: Optional[float] = Field(None, alias="landArea", description="Total land area sqm")
    total_units: int = Field(..., alias="totalUnits", description="Total housing units")
    reduced_price_units: Optional[int] = Field(None, alias="reducedPriceUnits", description="מחיר מופחת/מטרה/למשתכן units")
    free_market_units: Optional[int] = Field(None, alias="freeMarketUnits", description="שוק חופשי units")
    buildings: Optional[Union[int, str]] = Field(None, description="Number of buildings")
    floors: Optional[Union[int, str]] = Field(None, description="Max floors above ground")
    report_date: str = Field(..., alias="reportDate", description="DD/MM/YYYY")
    report_status: Optional[str] = Field(None, alias="reportStatus", description="Report status in Hebrew")
    appraiser: Optional[str] = Field(None, description="Appraiser firm/person")
    tender: Optional[Union[str, TenderDetail]] = Field(None, description="Tender info (string or structured)")
    tender_area: Optional[Union[int, str]] = Field(None, alias="tenderArea", description="Precinct code")
    original_tender_units: Optional[int] = Field(None, alias="originalTenderUnits", description="Units in original tender")


# ── Financial Summary ────────────────────────────────────────────────────────


class FinancialSummary(BaseModel):
    """Project-level financial overview."""

    model_config = ConfigDict(populate_by_name=True)

    currency: str = Field("ILS", description="Currency code")
    excluding_vat: bool = Field(True, alias="excludingVAT", description="Values exclude VAT")
    total_revenue: int = Field(..., alias="totalRevenue", description="Total revenue ILS")
    reduced_price_revenue: Optional[int] = Field(None, alias="reducedPriceRevenue", description="Revenue from reduced price units")
    free_market_revenue: Optional[int] = Field(None, alias="freeMarketRevenue", description="Revenue from free market units")
    revenue_after_hedge: Optional[int] = Field(None, alias="revenueAfterHedge", description="Revenue after hedge/גידור")
    hedge_amount: Optional[int] = Field(None, alias="hedgeAmount", description="Hedge/reserve amount")
    total_expenses: int = Field(..., alias="totalExpenses", description="Total project expenses")
    profit: int = Field(..., description="Profit (revenue minus expenses)")
    profit_margin_revenue: Optional[float] = Field(None, alias="profitMarginRevenue", description="Profit as % of revenue")
    profit_margin_costs: Optional[float] = Field(None, alias="profitMarginCosts", description="Profit as % of costs")
    equity_required: Optional[int] = Field(None, alias="equityRequired", description="Equity required ILS")
    equity_percent: Optional[float] = Field(None, alias="equityPercent", description="Equity as % of expenses")
    loan_amount: Optional[int] = Field(None, alias="loanAmount", description="Loan amount ILS")
    max_exposure: Optional[int] = Field(None, alias="maxExposure", description="Max bank exposure ILS")
    max_exposure_month: Optional[int] = Field(None, alias="maxExposureMonth", description="Month of max exposure")
    interest_rate: Optional[float] = Field(None, alias="interestRate", description="Annual interest rate %")
    prime_rate: Optional[float] = Field(None, alias="primeRate", description="Prime rate %")
    spread: Optional[float] = Field(None, description="Spread over prime %")
    price_per_sqm: Optional[int] = Field(None, alias="pricePerSqm", description="Average ₪/sqm")
    avg_unit_price: Optional[int] = Field(None, alias="avgUnitPrice", description="Average unit price")


# ── Revenue by Track ─────────────────────────────────────────────────────────


class RevenueTrack(BaseModel):
    """Revenue breakdown per track/phase."""

    model_config = ConfigDict(populate_by_name=True)

    track_name: Optional[str] = Field(None, alias="trackName", description="Track name (מחיר מופחת/שוק חופשי/שלב א')")
    track: Optional[str] = Field(None, description="Alternative field for track name")
    units: int = Field(..., description="Number of units in track")
    total_revenue: int = Field(..., alias="totalRevenue", description="Track total revenue")
    avg_price_per_unit: Optional[int] = Field(None, alias="avgPricePerUnit", description="Average price per unit")
    price_per_sqm: Optional[int] = Field(None, alias="pricePerSqm", description="Price per sqm")


# ── Free Market Unit Mix ─────────────────────────────────────────────────────


class UnitMixEntry(BaseModel):
    """Unit mix breakdown by room count."""

    model_config = ConfigDict(populate_by_name=True)

    rooms: float = Field(..., description="Number of rooms")
    units: int = Field(..., description="Number of units")
    total_area: Optional[float] = Field(None, alias="totalArea", description="Total area sqm")
    equivalent_area: Optional[float] = Field(None, alias="equivalentArea", description="Weighted area for pricing")
    total_revenue: Optional[int] = Field(None, alias="totalRevenue", description="Total revenue for this type")
    avg_price_per_unit: Optional[int] = Field(None, alias="avgPricePerUnit", description="Average price per unit")
    price_per_sqm: Optional[int] = Field(None, alias="pricePerSqm", description="Price per sqm")


# ── Expense Breakdown ────────────────────────────────────────────────────────


class ExpenseCategory(BaseModel):
    """Expense category with subtotal and variable line items."""

    model_config = ConfigDict(populate_by_name=True)

    subtotal: Optional[int] = Field(None, description="Category subtotal ILS")
    items: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Line items (key: amount or {description, amount, ...})")


class ExpenseBreakdown(BaseModel):
    """Three-way expense breakdown: land, construction, additional."""

    model_config = ConfigDict(populate_by_name=True)

    land_and_development: Optional[ExpenseCategory] = Field(None, alias="landAndDevelopment", description="Land and development costs")
    construction: Optional[ExpenseCategory] = Field(None, description="Construction costs")
    additional_costs: Optional[ExpenseCategory] = Field(None, alias="additionalCosts", description="Additional costs")
    total_expenses: int = Field(..., alias="totalExpenses", description="Must equal sum of 3 subtotals")
    avg_cost_per_unit: Optional[int] = Field(None, alias="avgCostPerUnit", description="Average cost per unit")
    avg_cost_per_sqm: Optional[int] = Field(None, alias="avgCostPerSqm", description="Average cost per sqm")


# ── Built Areas ──────────────────────────────────────────────────────────────


class AreaDetail(BaseModel):
    """Named area with description and sqm value."""

    description: Optional[str] = Field(None, description="Area description in Hebrew")
    area: Optional[float] = Field(None, description="Area in sqm")


class BuiltAreas(BaseModel):
    """Project built area breakdown."""

    model_config = ConfigDict(populate_by_name=True)

    main_area: Optional[AreaDetail] = Field(None, alias="mainArea", description="Main residential area")
    residential_only: Optional[AreaDetail] = Field(None, alias="residentialOnly", description="Residential-only area")
    service_area_above_ground: Optional[AreaDetail] = Field(None, alias="serviceAreaAboveGround")
    service_area_below_ground: Optional[AreaDetail] = Field(None, alias="serviceAreaBelowGround")
    underground_parking: Optional[AreaDetail] = Field(None, alias="undergroundParking")
    storage: Optional[AreaDetail] = Field(None, description="Storage/מחסנים area")
    open_balconies: Optional[AreaDetail] = Field(None, alias="openBalconies")
    balconies_for_construction: Optional[AreaDetail] = Field(None, alias="balconiesForConstruction")
    safe_rooms: Optional[AreaDetail] = Field(None, alias="safeRooms", description="ממ\"ד")
    total_building_area: Optional[float] = Field(None, alias="totalBuildingArea")
    total_above_ground: Optional[float] = Field(None, alias="totalAboveGround")
    total_below_ground: Optional[float] = Field(None, alias="totalBelowGround")


# ── Unit Mix by Floor ────────────────────────────────────────────────────────


class FloorMixEntry(BaseModel):
    """Unit distribution per floor."""

    model_config = ConfigDict(populate_by_name=True)

    floor: Optional[str] = Field(None, description="Floor name in Hebrew")
    floor_number: Optional[int] = Field(None, alias="floorNumber")
    units: int = Field(..., description="Units on this floor")
    residential_area: Optional[float] = Field(None, alias="residentialArea", description="Residential area sqm")
    avg_area_per_unit: Optional[float] = Field(None, alias="avgAreaPerUnit")


# ── Break-Even Analysis ──────────────────────────────────────────────────────


class BreakEvenAnalysis(BaseModel):
    """Break-even point analysis."""

    model_config = ConfigDict(populate_by_name=True)

    units_required: Optional[int] = Field(None, alias="unitsRequired", description="Units needed to break even")
    percent_required: Optional[float] = Field(None, alias="percentRequired", description="% of total units")
    avg_price_reduced_price: Optional[int] = Field(None, alias="avgPriceReducedPrice")
    avg_price_free_market: Optional[int] = Field(None, alias="avgPriceFreeMarket")
    avg_price_total: Optional[int] = Field(None, alias="avgPriceTotal")
    price_per_sqm_reduced_price: Optional[int] = Field(None, alias="pricePerSqmReducedPrice")
    price_per_sqm_free_market: Optional[int] = Field(None, alias="pricePerSqmFreeMarket")
    discount_at_break_even: Optional[float] = Field(None, alias="discountAtBreakEven", description="Max discount %")
    avg_price_at_break_even: Optional[int] = Field(None, alias="avgPriceAtBreakEven")


# ── Sensitivity Analysis ─────────────────────────────────────────────────────


class ProfitByCostLevel(BaseModel):
    """Profit amounts at different cost multiplier levels."""

    model_config = ConfigDict(populate_by_name=True)

    cost100: Optional[int] = Field(None)
    cost105: Optional[int] = Field(None)
    cost110: Optional[int] = Field(None)
    cost115: Optional[int] = Field(None)


class SensitivityRow(BaseModel):
    """One row of the sensitivity profit matrix."""

    model_config = ConfigDict(populate_by_name=True)

    revenue_level: str = Field(..., alias="revenueLevel", description="e.g. -5%")
    revenue_amount: Optional[int] = Field(None, alias="revenueAmount")
    profit_by_cost_level: Optional[ProfitByCostLevel] = Field(None, alias="profitByCostLevel")


class MarginByCostLevel(BaseModel):
    """Profit margin % at different cost multiplier levels."""

    model_config = ConfigDict(populate_by_name=True)

    cost100: Optional[float] = Field(None)
    cost105: Optional[float] = Field(None)
    cost110: Optional[float] = Field(None)
    cost115: Optional[float] = Field(None)


class SensitivityMarginRow(BaseModel):
    """One row of the sensitivity margin matrix."""

    model_config = ConfigDict(populate_by_name=True)

    revenue_level: str = Field(..., alias="revenueLevel")
    margin_by_cost_level: Optional[MarginByCostLevel] = Field(None, alias="marginByCostLevel")


class BaseCosts(BaseModel):
    """Base costs for sensitivity analysis (land fixed, construction variable)."""

    model_config = ConfigDict(populate_by_name=True)

    land_fixed: Optional[int] = Field(None, alias="landFixed", description="Land cost held fixed")
    construction_variable: Optional[int] = Field(None, alias="constructionVariable", description="Variable construction cost")
    total: Optional[int] = Field(None)


class SensitivityAnalysis(BaseModel):
    """Sensitivity analysis: revenue × cost → profit matrix."""

    model_config = ConfigDict(populate_by_name=True)

    revenue_change_levels: Optional[List[str]] = Field(default_factory=list, alias="revenueChangeLevels")
    cost_change_levels: Optional[List[str]] = Field(default_factory=list, alias="costChangeLevels")
    note: Optional[str] = Field(None)
    base_costs: Optional[BaseCosts] = Field(None, alias="baseCosts")
    revenue_amounts: Optional[Dict[str, int]] = Field(default_factory=dict, alias="revenueAmounts")
    cost_amounts: Optional[Dict[str, int]] = Field(default_factory=dict, alias="costAmounts")
    profit_matrix: Optional[List[SensitivityRow]] = Field(default_factory=list, alias="profitMatrix")
    profit_margin_matrix: Optional[List[SensitivityMarginRow]] = Field(default_factory=list, alias="profitMarginMatrix")


# ── Timeline ─────────────────────────────────────────────────────────────────


class Milestone(BaseModel):
    """Project milestone with date and status."""

    model_config = ConfigDict(populate_by_name=True)

    date: Optional[str] = Field(None, description="DD/MM/YYYY or MM/YYYY")
    milestone: Optional[str] = Field(None, description="Event description in Hebrew")
    name: Optional[str] = Field(None, description="Alternative field for milestone name")
    event: Optional[str] = Field(None, description="Alternative field for event description")
    status: Optional[str] = Field(None, description="completed|warning|pending")
    due_date: Optional[str] = Field(None, alias="dueDate")


class Timeline(BaseModel):
    """Construction timeline with milestones."""

    model_config = ConfigDict(populate_by_name=True)

    construction_duration: Optional[Union[int, str]] = Field(None, alias="constructionDuration", description="Total months")
    construction_duration_months: Optional[str] = Field(None, alias="constructionDurationMonths", description="Hebrew description")
    expected_permit_date: Optional[str] = Field(None, alias="expectedPermitDate")
    expected_completion_date: Optional[str] = Field(None, alias="expectedCompletionDate")
    expected_construction_start: Optional[str] = Field(None, alias="expectedConstructionStart")
    milestones: List[Milestone] = Field(default_factory=list, description="Project milestones")


# ── Legal Info ───────────────────────────────────────────────────────────────


class TenderWin(BaseModel):
    """Tender win details."""

    model_config = ConfigDict(populate_by_name=True)

    date: Optional[str] = Field(None, description="Win date")
    win_date: Optional[str] = Field(None, alias="winDate")
    year: Optional[int] = Field(None)
    tender_number: Optional[str] = Field(None, alias="tenderNumber")
    price_per_sqm: Optional[int] = Field(None, alias="pricePerSqm")
    original_units: Optional[int] = Field(None, alias="originalUnits")
    original_mix: Optional[str] = Field(None, alias="originalMix")
    actual_mix: Optional[str] = Field(None, alias="actualMix")
    winner: Optional[str] = Field(None)
    original_winner: Optional[str] = Field(None, alias="originalWinner")
    winning_company: Optional[str] = Field(None, alias="winningCompany")
    current_holder: Optional[str] = Field(None, alias="currentHolder")
    consideration: Optional[int] = Field(None)
    acquisition_amount: Optional[int] = Field(None, alias="acquisitionAmount")
    acquisition_date: Optional[str] = Field(None, alias="acquisitionDate")


class MortgageEntry(BaseModel):
    """Mortgage lien recorded at רמ\"י."""

    model_config = ConfigDict(populate_by_name=True)

    mortgage_number: Optional[str] = Field(None, alias="mortgageNumber")
    mortgage_date: Optional[str] = Field(None, alias="mortgageDate")
    bank: Optional[str] = Field(None)


class LienEntry(BaseModel):
    """Tax or governmental lien."""

    model_config = ConfigDict(populate_by_name=True)

    lien_number: Optional[str] = Field(None, alias="lienNumber")
    lien_date: Optional[str] = Field(None, alias="lienDate")
    authority: Optional[str] = Field(None)
    reason: Optional[str] = Field(None)


class Leaseholder(BaseModel):
    """Leaseholder name and share."""

    name: Optional[str] = Field(None)
    share: Optional[str] = Field(None)


class LeaseAgreement(BaseModel):
    """Land lease agreement details."""

    model_config = ConfigDict(populate_by_name=True)

    date: Optional[str] = Field(None)
    sign_date: Optional[str] = Field(None, alias="signDate")
    type: Optional[str] = Field(None, description="e.g. חוזה חכירה מהוון")
    name: Optional[str] = Field(None, description="Agreement name/type")
    duration: Optional[int] = Field(None, description="Years")
    additional_duration: Optional[int] = Field(None, alias="additionalDuration")
    start_date: Optional[str] = Field(None, alias="startDate")
    end_date: Optional[str] = Field(None, alias="endDate")
    lease_period_end: Optional[str] = Field(None, alias="leasePeriodEnd")
    total_payment: Optional[int] = Field(None, alias="totalPayment")
    value: Optional[int] = Field(None, description="Lease/contract value")
    base_value: Optional[int] = Field(None, alias="baseValue")
    payment_per_unit: Optional[int] = Field(None, alias="paymentPerUnit")
    total_land_area: Optional[float] = Field(None, alias="totalLandArea")
    ila_file_number: Optional[str] = Field(None, alias="ilaFileNumber")
    ila_account_number: Optional[str] = Field(None, alias="ilaAccountNumber")
    development_period_end: Optional[str] = Field(None, alias="developmentPeriodEnd")
    lessee: Optional[str] = Field(None)
    lessor: Optional[str] = Field(None)
    completion_deadline: Optional[str] = Field(None, alias="completionDeadline")
    land_value: Optional[int] = Field(None, alias="landValue")
    development_expenses: Optional[int] = Field(None, alias="developmentExpenses")
    signers_count: Optional[int] = Field(None, alias="signersCount")
    total_diers_count: Optional[int] = Field(None, alias="totalDiersCount")
    status: Optional[str] = Field(None)
    mortgages: Optional[List[MortgageEntry]] = Field(default_factory=list)
    liens: Optional[List[LienEntry]] = Field(default_factory=list)
    leaseeholders: Optional[List[Union[str, Leaseholder]]] = Field(default_factory=list)


class DevelopmentContract(BaseModel):
    """Development contract details."""

    model_config = ConfigDict(populate_by_name=True)

    date: Optional[str] = Field(None)
    contractor: Optional[str] = Field(None)
    development_period: Optional[int] = Field(None, alias="developmentPeriod", description="Months")
    total_payment: Optional[int] = Field(None, alias="totalPayment")


class GuaranteeEntry(BaseModel):
    """Bank guarantee details."""

    model_config = ConfigDict(populate_by_name=True)

    type: Optional[str] = Field(None)
    bank: Optional[str] = Field(None)
    amount: Optional[int] = Field(None)
    bank_guarantee: Optional[int] = Field(None, alias="bankGuarantee")
    guarantee_type: Optional[str] = Field(None, alias="guaranteeType")
    guarantee_percentage: Optional[float] = Field(None, alias="guaranteePercentage")
    guarantee_per_unit: Optional[int] = Field(None, alias="guaranteePerUnit")
    guarantee_amount: Optional[int] = Field(None, alias="guaranteeAmount")
    valid_until: Optional[str] = Field(None, alias="validUntil")
    index_base: Optional[Union[str, float]] = Field(None, alias="indexBase")


class Ownership(BaseModel):
    """Land ownership information."""

    model_config = ConfigDict(populate_by_name=True)

    type: Optional[str] = Field(None)
    registered_owners: Optional[List[str]] = Field(default_factory=list, alias="registeredOwners")
    restrictions: Optional[str] = Field(None)


class Supervision(BaseModel):
    """Project supervision details."""

    company: Optional[str] = Field(None)
    ministry: Optional[str] = Field(None)
    status: Optional[str] = Field(None)


class PermitEntry(BaseModel):
    """Building permit per plot."""

    model_config = ConfigDict(populate_by_name=True)

    plot: Optional[Union[int, str]] = Field(None)
    permit_number: Optional[str] = Field(None, alias="permitNumber")
    buildings: Optional[int] = Field(None)
    units: Optional[int] = Field(None)
    decision: Optional[str] = Field(None)
    decision_date: Optional[str] = Field(None, alias="decisionDate")


class OtherLegalInfo(BaseModel):
    """Plans and permits."""

    model_config = ConfigDict(populate_by_name=True)

    original_plan: Optional[str] = Field(None, alias="originalPlan")
    new_plan: Optional[str] = Field(None, alias="newPlan")
    plan_approval_date: Optional[str] = Field(None, alias="planApprovalDate")
    permits: Optional[List[PermitEntry]] = Field(default_factory=list)


class LegalInfo(BaseModel):
    """Legal background: tender, lease, guarantees, ownership."""

    model_config = ConfigDict(populate_by_name=True)

    tender_win: Optional[TenderWin] = Field(None, alias="tenderWin")
    tender_win_details: Optional[TenderWin] = Field(None, alias="tenderWinDetails")
    lease_agreement: Optional[LeaseAgreement] = Field(None, alias="leaseAgreement")
    development_contract: Optional[DevelopmentContract] = Field(None, alias="developmentContract")
    guarantees: Optional[Union[List[GuaranteeEntry], GuaranteeEntry]] = Field(None)
    ownership: Optional[Union[str, Ownership]] = Field(None)
    supervision: Optional[Union[str, Supervision]] = Field(None)
    other_legal_info: Optional[OtherLegalInfo] = Field(None, alias="otherLegalInfo")


# ── Planning Info ────────────────────────────────────────────────────────────


class MasterPlan(BaseModel):
    """Zoning/master plan details."""

    model_config = ConfigDict(populate_by_name=True)

    number: Optional[str] = Field(None)
    name: Optional[str] = Field(None)
    type: Optional[str] = Field(None)
    approval_date: Optional[str] = Field(None, alias="approvalDate")
    gazette_number: Optional[str] = Field(None, alias="gazetteNumber")
    initiator: Optional[str] = Field(None)
    total_area: Optional[float] = Field(None, alias="totalArea")
    purpose: Optional[str] = Field(None)


class Setbacks(BaseModel):
    """Building setback requirements."""

    model_config = ConfigDict(populate_by_name=True)

    front: Optional[float] = Field(None)
    rear: Optional[float] = Field(None)
    right_side: Optional[float] = Field(None, alias="rightSide")
    left_side: Optional[float] = Field(None, alias="leftSide")


class BuildingRights(BaseModel):
    """Permitted building rights."""

    model_config = ConfigDict(populate_by_name=True)

    designation: Optional[str] = Field(None, description="e.g. מגורים ג")
    plot_size: Optional[float] = Field(None, alias="plotSize")
    main_area_above_ground: Optional[Union[str, float]] = Field(None, alias="mainAreaAboveGround")
    service_area_above_ground: Optional[Union[str, float]] = Field(None, alias="serviceAreaAboveGround")
    service_area_below_ground: Optional[Union[str, float]] = Field(None, alias="serviceAreaBelowGround")
    coverage_percent: Optional[float] = Field(None, alias="coveragePercent")
    units: Optional[int] = Field(None)
    max_height: Optional[float] = Field(None, alias="maxHeight", description="Meters")
    floors_above_ground: Optional[int] = Field(None, alias="floorsAboveGround")
    floors_below_ground: Optional[int] = Field(None, alias="floorsBelowGround")
    setbacks: Optional[Setbacks] = Field(None)


class CommitteeApproval(BaseModel):
    """Planning committee approval."""

    model_config = ConfigDict(populate_by_name=True)

    date: Optional[str] = Field(None)
    session_number: Optional[str] = Field(None, alias="sessionNumber")
    approved_units: Optional[int] = Field(None, alias="approvedUnits")
    permit_status: Optional[str] = Field(None, alias="permitStatus")


class ParkingStandard(BaseModel):
    """Parking space requirements."""

    model_config = ConfigDict(populate_by_name=True)

    up_to_120sqm: Optional[float] = Field(None, alias="upTo120sqm")
    above_120sqm: Optional[float] = Field(None, alias="above120sqm")


class PlanningInfo(BaseModel):
    """Planning background: plans, rights, approvals."""

    model_config = ConfigDict(populate_by_name=True)

    master_plans: Optional[List[MasterPlan]] = Field(default_factory=list, alias="masterPlans")
    building_rights: Optional[BuildingRights] = Field(None, alias="buildingRights")
    committee_approval: Optional[CommitteeApproval] = Field(None, alias="committeeApproval")
    parking_standard: Optional[ParkingStandard] = Field(None, alias="parkingStandard")


# ── Consultants ──────────────────────────────────────────────────────────────


class Consultant(BaseModel):
    """Project consultant with role."""

    role: str = Field(..., description="Role in Hebrew (e.g. אדריכלות, קונסטרוקציה)")
    name: str = Field(..., description="Consultant name")


# ── Market Comparables ───────────────────────────────────────────────────────


class PriceRange(BaseModel):
    """Min/max/average price range."""

    min: Optional[int] = Field(None)
    max: Optional[int] = Field(None)
    average: Optional[int] = Field(None)


class RoomAverage(BaseModel):
    """Average price by room count."""

    average: Optional[int] = Field(None)
    count: Optional[int] = Field(None)


class Transaction(BaseModel):
    """Comparable market transaction."""

    model_config = ConfigDict(populate_by_name=True)

    parcel: Optional[str] = Field(None)
    date: Optional[str] = Field(None)
    price: Optional[int] = Field(None)
    area: Optional[float] = Field(None)
    rooms: Optional[float] = Field(None)
    year_built: Optional[int] = Field(None, alias="yearBuilt")
    price_per_sqm: Optional[int] = Field(None, alias="pricePerSqm")


class MarketComparables(BaseModel):
    """Market survey: comparable transactions in the area."""

    model_config = ConfigDict(populate_by_name=True)

    source: Optional[str] = Field(None, description="Data source")
    block: Optional[Union[int, str]] = Field(None)
    search_period: Optional[str] = Field(None, alias="searchPeriod")
    total_transactions: Optional[int] = Field(None, alias="totalTransactions")
    price_range: Optional[PriceRange] = Field(None, alias="priceRange")
    average_by_rooms: Optional[Dict[str, Union[int, RoomAverage]]] = Field(default_factory=dict, alias="averageByRooms")
    transactions: Optional[List[Transaction]] = Field(default_factory=list)


# ── Risks ────────────────────────────────────────────────────────────────────


class Risk(BaseModel):
    """Project risk assessment entry."""

    id: Optional[Union[int, str]] = Field(None)
    level: str = Field(..., description="high|medium|low")
    category: Optional[str] = Field(None, description="Risk category (Hebrew or English)")
    title: str = Field(..., description="Risk title in Hebrew")
    description: str = Field(..., description="Risk description in Hebrew")
    mitigation: Optional[str] = Field(None, description="Resolution strategy")
    impact: Optional[str] = Field(None)


# ── Sales Strategy ───────────────────────────────────────────────────────────


class PreSales(BaseModel):
    """Pre-sale requirements by track."""

    model_config = ConfigDict(populate_by_name=True)

    reduced_price: Optional[int] = Field(None, alias="reducedPrice")
    free_market: Optional[int] = Field(None, alias="freeMarket")
    total: Optional[int] = Field(None)


class TargetAudience(BaseModel):
    """Target audience descriptions."""

    model_config = ConfigDict(populate_by_name=True)

    reduced_price: Optional[str] = Field(None, alias="reducedPrice")
    free_market: Optional[str] = Field(None, alias="freeMarket")


class PricingCoefficients(BaseModel):
    """Area-type pricing coefficients."""

    model_config = ConfigDict(populate_by_name=True)

    main_area: Optional[float] = Field(None, alias="mainArea")
    garden: Optional[float] = Field(None)
    balcony: Optional[float] = Field(None)
    storage: Optional[float] = Field(None)
    parking: Optional[float] = Field(None)


class SalesStrategy(BaseModel):
    """Sales strategy and pricing approach."""

    model_config = ConfigDict(populate_by_name=True)

    pre_sales: Optional[PreSales] = Field(None, alias="preSales")
    target_audience: Optional[TargetAudience] = Field(None, alias="targetAudience")
    pricing_coefficients: Optional[PricingCoefficients] = Field(None, alias="pricingCoefficients")
    market_trend: Optional[str] = Field(None, alias="marketTrend")


# ── Neighborhood Info ────────────────────────────────────────────────────────


class NeighborhoodInfo(BaseModel):
    """Neighborhood/area context."""

    model_config = ConfigDict(populate_by_name=True)

    name: Optional[str] = Field(None)
    city: Optional[str] = Field(None)
    location: Optional[str] = Field(None)
    phase1_units: Optional[int] = Field(None, alias="phase1Units")
    total_planned_units: Optional[int] = Field(None, alias="totalPlannedUnits")
    built_complexes: Optional[int] = Field(None, alias="builtComplexes")
    built_units: Optional[int] = Field(None, alias="builtUnits")
    max_floors: Optional[str] = Field(None, alias="maxFloors")
    infrastructure: Optional[str] = Field(None)
    socioeconomic_level: Optional[str] = Field(None, alias="socioeconomicLevel")
    main_population: Optional[str] = Field(None, alias="mainPopulation")
    land_availability: Optional[str] = Field(None, alias="landAvailability")


# ── Indices ──────────────────────────────────────────────────────────────────


class IndexValue(BaseModel):
    """Economic index snapshot."""

    date: Optional[str] = Field(None)
    value: Optional[float] = Field(None)


class Indices(BaseModel):
    """Economic indices referenced in the report."""

    model_config = ConfigDict(populate_by_name=True)

    construction_input_index: Optional[IndexValue] = Field(None, alias="constructionInputIndex")
    consumer_price_index: Optional[IndexValue] = Field(None, alias="consumerPriceIndex")


# ── Metadata ─────────────────────────────────────────────────────────────────


class BankContact(BaseModel):
    """Bank contact person."""

    name: Optional[str] = Field(None)
    role: Optional[str] = Field(None)


class ReportMetadata(BaseModel):
    """Report metadata and provenance."""

    model_config = ConfigDict(populate_by_name=True)

    report_prepared_by: Optional[str] = Field(None, alias="reportPreparedBy")
    qualification: Optional[str] = Field(None)
    report_number: Optional[str] = Field(None, alias="reportNumber")
    bank_recipient: Optional[Union[str, List[str]]] = Field(None, alias="bankRecipient")
    bank_branch: Optional[str] = Field(None, alias="bankBranch")
    bank_address: Optional[str] = Field(None, alias="bankAddress")
    bank_contacts: Optional[List[Union[str, BankContact]]] = Field(default_factory=list, alias="bankContacts")
    report_date: Optional[str] = Field(None, alias="reportDate")
    visit_date: Optional[str] = Field(None, alias="visitDate")
    site_visit_date: Optional[str] = Field(None, alias="siteVisitDate")
    data_source_date: Optional[str] = Field(None, alias="dataSourceDate")
    vat_rate: Optional[float] = Field(None, alias="vatRate")
    currency: str = Field("ILS")
    excludes_vat: bool = Field(True, alias="excludesVAT")
    indexed_to: Optional[str] = Field(None, alias="indexedTo")
    revision_note: Optional[str] = Field(None, alias="revisionNote")
    prepared_for: Optional[str] = Field(None, alias="preparedFor")
    report_copy: Optional[str] = Field(None, alias="reportCopy")
    report_type: Optional[str] = Field(None, alias="reportType")
    report_conditions: Optional[str] = Field(None, alias="reportConditions")
    phase_count: Optional[int] = Field(None, alias="phaseCount")
    phase1_units: Optional[int] = Field(None, alias="phase1Units")
    phase2_units: Optional[int] = Field(None, alias="phase2Units")
    dwelling_types: Optional[List[Union[str, Dict[str, Any]]]] = Field(default_factory=list, alias="dwellingTypes")
    previous_report_date: Optional[str] = Field(None, alias="previousReportDate")
    previous_report_ref: Optional[str] = Field(None, alias="previousReportRef")
    visited_by: Optional[str] = Field(None, alias="visitedBy")


# ── Validation Notes ─────────────────────────────────────────────────────────


class ValidationNotes(BaseModel):
    """Cross-validation results for audit trail."""

    model_config = ConfigDict(populate_by_name=True)

    revenue_minus_expenses_equals_profit: Optional[bool] = Field(None, alias="revenueMinusExpensesEqualsProfit")
    calculated_profit: Optional[int] = Field(None, alias="calculatedProfit")
    reported_profit: Optional[int] = Field(None, alias="reportedProfit")
    revenue: Optional[int] = Field(None, description="Revenue used for calc (may be revenueAfterHedge)")
    expenses: Optional[int] = Field(None)
    variance: Optional[int] = Field(None, description="Difference between calculated and reported")
    calculation: Optional[str] = Field(None, description="Human-readable calculation string")
    validation_note: Optional[str] = Field(None, alias="validationNote")


# ═══════════════════════════════════════════════════════════════════════════════
# TOP-LEVEL MODEL
# ═══════════════════════════════════════════════════════════════════════════════


class DoachEfesResult(BaseModel):
    """Top-level extraction result for Israeli zero-stage appraisal reports (דו\"ח אפס)."""

    model_config = ConfigDict(populate_by_name=True)

    # Required sections
    project_info: ProjectInfo = Field(..., alias="projectInfo", description="Project identification")
    financial_summary: Optional[FinancialSummary] = Field(None, alias="financialSummary", description="Financial overview")
    revenue_by_track: List[RevenueTrack] = Field(default_factory=list, alias="revenueByTrack", description="Revenue by track/phase")
    expense_breakdown: Optional[ExpenseBreakdown] = Field(None, alias="expenseBreakdown", description="Three-way expense breakdown")
    risks: List[Risk] = Field(default_factory=list, description="Risk assessment entries")

    # Optional sections
    free_market_unit_mix: Optional[List[UnitMixEntry]] = Field(default_factory=list, alias="freeMarketUnitMix")
    built_areas: Optional[BuiltAreas] = Field(None, alias="builtAreas")
    unit_mix_by_floor: Optional[List[FloorMixEntry]] = Field(default_factory=list, alias="unitMixByFloor")
    break_even_analysis: Optional[BreakEvenAnalysis] = Field(None, alias="breakEvenAnalysis")
    sensitivity_analysis: Optional[SensitivityAnalysis] = Field(None, alias="sensitivityAnalysis")
    timeline: Optional[Timeline] = Field(None, description="Construction timeline")
    legal_info: Optional[LegalInfo] = Field(None, alias="legalInfo")
    planning_info: Optional[PlanningInfo] = Field(None, alias="planningInfo")
    consultants: Optional[List[Consultant]] = Field(default_factory=list)
    market_comparables: Optional[MarketComparables] = Field(None, alias="marketComparables")
    assumptions: Optional[List[str]] = Field(default_factory=list)
    sales_strategy: Optional[SalesStrategy] = Field(None, alias="salesStrategy")
    neighborhood_info: Optional[NeighborhoodInfo] = Field(None, alias="neighborhoodInfo")
    indices: Optional[Indices] = Field(None)
    disclaimers: Optional[List[str]] = Field(default_factory=list)
    metadata: Optional[ReportMetadata] = Field(None)
    validation_notes: Optional[ValidationNotes] = Field(None, alias="validationNotes")
