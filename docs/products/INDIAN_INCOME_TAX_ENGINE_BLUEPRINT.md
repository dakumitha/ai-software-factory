# Product Blueprint: Indian Income-tax Computation Engine

**Status:** proposed product architecture; no tax calculation capability is claimed by this document.
**Product objective:** deterministic, auditable Indian income-tax engine covering AY 2007-08 onward under the Income-tax Act, 1961 and Tax Year 2026-27 onward under the Income-tax Act, 2025.
**Budget:** ₹0 / US$0 default. No paid model/API/cloud dependency.

## 1. Scope and terminology

The requested starting point "2007-07" is interpreted provisionally as **AY 2007-08** (income period FY 2006-07). Confirm this before finalizing the year catalogue.

The engine must calculate and explain:
- income under applicable heads and total income;
- normal-rate and special-rate tax;
- rebates, reliefs, surcharge, marginal relief, cess, AMT/MAT where applicable;
- interest under applicable statutory provisions;
- statutory fees and penalties where quantifiable;
- prepaid taxes, credits, balance tax/refund and rounding;
- year-specific ITR eligibility, schedules, validation and output mapping for ITR-1 through ITR-7.

ITR form selection is a year-specific reporting/eligibility layer. It must not determine or constrain the underlying tax-law calculation model. ITR-1 to ITR-7 cover different categories and eligibility conditions, which change over time.

Penalty support must distinguish arithmetic calculation from legal applicability, statutory conditions, discretion, reasonable-cause defences, notice/hearing, limitation and procedural validity. The engine must never automatically conclude that a penalty is legally leviable merely because an amount can be calculated.

## 2. Dual-law timeline

### Legacy regime
- Income-tax Act, 1961 applies to income periods beginning before 1 April 2026.
- Preserve AY terminology and the applicable Finance Act, Rules, notifications and forms for each historical year.
- AY 2026-27 (FY 2025-26) remains governed by the 1961 Act.

### New regime
- Income-tax Act, 2025 and Income-tax Rules, 2026 came into force on 1 April 2026.
- Use Tax Year terminology for FY 2026-27 onward; do not fabricate an AY for this regime.
- Build a separate ruleset and form/schema adapter for the new Act.
- Transitional and savings provisions must preserve old-law treatment for earlier periods and pending proceedings.

The application must resolve and store the correct legal period and governing Act. A simple AY-to-TY rename is not sufficient. Each computation stores the statute version, effective dates, source documents and transition basis.

## 3. Core architecture

    User / Assessment Case
           |
           v
    Fact Intake + Source Documents
           |
           v
    Canonical Tax Data Model
           |
           +--> Period / Act / assessee / regime resolver
           |
           v
    Versioned Legal Rules Registry
           |
           v
    Income Computation Pipeline
           |
           v
    Tax + Interest + Fee + Penalty Engines
           |
           v
    Credits / Payments / Demand / Refund Reconciliation
           |
           v
    ITR-1 ... ITR-7 / historical form adapter
           |
           v
    Explainable Computation Report + Audit Evidence

    Official Excel Utility Lab
      -> safe archive intake -> workbook/formula/VBA/schema extraction
      -> versioned reference fixtures -> differential tests against engine

### Recommended implementation stack
- Core computation: Python 3.11+; deterministic, typed, decimal-based calculation modules.
- API: FastAPI, optional until a stable core exists.
- Initial persistence: SQLite for local-first prototype; PostgreSQL only when multi-user deployment is genuinely needed.
- Frontend: React/TypeScript responsive web UI, mobile usable.
- Workbook inspection: openpyxl for workbook structure/formulas/named ranges; separate safe VBA extraction tooling for macro-enabled files; archive/hash manifest.
- Excel execution: use official Microsoft Excel automation only if a properly licensed Excel installation is already available. Do not assume LibreOffice reproduces Excel/VBA behaviour.
- Tests: unittest/pytest, golden fixtures, differential tests, property-based tests where useful.
- No LLM call is allowed inside the numeric calculation path. AI may assist with research, extraction review and drafting, but cannot supply runtime tax amounts or override approved rules.

## 4. Canonical data model

Model source facts separately from derived amounts.

