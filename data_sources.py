"""Defensive source parsers. No fabricated market quotes or silent defaults."""
import io
import re
from datetime import datetime, timezone
from urllib.parse import quote
import pandas as pd
import requests
from bs4 import BeautifulSoup

BETAS_HTML = 'https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/Betas.html'
BETAS_XLS = 'https://pages.stern.nyu.edu/~adamodar/pc/datasets/betas.xls'
BONDS = 'https://tradingeconomics.com/bonds'
HEADERS = {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36', 'Accept-Language':'en-US,en;q=0.9'}

def get_text(url, session=requests):
    response = session.get(url, headers=HEADERS, timeout=22)
    response.raise_for_status()
    if len(response.content) < 200: raise ValueError('Source returned an empty or blocked response')
    return response.text

def _normalize(value):
    return re.sub(r'\s+', ' ', str(value).replace('\xa0',' ')).strip().casefold()

def _beta_frame(frame):
    for i in range(min(len(frame), 60)):
        labels=[_normalize(x) for x in frame.iloc[i]]
        try:
            name_idx=labels.index('industry name'); beta_idx=labels.index('unlevered beta')
        except ValueError: continue
        out=frame.iloc[i+1:,[name_idx,beta_idx]].copy()
        out.columns=['Industry Name','Unlevered beta']
        out['Industry Name']=out['Industry Name'].astype(str).str.strip()
        out['Unlevered beta']=pd.to_numeric(out['Unlevered beta'],errors='coerce')
        out=out.dropna()
        out=out[(out['Unlevered beta']>=0)&(out['Unlevered beta']<20)]
        out=out[~out['Industry Name'].str.casefold().str.startswith('total market')]
        out=out.drop_duplicates('Industry Name').sort_values('Industry Name')
        if len(out)>=30 and any('Software (System' in n for n in out['Industry Name']):return out.reset_index(drop=True)
    raise ValueError('Could not validate industry and unlevered beta columns')

def parse_beta_html(html):
    soup=BeautifulSoup(html,'html.parser')
    for table in soup.select('table'):
        rows=[]
        for tr in table.select('tr'):
            cells=tr.find_all(['th','td'],recursive=False)
            rows.append([c.get_text(' ',strip=True) for c in cells])
        if not rows:continue
        width=max(map(len,rows))
        frame=pd.DataFrame([r+['']*(width-len(r)) for r in rows])
        try:return _beta_frame(frame)
        except ValueError:pass
    raise ValueError('Official Damodaran HTML contains no validated beta table')

def parse_beta_xls(content):
    workbook=pd.ExcelFile(io.BytesIO(content))
    for sheet in workbook.sheet_names:
        frame=pd.read_excel(workbook,sheet_name=sheet,header=None)
        try:return _beta_frame(frame)
        except ValueError:continue
    raise ValueError('Downloaded XLS has no validated beta table')

def fetch_betas(session=requests):
    problems=[]
    for url,parser in [(BETAS_HTML,parse_beta_html),(BETAS_XLS,parse_beta_xls)]:
        try:
            r=session.get(url,headers=HEADERS,timeout=22);r.raise_for_status()
            data=parser(r.text if parser==parse_beta_html else r.content)
            return data,url
        except Exception as exc: problems.append(f'{url}: {type(exc).__name__}: {exc}')
    raise ValueError(' / '.join(problems))

# The /bonds overview is client-rendered in some environments. Instead retrieve
# the country-specific public page, which publishes a labeled 10Y quote.
COUNTRY_SLUGS={'United States':'united-states','United Kingdom':'united-kingdom','South Korea':'south-korea','Czech Republic':'czech-republic','Czechia':'czech-republic','Türkiye':'turkey','Turkey':'turkey','United Arab Emirates':'united-arab-emirates','New Zealand':'new-zealand','South Africa':'south-africa','Saudi Arabia':'saudi-arabia'}
COUNTRY_CODES={'United States':'US','United Kingdom':'UK','Germany':'Germany','Japan':'Japan','Canada':'Canada','France':'France','Italy':'Italy','Australia':'Australia','China':'China','India':'India','Brazil':'Brazil','Colombia':'Colombia','Mexico':'Mexico','South Korea':'South Korea'}

def bond_page_url(country):
    slug=COUNTRY_SLUGS.get(country, re.sub(r'[^a-z0-9]+','-',country.lower()).strip('-'))
    return f'https://tradingeconomics.com/{slug}/government-bond-yield'

def parse_country_bond(html,country):
    soup=BeautifulSoup(html,'html.parser')
    # Use only an explicitly labeled 10-year benchmark, not 2Y/5Y/30Y or a forecast.
    aliases={country,COUNTRY_CODES.get(country,country)}
    if country=='United States': aliases|={'US','USA'}
    if country=='United Kingdom':aliases|={'UK','GB'}
    aliases={_normalize(a) for a in aliases}
    for table in soup.select('table'):
        for tr in table.select('tr'):
            cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'],recursive=False)]
            if len(cells)<2:continue
            label=_normalize(cells[0]); m=re.match(r'^(.*?)\s+(?:10\s*y|10\s*year|10-year)(?:\s|$)',label)
            if not m or m.group(1).strip() not in aliases:continue
            number=re.match(r'^\s*([+-]?\d+(?:\.\d+)?)\s*%?\s*$',cells[1].replace(',',''))
            if not number:continue
            yield_percent=float(number.group(1))
            if -10<yield_percent<50:return yield_percent/100
    raise ValueError(f'No unambiguous {country} 10Y quote found on public country page')

def fetch_country_bond(country,session=requests):
    url=bond_page_url(country)
    html=get_text(url,session)
    return parse_country_bond(html,country),url
