# Courier Pricing Automation

This project automates the generation of courier pricing sheets from a Base File template.

## Structure

- `src/models.py`: Data structures for Courier, Zone, and Rules.
- `src/parser.py`: Logic to parse the Excel Base File.
- `src/logic.py`: Core pricing engine (Slab expansion, Reset logic, RTO/RVP calculations).
- `src/utils.py`: Helper functions for unit conversion.
- `src/main.py`: Entry point to run the automation.

## Usage

1. Place your input file (e.g., `D2C Pricing Base File Template (1).xlsx`) in the root directory.
2. Run the script:
   ```bash
   python -m src.main
   ```
3. The output will be generated in `output/Courier_Pricing_Output.xlsx`.

## Features

- **Modular Design**: Separated parsing, logic, and models.
- **Slab Expansion**: Handles Base, Incremental, and Reset slabs.
- **Reset Logic**: Correctly looks ahead to apply reset prices to the relevant slab range.
- **Global Parameters**: Auto-fills missing global parameters (Tax, COD, etc.) from other zones if available.
- **GST Handling**: Automatically converts GST Inclusive prices to Exclusive in the output.
- **RTO/RVP**: Calculates RTO % and RVP charges based on slabs or multipliers.
