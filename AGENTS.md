Executive Summary
The system will automate the creation of courier pricing output files from standardized BASE FILE templates.
Users will manually extract commercial details from courier agreements and prepare structured BASE FILE sheets per courier.
The system will:
Accept a single input file containing multiple courier BASE sheets.
Automatically expand pricing slabs.
Apply zone-wise pricing logic.
Generate a standardized output file with one output sheet per courier in the google drive folder.
Support configurable maximum weight.
This removes manual slab calculations and ensures consistency across couriers.
Note:
PDF extraction automation is considered a secondary phase and will be explored later using agentic AI.
Background & Problem Statement
Commercial onboarding teams currently receive courier agreements in PDF format and manually convert them into operational pricing sheets.
This process involves:
Extracting commercial data from PDFs.
Interpreting weight slab rules.
Manually building expanded output tables rates.
Challenges:
Manual slab rate calculations are time-consuming.
Many types of rates format for FWD, RTO and RVP
Different courier formats increase complexity.
To reduce operational effort and errors, the slab expansion and output generation will be automated.
PDF extraction is not part of the initial scope.

Objectives & Success Criteria
Objectives
Automate slab expansion from BASE FILE templates.
Generate courier-wise output sheets in standardized format.
Support multiple couriers in a single input file.
Ensure consistency across zones and weight slabs.
Allow configurable maximum weight.
Success Criteria
100% correct slab expansion logic.
Output matches expected format for all couriers.
Support for all defined slab rule types.
Zero manual calculations required.
Scope
In Scope (Phase 1)
Input: Excel file containing BASE sheets for multiple couriers.
Parsing courier-wise, zone-wise pricing rules.
Slab expansion up to configurable max weight.
Calculation of:
Forward pricing
RTO pricing
RVP pricing with and without QC
COD fields
Global charges(dock, FSC etc.)
Output: Single Excel file with one output sheet per courier in the google drive folder.
Out of Scope (Phase 1)
PDF ingestion.
OCR or document parsing.
AI-based extraction from agreements.

Phase 2 (Future)
Automated PDF extraction using agentic AI.
Base file generation for all couriers.
Confidence scoring and reviewing UI.
Input Format
Input File
Single Excel file.
One sheet per courier partner.
Each sheet follows the BASE FILE template.
BASE FILE Contents
Per courier sheet:
Zone-wise pricing rules:
FWD slabs
RTO slabs or multipliers
RVP slabs or flat charges and multiplier
Global parameters:
Volumetric coefficient
Tax %
Fuel surcharge %
Docket charge
COD settings
Output Format
Single Excel file in google drive folder with:
One sheet per courier.
Each sheet expanded up to configurable max weight.
Output Columns
Same as existing:
Zone
Start Weight(gm)
Min Weight(gm)
Max Weight(gm)
Price
Additional Unit(gm)
Additional Unit Rate
Volumetric Coefficient
Tax(%)
Fuel Surcharge(%)
Docket Charge
Invoice Percentage for COD(Optional)%
COD Operator(Min/Max)(Optional)
Fixed COD Charge(Optional)
RVP Without QC
RVP With QC
RTO (Forward %)
Slab Expansion Logic
Weight Expansion
Default slab step: 500 g.
Maximum weight: configurable (default 50,000 g).
Slab Rule Types
Each zone may contain:
Base slab
Example: 500g → ₹3
Meaning: 0–500g = ₹3
Incremental slab
Example: add 0.5kg → +₹1
Meaning:
After base slab,
Every 500g adds ₹1.


Reset slab
Example: 2kg → ₹7
Meaning:
The price at 2kg becomes ₹7.
Overrides accumulated price.
Reset Rule (Critical Logic)
If a reset slab exists:
All slabs within incremental gap whose max weight equals the reset weight
must have the reset price.
Example:
2kg → 7
add 1kg → +2
4kg → 13
Correct expansion:
Slab
Price
2000–2500g
9
2500–3000g
9
3000–3500g
13 ← reset applied
3500–4000g
13 ← reset applied

Note: If we had
2kg → 7
add 0.5kg → +1
4kg → 13
Correct expansion:
Slab
Price
2000–2500g
8
2500–3000g
9
3000–3500g
10
3500–4000g
13 ← reset applied

RTO Logic
Two supported modes:
Slab-based RTO.
Multiplier-based RTO:  FWD × multiplier
RVP Logic
Two supported modes:
Slab-based RVP.
Maximum of Flat addition over FWD and a fraction of FWD:
RVP = Max(FWD + flat charge, 1.2*FWD)
RVP with QC = RVP without QC + flat QC charges
COD Logic
If operator is:
MAX: COD = max(invoice% of order value, fixed charge)
MIN: COD = min(invoice% of order value, fixed charge)
Functional Requirements
Core Automation Engine
Read input Excel with multiple courier sheets.
Parse BASE FILE rules per zone.
Expand slabs to max weight.
Apply reset logic.
Compute RTO, RVP, RVP with QC and COD fields.
Generate output Excel with courier-wise sheets in the google drive folder.
Non-Functional Requirements
Deterministic calculations.
Configurable max weight.
Processing time under:
5 seconds per courier sheet.
No dependency on AI/LLM in Phase 1.
Error Handling
System should flag:
Missing base slab.
Conflicting reset rules.
Invalid weight units.
Missing zone definitions.
Deliverables
Phase 1:
Slab expansion engine.
Multi-courier input processor.
Output Excel generator in google drive folder.
Documentation and test cases.

12. Sample files
Base file template: D2C Pricing Base File Template