Core entities:
- Taxpayer: legal person type, residential status, age/date-of-birth facts, jurisdiction and relevant elections.
- TaxPeriod: FY/AY or Tax Year, start/end dates, governing Act, Finance Act / rate schedule, rule version.
- ReturnProfile: ITR form and version, filing section/type, due date, original/revised/updated/defective status.
- IncomeFact: head, source, gross amount, dates, evidence reference, TDS/TCS and tax character.
- DeductionClaim / ExemptionClaim / LossCarryForward: provision, amount, eligibility facts, cap, evidence and year.
- TaxPayment: advance tax, TDS, TCS, self-assessment tax, refund and challan allocation.
- LegalRule: provision, sub-provision, effective interval, assessee scope, predicates, formula, cap/floor, rounding, source citation and review status.
- ComputationRun: immutable input snapshot, ruleset versions, outputs, trace and reproducibility hash.
- ReviewDecision: reviewer, issue, reason, evidence and timestamp.

All monetary calculations use decimal arithmetic and explicit statutory rounding. Do not use binary floating-point for tax money.

## 5. Calculation modules

### A. Income
1. Salary.
2. Income from house property.
3. Profits and gains of business or profession.
4. Capital gains, including asset type, holding period, cost/indexation rules and special transitional provisions.
5. Income from other sources.
6. Exempt income and agricultural income integration where applicable.
7. Clubbing, set-off and carry-forward of losses.
8. Chapter VI-A and other deductions.
9. Special income and special-rate provisions.
10. AMT/MAT and applicable credits.

Every rule is period-specific. A section number or rate must never be assumed to apply unchanged across the entire 2007-to-present range.

### B. Tax
- Entity/person-type-specific normal rates.
- Special rates and income-character-specific calculations.
- Old/new regime choices where available for the relevant year.
- Rebate, surcharge, marginal relief and cess.
- Reliefs, credits and tax already paid.
- Rounding and final payable/refundable amount.

### C. Interest and fees
Implement each provision as its own rule module, not a single generic interest formula. Initial candidates include sections 234A, 234B, 234C, 234D, 220(2), and statutory fees such as 234F, subject to period applicability and exact statutory conditions. Add other provisions only after source verification.

Each interest result must show:
- principal base;
- rate and statutory source;
- start/end dates and month-count convention;
- instalment/payment adjustments;
- rounding stage;
- calculation trace and exceptions.

### D. Penalties
Create provision-specific modules, including historical provisions and successor provisions where applicable. Each result has two separate statuses:
- AMOUNT_COMPUTABLE: arithmetic can be calculated from facts and approved parameters.
- LEGAL_APPLICABILITY_REVIEW_REQUIRED: statutory predicates, discretion, defences and procedure need legal review.

Do not convert a calculated maximum/minimum into a conclusion that penalty should be imposed. Store satisfaction notes, notice/hearing chronology, limitation checks and reasoned decisions separately.

## 6. Official Excel Utility Lab

The official Income Tax Department Excel utilities are a primary **reference implementation and differential-testing source**, not the ultimate legal authority. The Act, Finance Acts, Rules, notified forms, notifications and binding judicial decisions govern legal interpretation.

For every downloaded official utility:
1. Record source URL, AY/TY, ITR form, release/version/date, download date, archive SHA-256 and licence/usage notes.
2. Preserve the original archive unchanged in a read-only evidence store.
3. Inventory archive contents, workbook sheets, hidden sheets/rows/columns, named ranges, formulas, data validation, tables, external links and macros.
4. Extract formula text and VBA source safely for human review. Never execute untrusted macros or workbook code automatically.
5. Record all formula dependencies and lookup/parameter tables.
6. Compare changes between utility releases and between assessment years.
7. Convert validated formulas and parameters into reviewed, versioned rule specifications with source links and effective dates.
8. Create input/output fixtures for each important formula and compare engine results with the official utility.
9. Record differences, explain intentional differences, and block certification when unexplained differences remain.

Important limitations:
- A formula extractor does not evaluate formulas.
- openpyxl reads formula expressions but does not calculate them.
- Excel VBA and macro behaviour may require genuine Microsoft Excel; LibreOffice is not assumed equivalent.
- Missing historical ITR/form utilities must be recorded as missing; never infer that a later workbook applies retrospectively.
- The AY 2007-08 portal page surfaced Excel utilities for ITR-1 to ITR-6; ITR-7 availability for that year must be separately established.

## 7. Legal source hierarchy and provenance

For each parameter/rule, retain the exact source and the reason it applies:
1. Income-tax Act and amendments applicable to the period.
2. Finance Act and First Schedule rates for the relevant year.
3. Income-tax Rules and prescribed forms.
4. Notifications and circulars, with validity/effective dates.
5. Binding judicial decisions and jurisdictional applicability.
6. Official Excel utility formulas, validations and examples as implementation evidence.
7. Secondary explanations only as discovery aids, never as sole authority.

