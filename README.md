# International Cost of Capital

Streamlit app for Professor Sergio Rebelo's **Building an International Cost of Capital App** assignment. Compares USD and selected-country-currency equity cost, debt cost, and WACC using the formulas in *CasePacket2026-part9.pdf*, pages 18 and 23–29.

## Deploy

1. Create a GitHub repository and upload **all five** files: `app.py`, `calculations.py`, `requirements.txt`, `source_data.xlsx`, `test_calculations.py` (and this README).
2. At https://share.streamlit.io choose **Create app**, connect your repository, select `app.py` as the entrypoint, and deploy.
3. In the deployed app, click **Refresh live data**. Review source statuses and manually supply any missing bond yields. The 4% initial yield fields are placeholders, not live data.

For local development:

```bash
pip install -r requirements.txt
streamlit run app.py
python -m unittest -v test_calculations.py
```

## Inputs and sources

- **Industry unlevered betas**: Damodaran, US industry data, `https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls`. Local workbook's beta tab says **January 5, 2026**. Refresh attempts the current XLS file.
- **BBB USD spread**: Damodaran, Baa2/BBB for large nonfinancial firms, `https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html`. The uploaded table was identified as **January 2026**. Refresh attempts the current page.
- **Corporate tax rates**: OECD source listed in the supplied workbook, `https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html`. **Current implementation uses workbook rates only**, not a live OECD feed; rates may be stale. A refresh does **not** update OECD data. Update the workbook tax tab to update rates.
- **10-year government yields**: `https://tradingeconomics.com/bonds`. Refresh attempts to parse public HTML; some deployments may be blocked or the page layout may change. When unavailable, **enter both yields manually from a verified current quote**. The app labels manual inputs; it does not fabricate current rates. The fetch timestamp is not necessarily the quote's market date.

## Calculation methodology

Rates are stored as decimals and calculated without intermediate rounding.

- `D/E = d/(1-d)`
- `beta_E = beta_U * (1+(1-tax)*D/E)`
- `Re_USD = US_10Y + beta_E*ERP`
- `factor = (1+foreign_10Y)/(1+US_10Y)`
- `Re_foreign = (1+Re_USD)*factor - 1`
- `spread_foreign = spread_USD*factor`, unless manually overridden
- `Rd_USD = US_10Y + spread_USD`
- `Rd_foreign = foreign_10Y + spread_foreign`
- `WACC = (1-d)*Re + d*Rd*(1-tax)` in each currency.

Same selected project tax rate, debt share and ERP in both scenarios. Government yields are proxies for risk-free rates; no extra country equity premium. The conversion assumes relative PPP and equal real interest rates. Debt beta is assumed zero, and interest tax shields are fully usable.

## Verification (independent from the UI)

Run `python -m unittest -v test_calculations.py`.

Colombia class example: unlevered beta 0.80, debt share 30%, tax 35%, ERP 6.5%, US yield 4%, Colombia yield 12%, USD spread 1.5%.

| Metric | USD | COP |
|---|---:|---:|
| Cost of equity | 10.6486% | 19.1600% |
| Pretax debt cost | 5.5000% | 13.6154% |
| After-tax debt cost | 3.5750% | 8.8500% |
| WACC | 8.5265% | 16.0670% |

Three additional invariants are tested: equal yields imply equal outputs when the foreign spread override is off; zero debt implies WACC equals equity cost; overriding foreign spread leaves all USD outputs unchanged.

## Limitations and review before submission

- OECD live refresh is **not implemented**. The assignment asks for refresh of data fetching, so this should be improved before final submission.
- Trading Economics parsing is best effort and **has not been verified against the live website** in this environment. Manually check the yield values and quote dates.
- The full Streamlit UI has **not been launched in this environment**; only Python syntax and calculation tests have been run.
- Verify that country taxes and industry betas correspond to the latest available observation dates.
- Keep screenshots of AI interactions for the assignment submission, and prepare a short independent spreadsheet calculation and design-choice note.
