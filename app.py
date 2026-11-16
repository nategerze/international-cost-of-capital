"""International Cost of Capital — Sergio Rebelo class methodology."""
from __future__ import annotations
import io
import re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
BOOK = BASE / 'source_data.xlsx'
BETAS_URL = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
SPREAD_URL = 'https://pages.stern.nyu.edu/adamodar/New_Home_Page/datafile/ratings.html'
TAX_URL = 'https://www.oecd.org/en/publications/corporate-tax-statistics-2024_9c27d6e8-en/full-report/statutory-corporate-income-tax-rates_440f9286.html'
BONDS_URL = 'https://tradingeconomics.com/bonds'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; academic research app)'}

# Country names and ISO3 codes used by the OECD input sheet. Only countries with a
# verified Trading Economics quote are selectable in automatic mode.
COUNTRIES = {
 'United States':'USA','Canada':'CAN','Mexico':'MEX','Brazil':'BRA','Colombia':'COL',
 'United Kingdom':'GBR','Germany':'DEU','France':'FRA','Italy':'ITA','Spain':'ESP',
 'Portugal':'PRT','Ireland':'IRL','Netherlands':'NLD','Belgium':'BEL','Switzerland':'CHE',
 'Sweden':'SWE','Norway':'NOR','Denmark':'DNK','Finland':'FIN','Poland':'POL',
 'Australia':'AUS','New Zealand':'NZL','Japan':'JPN','China':'CHN','India':'IND',
 'South Korea':'KOR','Singapore':'SGP','South Africa':'ZAF','Türkiye':'TUR',
 'Turkey':'TUR','Greece':'GRC','Austria':'AUT','Czech Republic':'CZE','Czechia':'CZE',
 'Hungary':'HUN','Israel':'ISR','Indonesia':'IDN','Malaysia':'MYS','Thailand':'THA',
 'Chile':'CHL','Argentina':'ARG','Peru':'PER','Slovakia':'SVK','Luxembourg':'LUX',
 'United Arab Emirates':'ARE','Saudi Arabia':'SAU','Romania':'ROU','Bulgaria':'BGR',
 'Philippines':'PHL','Vietnam':'VNM','Russia':'RUS','Iceland':'ISL'
}

def pct(x):
    return f'{100*x:.4f}%'

from calculations import compute

def read_betas(book):
    df = pd.read_excel(book, sheet_name='Betas Industry Averages', header=9)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[['Industry Name','Unlevered beta']].copy()
    df['Unlevered beta'] = pd.to_numeric(df['Unlevered beta'],errors='coerce')
    return df.dropna().query('`Unlevered beta` >= 0').drop_duplicates('Industry Name').sort_values('Industry Name')

def read_tax(book):
    df = pd.read_excel(book, sheet_name='Corporate Tax Rates', header=3)
    df.columns = [str(c).strip() for c in df.columns]
    df = df[['Country','Statutory corporate income tax rates']].dropna()
    df['Statutory corporate income tax rates'] = pd.to_numeric(df['Statutory corporate income tax rates'],errors='coerce')
    return dict(zip(df['Country'].astype(str), df['Statutory corporate income tax rates']))

def read_spread(book):
    df = pd.read_excel(book, sheet_name='BBB USD borrowing spread', header=5)
    for _,row in df.iterrows():
        if 'Baa2/BBB' in [str(v).strip() for v in row.values]:
            idx = [str(v).strip() for v in row.values].index('Baa2/BBB')
            return float(row.iloc[idx+1])
    raise ValueError('BBB benchmark not found in workbook')

def fetch_betas():
    r=requests.get(BETAS_URL,headers=HEADERS,timeout=20);r.raise_for_status()
    raw=pd.read_excel(io.BytesIO(r.content),header=None)
    matches=raw.index[raw.iloc[:,0].astype(str).str.strip().eq('Industry Name')].tolist()
    if not matches: raise ValueError('Industry Name header missing in live Damodaran file')
    header=int(matches[0]);df=pd.read_excel(io.BytesIO(r.content),header=header)
    df.columns=[str(c).strip() for c in df.columns]
    out=df[['Industry Name','Unlevered beta']].copy()
    out['Unlevered beta']=pd.to_numeric(out['Unlevered beta'],errors='coerce')
    out=out.dropna().drop_duplicates('Industry Name')
    if len(out)<20:raise ValueError('Unexpectedly few industry rows')
    return out.sort_values('Industry Name')

