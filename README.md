# NSE Option Chain Support/Resistance Graph

This small Python project reads an NSE option-chain table (typically CSV or Excel), extracts `Strike`, `CE OI`, and `PE OI`, then plots:
- Put OI peaks (support candidates) in **green**
- Call OI peaks (resistance candidates) in **red**
- The **maximum support** (max PE OI) and **maximum resistance** (max CE OI) are highlighted.

## Requirements

Install dependencies:

```powershell
cd "C:\Users\ravur\OneDrive\Documents\nse_option_chain_graph"
python -m pip install -r requirements.txt
```

## Run with the included sample

```powershell
python -m nse_option_chain_graph --input "C:\Users\ravur\OneDrive\Documents\nse_option_chain_graph\sample\option_chain_sample.csv" --output "support_resistance.png"
```

It will print the max support/resistance strikes and create `support_resistance.png` in the project folder.

## Run with your own NSE file

```powershell
python -m nse_option_chain_graph --input "path\to\option_chain.csv" --output "support_resistance.png"
```

## Run with your `Downloads/option_chain_data.csv`

This is a common NSE export that comes with flat headers like `STRIKE`, `OI`, and `OI.1`.

```powershell
python -m nse_option_chain_graph --input "C:\Users\ravur\Downloads\option_chain_data.csv" --output "support_resistance.png"
```

If your column names don't match common NSE exports, pass explicit columns:

```powershell
python -m nse_option_chain_graph --input "path\to\option_chain.csv" --output "support_resistance.png" `
  --strike-col "Strike Price" --ce-oi-col "CE OI" --pe-oi-col "PE OI"
```

## How support/resistance is computed

- **Support** = strike with the highest **PE OI**
- **Resistance** = strike with the highest **CE OI**
- Additionally, the tool highlights the **top N** PE/CE OI strikes (default `N=3`).

## Notes / next step

If you tell me what your NSE file columns look like (paste the header row), I can tune the column guessing rules and (if you want) the exact formula used for support/resistance.

