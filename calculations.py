from __future__ import annotations

def compute(beta_u, debt_share, tax, erp, us_yield, foreign_yield, usd_spread, foreign_spread=None):
    """All rates decimal. Uses full-precision gross-rate conversion from class."""
    if not (0 <= debt_share < 1 and 0 <= tax < 1 and us_yield > -1 and foreign_yield > -1):
        raise ValueError('Invalid debt share, tax rate or bond yield')
    debt_equity = debt_share / (1 - debt_share)
    beta_e = beta_u * (1 + (1-tax) * debt_equity)
    re_us = us_yield + beta_e * erp
    factor = (1 + foreign_yield) / (1 + us_yield)
    re_foreign = (1 + re_us) * factor - 1
    s_foreign_auto = usd_spread * factor
    s_foreign = s_foreign_auto if foreign_spread is None else foreign_spread
    rd_us = us_yield + usd_spread
    rd_foreign = foreign_yield + s_foreign
    return {'Levered beta': beta_e, 'D/E': debt_equity, 'Currency factor': factor,
            'Automatic foreign spread': s_foreign_auto, 'Foreign spread used': s_foreign,
            'Cost of equity': (re_us, re_foreign),
            'Pretax cost of debt': (rd_us, rd_foreign),
            'After-tax cost of debt': (rd_us*(1-tax), rd_foreign*(1-tax)),
            'WACC': ((1-debt_share)*re_us+debt_share*rd_us*(1-tax),
                     (1-debt_share)*re_foreign+debt_share*rd_foreign*(1-tax))}