def fetch_spread():
    r=requests.get(SPREAD_URL,headers=HEADERS,timeout=20);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    for tr in soup.select('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
        if any('Baa2/BBB' in c for c in cells):
            idx=next(i for i,c in enumerate(cells) if 'Baa2/BBB' in c)
            for cell in cells[idx+1:]:
                m=re.search(r'(\d+(?:\.\d+)?)\s*%',cell)
                if m:return float(m.group(1))/100
    raise ValueError('Could not identify BBB spread in current ratings page')

def fetch_bonds():
    """Best-effort scrape of public HTML table; never fabricate yields."""
    r=requests.get(BONDS_URL,headers=HEADERS,timeout=25);r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser')
    results={}
    # Trading Economics bond listing typically has a 'Yield' column and a
    # country/bond column; parse table headers rather than fixed positions.
    for table in soup.find_all('table'):
        heads=[x.get_text(' ',strip=True).lower() for x in table.select('thead th')]
        yield_idx=next((i for i,h in enumerate(heads) if h=='yield' or h.startswith('yield ')),None)
        if yield_idx is None:continue
        for tr in table.select('tbody tr'):
            cells=[x.get_text(' ',strip=True) for x in tr.find_all(['td','th'],recursive=False)]
            if len(cells)<=yield_idx:continue
            label=cells[0]
            if '10y' not in label.lower() and '10 year' not in label.lower() and '10-year' not in label.lower():
                # TE /bonds page is itself a list of 10Y bonds; allow country-only rows.
                pass
            country=next((c for c in COUNTRIES if label.lower().startswith(c.lower())),None)
            if not country:continue
            m=re.search(r'-?\d+(?:\.\d+)?',cells[yield_idx].replace(',',''))
            if m:
                val=float(m.group())/100
                if -0.1 < val < 0.5:results[country]=val
    if len(results)<3:raise ValueError('Bond table unavailable or page structure changed; enter yields manually')
    return results

@st.cache_data(show_spinner=False)
def load_local():
    return read_betas(BOOK),read_tax(BOOK),read_spread(BOOK)

@st.cache_data(show_spinner=False)
def load_live_betas():return fetch_betas()
@st.cache_data(show_spinner=False)
def load_live_spread():return fetch_spread()
@st.cache_data(show_spinner=False)
def load_live_bonds():return fetch_bonds()

st.set_page_config(page_title='International Cost of Capital',layout='wide')
st.title('International Cost of Capital')
st.caption('USD vs. selected-country currency | Sergio Rebelo course methodology')
if not BOOK.exists():st.error('source_data.xlsx is missing. Put the supplied workbook beside app.py.');st.stop()

with st.sidebar:
    st.header('Data and assumptions')
    if st.button('↻ Refresh live data',use_container_width=True):
        load_live_betas.clear();load_live_spread.clear();load_live_bonds.clear()
        st.rerun()
    use_live=st.checkbox('Attempt latest online data',value=True)
    st.caption('If a live source fails, the app labels the workbook fallback. Bond yields require a live quote or manual entry.')

betas,taxes,spread=load_local()
provenance={'Industry betas':'Workbook (Damodaran; updated Jan 5, 2026)',
            'BBB USD spread':'Workbook (Damodaran; date in screenshot Jan 2026)',
            'Corporate taxes':'Workbook (OECD; source linked in workbook; observation dates not individually supplied)',
            'Bond yields':'Not loaded'}
errors=[]
if use_live:
    try:betas=load_live_betas();provenance['Industry betas']='Live Damodaran file (fetched '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+')'
    except Exception as e:errors.append('Industry betas: '+str(e))
    try:spread=load_live_spread();provenance['BBB USD spread']='Live Damodaran ratings page (fetched '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+')'
    except Exception as e:errors.append('BBB spread: '+str(e))
    # OECD rates are workbook-sourced; no unverified current rates substituted.
    try:bonds=load_live_bonds();provenance['Bond yields']='Trading Economics public table (fetched '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+')'
    except Exception as e:bonds={};errors.append('Bond yields: '+str(e))
else:bonds={}
if errors:
    with st.expander('Data retrieval notices',expanded=True):
        for error in errors:st.warning(error)

names=betas['Industry Name'].astype(str).tolist()
default_industry=next((n for n in names if 'Software (System' in n),names[0])
left,right=st.columns(2)
with left:
    industry=st.selectbox('Industry',names,index=names.index(default_industry))
    country=st.selectbox('Selected country',list(COUNTRIES),index=0)
    erp=st.number_input('Equity risk premium (%)',value=6.5,step=0.1)/100
    debt=st.slider('Target debt financing (%)',0.0,95.0,30.0,1.0)/100
    tax_choice=st.radio('Project tax rate for BOTH currencies',['United States','Selected country'],horizontal=True)
with right:
    beta_default=float(betas.loc[betas['Industry Name']==industry,'Unlevered beta'].iloc[0])
    beta=st.number_input('Unlevered beta',value=beta_default,format='%.5f')
    us_tax=taxes.get('USA'); foreign_tax=taxes.get(COUNTRIES[country])
    if us_tax is None:st.warning('U.S. tax rate unavailable in workbook: enter manually.')
    if foreign_tax is None:st.warning(f'{country} tax rate unavailable in workbook: enter manually.')
    tax_default=(us_tax if tax_choice=='United States' else foreign_tax)
    tax=st.number_input('Corporate tax rate used (%)',value=float(100*tax_default) if tax_default is not None else 25.0,min_value=0.0,max_value=99.0,step=0.1)/100
    spread=st.number_input('USD BBB borrowing spread (%)',value=float(100*spread),min_value=0.0,step=0.01,format='%.4f')/100

us_auto=bonds.get('United States');other_auto=bonds.get(country)
y1,y2=st.columns(2)
with y1:
    st.caption('No yield is silently assumed. Check the quote and enter a manual value if necessary.')
    us_manual=st.checkbox('Manually enter U.S. yield',value=us_auto is None)
    us_y=st.number_input('U.S. 10-year government yield (%)',value=round(100*us_auto,4) if us_auto is not None else 4.0,step=0.1,format='%.4f',disabled=not us_manual)/100
    if not us_manual:us_y=us_auto
with y2:
    foreign_manual=st.checkbox('Manually enter selected-country yield',value=other_auto is None)
    foreign_y=st.number_input(f'{country} 10-year government yield (%)',value=round(100*other_auto,4) if other_auto is not None else 4.0,step=0.1,format='%.4f',disabled=not foreign_manual)/100
    if not foreign_manual:foreign_y=other_auto
if us_manual or foreign_manual:
    st.info('One or both bond yields are manually entered. The initial 4.0% field values are **illustrative placeholders**, not verified market observations. Replace them before using the result.')
if country=='United States':
    st.caption('United States selected: matching government yields are required for identical-currency comparisons.')
    if not foreign_manual:foreign_y=us_y

foreign_override=st.checkbox('Override foreign-currency BBB spread',value=False)
auto_spread=spread*(1+foreign_y)/(1+us_y)
foreign_spread=st.number_input('Foreign-currency spread (%)',value=round(auto_spread*100,5),min_value=0.0,step=0.01,format='%.5f',disabled=not foreign_override)/100 if foreign_override else None
result=compute(beta,debt,tax,erp,us_y,foreign_y,spread,foreign_spread)
st.subheader('Side-by-side results')
view=pd.DataFrame({f'USD': [pct(result[k][0]) for k in ['Cost of equity','Pretax cost of debt','After-tax cost of debt','WACC']],
                   f'{country} currency': [pct(result[k][1]) for k in ['Cost of equity','Pretax cost of debt','After-tax cost of debt','WACC']]},
                  index=['Cost of equity','Pretax cost of debt','After-tax cost of debt','WACC'])
st.dataframe(view,use_container_width=True)
st.caption(f"Levered beta: {result['Levered beta']:.5f} | Auto foreign spread: {pct(result['Automatic foreign spread'])} | Applied foreign spread: {pct(result['Foreign spread used'])}")

st.subheader('All-industry comparison')
records=[]
for _,row in betas.iterrows():
    calc=compute(float(row['Unlevered beta']),debt,tax,erp,us_y,foreign_y,spread,foreign_spread)
    records.append({'Industry':row['Industry Name'],'Unlevered beta':float(row['Unlevered beta']),
                    'Levered beta':calc['Levered beta'],'USD cost of equity':calc['Cost of equity'][0],
                    'Foreign cost of equity':calc['Cost of equity'][1], 'USD WACC':calc['WACC'][0],
                    'Foreign WACC':calc['WACC'][1]})
all_df=pd.DataFrame(records)
st.dataframe(all_df,hide_index=True,use_container_width=True,column_config={k:st.column_config.NumberColumn(k,format='%.4f') for k in ['Unlevered beta','Levered beta'] } | {k:st.column_config.NumberColumn(k,format='%.4f%%') for k in []})
export=all_df.copy()
for col in ['USD cost of equity','Foreign cost of equity','USD WACC','Foreign WACC']:export[col]=export[col]*100
st.download_button('Download all-industry results (CSV, rates in %)',export.to_csv(index=False).encode(),file_name='international_cost_of_capital.csv',mime='text/csv')
with st.expander('Methodology and assumptions'):
    st.markdown('''**Project leverage:** D/E = d/(1-d); βE = βU × [1+(1−τ)D/E].

**USD equity:** Re = U.S. yield + βE × ERP.

**Foreign equity:** (1+Re*) = (1+Re) × (1+foreign yield)/(1+U.S. yield).

**Debt:** Rd = government yield + BBB spread; foreign spread defaults to USD spread × (1+foreign yield)/(1+U.S. yield).

**WACC:** (1−d) × Re + d × Rd × (1−τ), separately in each currency.

Government yields are treated as risk-free proxies. No separate country equity premium. U.S. industry beta proxies for project risk. Same project tax rate, ERP and leverage in both currencies. Interest tax shields are fully usable; debt beta is zero. Currency conversion assumes equal real rates and relative purchasing power parity. Foreign spread override changes only foreign results.''')
with st.expander('Data sources, observation dates and limitations',expanded=True):
    for k,v in provenance.items():st.write(f'**{k}:** {v}')
    st.markdown(f'- [Damodaran industry betas]({BETAS_URL})\n- [Damodaran ratings and default spreads]({SPREAD_URL})\n- [OECD corporate tax rates]({TAX_URL})\n- [Trading Economics government bond yields]({BONDS_URL})')
    st.warning('OECD data currently loads from the supplied workbook, not a verified live OECD API. Its observation dates may differ by country. A successful refresh does not imply OECD rates were updated. Trading Economics may block scraping; manual bond yields remain available. A fetch timestamp is not the market observation date.')