The rule registry must support supersession, retrospective amendments, sunset clauses, territorial/jurisdictional relevance, and multiple versions effective on different dates.

## 8. Verification strategy

A year/form matrix is mandatory. Do not claim all years/forms are supported until each cell has evidence.

Test layers:
- Unit tests for every formula and statutory boundary.
- Golden cases from official utility examples and independently checked computations.
- Differential tests against official Excel outputs where the utility exists and can be run.
- Regression tests for every defect and legal amendment.
- Boundary tests for slab thresholds, caps, dates, age categories, instalments, rounding and loss expiry.
- Cross-year tests for changes in law and transitional provisions.
- Metamorphic tests for arithmetic invariants.
- Independent reviewer sign-off for legal interpretation and penalty applicability.

Each certified computation must be reproducible from an immutable fact snapshot and pinned ruleset. Reports must disclose unsupported scenarios and unverified assumptions.

## 9. Delivery sequence

### Phase 0: source inventory and scope lock
- Confirm starting period means AY 2007-08.
- Build a year-by-year inventory of official ITR-1 to ITR-7 utilities, notified forms, schemas and validation documents.
- Inventory relevant Acts, Finance Acts, Rules, amendments and transition materials.
- Create source manifest with URLs, versions, hashes and availability gaps.

### Phase 1: Excel utility reverse engineering
- Download a small representative sample: AY 2007-08, a middle historical year, AY 2025-26 / AY 2026-27, and Tax Year 2026-27 utility material.
- Inspect ITR-1 and one more complex return form first.
- Extract formulas, names, sheets, macros, lookup tables and validations.
- Build workbook comparison and evidence reports.
- Produce a reviewed rule catalogue; no full calculator claim yet.

### Phase 2: tax calculation kernel
- Build period resolver and versioned rules registry.
- Implement one narrow vertical slice (e.g. resident individual salary + interest income, normal rates, deductions, rebate, surcharge/cess as applicable).
- Validate against the matching official utility and independent manual calculations.

### Phase 3: income heads and entity coverage
- Implement all income heads and loss/deduction rules.
- Expand entity types and ITR form adapters.
- Add AMT/MAT, special rates and credits.

### Phase 4: interest, fees and penalties
- Implement section-specific date and amount logic.
- Separate computability from legal levy/applicability.
- Validate limitation, procedure and transitional treatment.

### Phase 5: historical coverage and new Act
- Fill the year/form support matrix back to AY 2007-08.
- Add Income-tax Act, 2025 / Rules, 2026 for Tax Year 2026-27 onward.
- Implement cross-reference and transition support without conflating old and new provisions.

### Phase 6: user interface and assessment reports
- Case intake, data entry/import, source evidence, computation trace, comparison, review and export.
- Generate readable computation sheets and supporting schedules.
- Keep every output reviewable and reproducible.

## 10. First acceptance criteria

The first vertical slice is accepted only when:
- the exact AY/TY and governing Act are resolved correctly;
- source facts are immutable and traceable;
- every applied rate/deduction/rebate is linked to a versioned legal rule;
- calculation is deterministic using decimal arithmetic;
- the official utility comparison matches for the selected test case, or every difference is documented and approved;
- an independent test validates the same result;
- the output explains each step and rounding;
- no unsupported legal issue is silently guessed.

## 11. Known scope risks

- Historical utilities may be missing, revised or no longer executable on modern Excel.
- Excel formulas may depend on VBA, hidden sheets, named ranges or external data.
- Utility calculations can contain implementation defects; statute prevails.
- The Income-tax Act, 2025 changes terminology and legal structure from 1 April 2026; old proceedings remain subject to transition/savings rules.
- Penalty liability is often fact- and procedure-dependent and cannot safely be reduced to a numeric formula.
- ITR form eligibility and reporting structure change over time; the engine must maintain versioned form adapters.

## 12. Explicit non-goals for the first release

- No automated filing or submission to the e-Filing portal.
- No direct access to ITBA, Insight, AIS, CPC or departmental systems.
- No automatic penalty imposition recommendation.
- No AI-generated tax result without deterministic rule execution.
- No paid subscription or API dependency.
- No claim of complete 2007-to-current coverage before the support matrix and test evidence are complete.
