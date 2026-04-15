#!/usr/bin/env python3
"""
Wikipedia Timeline Scraper & Server

Scrapes curated Wikipedia timeline articles and converts them to organized
markdown. Registry of ~230 articles across 27 categories covering financial
crises, monetary policy, central banking, currency/FX, inflation, recessions,
geopolitics, trade, sanctions, pandemics, energy, commodities, sovereign debt,
market events, financial regulation, US fiscal/legislative, elections, China,
technology, and more. No auth required.

Requires: beautifulsoup4 (pip install beautifulsoup4)

PRISM interface (clean stdout, status to stderr):
    python timelines.py catalog                                  # JSON catalog of all timelines
    python timelines.py catalog --category geopolitical          # catalog for one category
    python timelines.py get "FOMC Actions History"               # output timeline markdown
    python timelines.py get "Russo-Ukrainian_War"                # fuzzy match on wiki title
    python timelines.py get "FOMC" --no-scrape                   # skip auto-scrape if missing
    python timelines.py get-category monetary_policy             # all timelines in category

Scraping:
    python timelines.py scrape "History_of_Federal_Open_Market_Committee_actions"
    python timelines.py scrape-category financial_crises
    python timelines.py scrape-all
    python timelines.py scrape-all --force

Browsing:
    python timelines.py                                          # interactive CLI
    python timelines.py list                                     # list all categories
    python timelines.py list --category monetary_policy
    python timelines.py search "FOMC timeline"
    python timelines.py preview "History_of_Federal_Open_Market_Committee_actions"
"""

import argparse
import json
import os
import re
import sys
import time
from collections import OrderedDict
from datetime import datetime
from urllib.parse import quote

import requests

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit("beautifulsoup4 required -- pip install beautifulsoup4")


# --- Configuration ------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PRISM-WikipediaTimelines/1.0 (macro-analysis-bot)",
})

API_URL = "https://en.wikipedia.org/w/api.php"
WIKI_BASE = "https://en.wikipedia.org/wiki"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "output", "timelines")

RESCRAPE_DAYS = 7

SKIP_SECTIONS = frozenset({
    "References", "External links", "See also", "Further reading",
    "Notes", "Citations", "Bibliography", "Sources", "Footnotes",
    "External sources",
})

TIMELINE_REGISTRY = OrderedDict([

    # ── FINANCIAL CRISES ─────────────────────────────────────────────
    ("financial_crises", {
        "name": "FINANCIAL CRISES",
        "articles": [
            ("Subprime_crisis_impact_timeline",
             "2007-2008 Financial Crisis Timeline"),
            ("Financial_crisis_of_2007\u20132008",
             "2008 Financial Crisis"),
            ("Subprime_mortgage_crisis", "Subprime Mortgage Crisis"),
            ("European_debt_crisis", "European Debt Crisis"),
            ("Greek_government-debt_crisis", "Greek Debt Crisis"),
            ("2023_United_States_banking_crisis", "2023 US Banking Crisis"),
            ("1997_Asian_financial_crisis", "1997 Asian Financial Crisis"),
            ("Russian_financial_crisis_(1998)", "1998 Russian Financial Crisis"),
            ("Dot-com_bubble", "Dot-com Bubble"),
            ("Black_Monday_(1987)", "Black Monday 1987"),
            ("2020_stock_market_crash", "2020 Stock Market Crash"),
            ("Savings_and_loan_crisis", "Savings and Loan Crisis"),
            ("Mexican_peso_crisis", "1994 Mexican Peso Crisis"),
            ("2008\u20132011_Icelandic_financial_crisis",
             "Icelandic Financial Crisis"),
            ("Turkish_currency_and_debt_crisis,_2018",
             "2018 Turkish Currency Crisis"),
            ("Argentine_monetary_crisis", "Argentine Currency Crisis"),
        ],
    }),

    # ── MONETARY POLICY ──────────────────────────────────────────────
    ("monetary_policy", {
        "name": "MONETARY POLICY",
        "articles": [
            ("History_of_Federal_Open_Market_Committee_actions",
             "FOMC Actions History"),
            ("History_of_the_Federal_Reserve_System", "Federal Reserve History"),
            ("Quantitative_easing", "Quantitative Easing"),
            ("Quantitative_tightening", "Quantitative Tightening"),
            ("Federal_funds_rate", "Federal Funds Rate"),
            ("Forward_guidance", "Forward Guidance"),
            ("Zero_interest-rate_policy", "Zero/Negative Interest Rate Policy"),
            ("Yield_curve_control", "Yield Curve Control"),
            ("Discount_window", "Discount Window"),
            ("Taylor_rule", "Taylor Rule"),
        ],
    }),

    # ── GLOBAL CENTRAL BANKS ─────────────────────────────────────────
    ("global_central_banks", {
        "name": "GLOBAL CENTRAL BANKS",
        "articles": [
            ("European_Central_Bank", "European Central Bank"),
            ("Bank_of_Japan", "Bank of Japan"),
            ("Bank_of_England", "Bank of England"),
            ("People%27s_Bank_of_China", "People's Bank of China"),
            ("Swiss_National_Bank", "Swiss National Bank"),
            ("Reserve_Bank_of_Australia", "Reserve Bank of Australia"),
            ("Bank_of_Canada", "Bank of Canada"),
            ("Central_bank", "Central Banking (Overview)"),
            ("European_System_of_Central_Banks",
             "European System of Central Banks"),
        ],
    }),

    # ── CURRENCY & FX ────────────────────────────────────────────────
    ("currency_fx", {
        "name": "CURRENCY & FX REGIMES",
        "articles": [
            ("Bretton_Woods_system", "Bretton Woods System"),
            ("Nixon_shock", "Nixon Shock (1971)"),
            ("Plaza_Accord", "Plaza Accord (1985)"),
            ("Louvre_Accord", "Louvre Accord (1987)"),
            ("Black_Wednesday", "Black Wednesday (1992 ERM Crisis)"),
            ("Currency_crisis", "Currency Crises (Overview)"),
            ("2015_Chinese_stock_market_crash",
             "2015 Chinese Stock Market Crash"),
            ("2015\u201316_Chinese_stock_market_turbulence",
             "2015-16 Chinese Market Turbulence"),
            ("Gold_standard", "Gold Standard"),
            ("Petrodollar_recycling", "Petrodollar Recycling"),
            ("Exchange_rate_regime", "Exchange Rate Regimes"),
            ("Reserve_currency", "Reserve Currency"),
        ],
    }),

    # ── INFLATION & DEFLATION ────────────────────────────────────────
    ("inflation_deflation", {
        "name": "INFLATION & DEFLATION",
        "articles": [
            ("Inflation_in_the_United_States", "US Inflation History"),
            ("Early_1980s_recession", "Volcker Recession / Early 1980s"),
            ("Stagflation", "Stagflation"),
            ("2021\u20132023_inflation_surge",
             "2021-2023 Inflation Surge"),
            ("Deflation", "Deflation"),
            ("Lost_Decades_(Japan)", "Japan Lost Decades"),
            ("Hyperinflation", "Hyperinflation (Overview)"),
            ("Hyperinflation_in_Zimbabwe", "Zimbabwe Hyperinflation"),
            ("Hyperinflation_in_Venezuela", "Venezuela Hyperinflation"),
            ("Phillips_curve", "Phillips Curve"),
            ("Wage%E2%80%93price_spiral", "Wage-Price Spiral"),
        ],
    }),

    # ── RECESSIONS ───────────────────────────────────────────────────
    ("recessions", {
        "name": "RECESSIONS & DEPRESSIONS",
        "articles": [
            ("Great_Depression", "Great Depression"),
            ("Causes_of_the_Great_Depression", "Causes of Great Depression"),
            ("Great_Recession", "Great Recession (2007-2009)"),
            ("COVID-19_recession", "COVID-19 Recession"),
            ("Early_2000s_recession", "Early 2000s Recession"),
            ("Early_1990s_recession", "Early 1990s Recession"),
            ("List_of_recessions_in_the_United_States",
             "List of US Recessions"),
            ("Business_cycle", "Business Cycle"),
            ("Abenomics", "Abenomics"),
        ],
    }),

    # ── MARKET EVENTS ────────────────────────────────────────────────
    ("market_events", {
        "name": "MARKET EVENTS & BLOWUPS",
        "articles": [
            ("Long-Term_Capital_Management", "LTCM"),
            ("Collapse_of_Lehman_Brothers", "Lehman Brothers Collapse"),
            ("Bear_Stearns", "Bear Stearns"),
            ("2010_flash_crash", "2010 Flash Crash"),
            ("2015\u201316_stock_market_selloff",
             "2015-16 Global Selloff"),
            ("GameStop_short_squeeze", "GameStop Short Squeeze"),
            ("Archegos_Capital_Management", "Archegos Collapse"),
            ("Collapse_of_FTX", "FTX Collapse"),
            ("Cryptocurrency_bubble", "Cryptocurrency Bubble"),
            ("Collapse_of_Silicon_Valley_Bank", "SVB Collapse"),
            ("Collapse_of_Credit_Suisse", "Credit Suisse Collapse"),
            ("Enron_scandal", "Enron Scandal"),
            ("WorldCom_scandal", "WorldCom Scandal"),
            ("Barings_Bank", "Barings Bank Collapse"),
            ("Washington_Mutual", "Washington Mutual"),
            ("Northern_Rock", "Northern Rock"),
            ("Flash_crash", "Flash Crashes (Overview)"),
            ("2018_cryptocurrency_crash", "2018 Crypto Crash"),
            ("Taper_tantrum", "Taper Tantrum (2013)"),
        ],
    }),

    # ── FINANCIAL REGULATION ─────────────────────────────────────────
    ("financial_regulation", {
        "name": "FINANCIAL REGULATION",
        "articles": [
            ("Dodd\u2013Frank_Wall_Street_Reform_and_Consumer_Protection_Act",
             "Dodd-Frank Act"),
            ("Glass\u2013Steagall_legislation",
             "Glass-Steagall Act"),
            ("Gramm\u2013Leach\u2013Bliley_Act",
             "Gramm-Leach-Bliley Act (Glass-Steagall Repeal)"),
            ("Basel_III", "Basel III"),
            ("Basel_II", "Basel II"),
            ("Sarbanes\u2013Oxley_Act", "Sarbanes-Oxley Act"),
            ("Volcker_Rule", "Volcker Rule"),
            ("Too_big_to_fail", "Too Big To Fail"),
            ("Troubled_Asset_Relief_Program", "TARP"),
            ("Emergency_Economic_Stabilization_Act_of_2008",
             "Emergency Economic Stabilization Act 2008"),
        ],
    }),

    # ── SOVEREIGN DEBT ───────────────────────────────────────────────
    ("sovereign_debt", {
        "name": "SOVEREIGN DEBT",
        "articles": [
            ("Latin_American_debt_crisis", "Latin American Debt Crisis"),
            ("Argentine_debt_restructuring", "Argentine Debt Restructuring"),
            ("Italian_government_debt", "Italian Government Debt"),
            ("United_States_public_debt", "US Public Debt"),
            ("National_debt_of_Japan", "Japanese Government Debt"),
            ("List_of_sovereign_debt_crises", "List of Sovereign Debt Crises"),
            ("Debt-to-GDP_ratio", "Debt-to-GDP Ratio"),
        ],
    }),

    # ── US PRESIDENTS ────────────────────────────────────────────────
    ("us_presidents", {
        "name": "US PRESIDENCIES",
        "articles": [
            ("Presidency_of_Joe_Biden", "Biden Presidency"),
            ("First_presidency_of_Donald_Trump", "Trump First Term (2017-2021)"),
            ("Second_presidency_of_Donald_Trump", "Trump Second Term"),
            ("Presidency_of_Barack_Obama", "Obama Presidency"),
            ("Presidency_of_George_W._Bush", "George W. Bush Presidency"),
            ("Presidency_of_Bill_Clinton", "Clinton Presidency"),
        ],
    }),

    # ── GEOPOLITICAL EVENTS ──────────────────────────────────────────
    ("geopolitical", {
        "name": "GEOPOLITICAL EVENTS",
        "articles": [
            ("Russo-Ukrainian_War", "Russia-Ukraine War"),
            ("Israel\u2013Hamas_war", "Israel-Hamas War"),
            ("Iraq_War", "Iraq War"),
            ("Syrian_civil_war", "Syrian Civil War"),
            ("War_in_Afghanistan_(2001\u20132021)", "Afghanistan War"),
            ("Iran\u2013United_States_relations", "Iran-US Relations"),
            ("Arab_Spring", "Arab Spring"),
            ("Timeline_of_geopolitical_changes_(2000\u2013present)",
             "Geopolitical Changes 2000-Present"),
            ("Cold_War", "Cold War"),
            ("Korean_War", "Korean War"),
            ("September_11_attacks", "September 11 Attacks"),
            ("War_on_terror", "War on Terror"),
            ("Annexation_of_Crimea_by_the_Russian_Federation",
             "Crimea Annexation (2014)"),
            ("Taiwan_Strait_crises", "Taiwan Strait Crises"),
            ("South_China_Sea_disputes", "South China Sea Disputes"),
            ("North_Korea\u2013United_States_relations",
             "North Korea-US Relations"),
            ("Yemeni_civil_war_(2014\u2013present)", "Yemen Civil War"),
            ("2011_military_intervention_in_Libya", "Libya Intervention 2011"),
            ("Joint_Comprehensive_Plan_of_Action", "Iran Nuclear Deal (JCPOA)"),
            ("China\u2013United_States_relations", "China-US Relations"),
        ],
    }),

    # ── TRADE & TARIFFS ──────────────────────────────────────────────
    ("trade_tariffs", {
        "name": "TRADE & TARIFFS",
        "articles": [
            ("China\u2013United_States_trade_war", "China-US Trade War"),
            ("Tariffs_in_the_first_Trump_administration",
             "Trump Tariffs (2017-2021)"),
            ("Tariffs_in_the_second_Trump_administration",
             "Trump Tariffs (2025-present)"),
            ("Smoot\u2013Hawley_Tariff_Act", "Smoot-Hawley Tariff Act"),
            ("Chicken_tax", "Chicken Tax"),
        ],
    }),

    # ── TRADE ORGANIZATIONS & AGREEMENTS ─────────────────────────────
    ("trade_organizations", {
        "name": "TRADE ORGANIZATIONS & AGREEMENTS",
        "articles": [
            ("World_Trade_Organization", "World Trade Organization"),
            ("General_Agreement_on_Tariffs_and_Trade", "GATT"),
            ("North_American_Free_Trade_Agreement", "NAFTA"),
            ("United_States\u2013Mexico\u2013Canada_Agreement", "USMCA"),
            ("Trans-Pacific_Partnership", "Trans-Pacific Partnership"),
            ("Comprehensive_and_Progressive_Agreement_for_Trans-Pacific_Partnership",
             "CPTPP"),
            ("Regional_Comprehensive_Economic_Partnership", "RCEP"),
            ("Bretton_Woods_Conference", "Bretton Woods Conference"),
            ("International_Monetary_Fund", "IMF"),
            ("World_Bank", "World Bank"),
        ],
    }),

    # ── SANCTIONS ────────────────────────────────────────────────────
    ("sanctions", {
        "name": "SANCTIONS",
        "articles": [
            ("International_sanctions_during_the_Russo-Ukrainian_War",
             "Russia-Ukraine Sanctions"),
            ("United_States_sanctions_against_Iran", "Iran Sanctions"),
            ("Sanctions_against_North_Korea", "North Korea Sanctions"),
            ("United_States_embargo_against_Cuba", "Cuba Embargo"),
            ("Sanctions_during_the_Venezuelan_crisis",
             "Venezuela Sanctions"),
            ("United_States_sanctions", "US Sanctions (Overview)"),
        ],
    }),

    # ── PANDEMIC ─────────────────────────────────────────────────────
    ("pandemic", {
        "name": "PANDEMIC",
        "articles": [
            ("COVID-19_pandemic", "COVID-19 Pandemic"),
            ("Timeline_of_the_COVID-19_pandemic_in_2020",
             "COVID-19 Timeline 2020"),
            ("Economic_impact_of_the_COVID-19_pandemic",
             "COVID-19 Economic Impact"),
            ("COVID-19_pandemic_in_the_United_States",
             "COVID-19 in the United States"),
        ],
    }),

    # ── ENERGY ───────────────────────────────────────────────────────
    ("energy", {
        "name": "ENERGY & OIL",
        "articles": [
            ("2021\u20132023_global_energy_crisis", "2021-2023 Energy Crisis"),
            ("2020_Russia\u2013Saudi_Arabia_oil_price_war",
             "2020 Oil Price War"),
            ("1973_oil_crisis", "1973 Oil Crisis"),
            ("1979_energy_crisis", "1979 Energy Crisis"),
            ("OPEC", "OPEC"),
            ("Peak_oil", "Peak Oil"),
            ("Price_of_oil", "Price of Oil"),
            ("2000s_energy_crisis", "2000s Energy Crisis"),
        ],
    }),

    # ── COMMODITIES ──────────────────────────────────────────────────
    ("commodities", {
        "name": "COMMODITIES (NON-ENERGY)",
        "articles": [
            ("2007\u20132008_world_food_price_crisis",
             "2007-2008 Food Price Crisis"),
            ("2022_food_crises", "2022 Food Crises"),
            ("Silver_Thursday", "Silver Thursday"),
            ("Gold_as_an_investment", "Gold as Investment"),
            ("History_of_gold", "History of Gold"),
            ("Copper", "Copper"),
            ("Lithium", "Lithium"),
        ],
    }),

    # ── US FISCAL POLICY ─────────────────────────────────────────────
    ("us_fiscal", {
        "name": "US FISCAL POLICY",
        "articles": [
            ("2023_United_States_debt-ceiling_crisis",
             "2023 Debt Ceiling Crisis"),
            ("2011_United_States_debt-ceiling_crisis",
             "2011 Debt Ceiling Crisis"),
            ("United_States_fiscal_cliff", "Fiscal Cliff"),
            ("Government_shutdowns_in_the_United_States",
             "US Government Shutdowns"),
            ("Budget_sequestration_in_2013",
             "Sequestration 2013"),
            ("United_States_federal_budget",
             "US Federal Budget"),
        ],
    }),

    # ── US LEGISLATION (ECONOMIC) ────────────────────────────────────
    ("us_legislation", {
        "name": "US ECONOMIC LEGISLATION",
        "articles": [
            ("Tax_Cuts_and_Jobs_Act", "Tax Cuts and Jobs Act (2017)"),
            ("CARES_Act", "CARES Act"),
            ("American_Rescue_Plan_Act_of_2021", "American Rescue Plan"),
            ("Inflation_Reduction_Act", "Inflation Reduction Act"),
            ("CHIPS_and_Science_Act", "CHIPS Act"),
            ("Infrastructure_Investment_and_Jobs_Act",
             "Infrastructure Investment Act"),
            ("Paycheck_Protection_Program", "PPP"),
            ("American_Recovery_and_Reinvestment_Act_of_2009",
             "ARRA (2009 Stimulus)"),
            ("Economic_Stimulus_Act_of_2008", "2008 Stimulus Act"),
        ],
    }),

    # ── US ELECTIONS ──────────────────────────────────────────────────
    ("elections", {
        "name": "US ELECTIONS",
        "articles": [
            ("2024_United_States_presidential_election", "2024 Election"),
            ("2020_United_States_presidential_election", "2020 Election"),
            ("2016_United_States_presidential_election", "2016 Election"),
            ("2012_United_States_presidential_election", "2012 Election"),
            ("2008_United_States_presidential_election", "2008 Election"),
        ],
    }),

    # ── BREXIT & EU ──────────────────────────────────────────────────
    ("brexit", {
        "name": "BREXIT & EU",
        "articles": [
            ("Brexit", "Brexit"),
            ("Timeline_of_Brexit", "Brexit Timeline"),
            ("2000s_European_sovereign_debt_crisis_timeline",
             "Euro Debt Crisis Timeline"),
        ],
    }),

    # ── CHINA ECONOMY ────────────────────────────────────────────────
    ("china_economy", {
        "name": "CHINA ECONOMY",
        "articles": [
            ("Chinese_economic_reform", "Chinese Economic Reform"),
            ("Economy_of_China", "Economy of China"),
            ("Evergrande_Group", "Evergrande"),
            ("Chinese_property_sector_crisis_(2020\u2013present)",
             "Chinese Property Crisis"),
            ("Belt_and_Road_Initiative", "Belt and Road Initiative"),
            ("Made_in_China_2025", "Made in China 2025"),
            ("Renminbi", "Renminbi"),
            ("Economic_history_of_China_before_1912",
             "Economic History of China (Pre-1912)"),
        ],
    }),

    # ── TECHNOLOGY & MARKETS ─────────────────────────────────────────
    ("technology_markets", {
        "name": "TECHNOLOGY & MARKETS",
        "articles": [
            ("History_of_artificial_intelligence",
             "History of Artificial Intelligence"),
            ("AI_boom", "AI Boom"),
            ("History_of_bitcoin", "History of Bitcoin"),
            ("Cryptocurrency", "Cryptocurrency (Overview)"),
            ("Fintech", "Fintech"),
            ("High-frequency_trading", "High-Frequency Trading"),
            ("Algorithmic_trading", "Algorithmic Trading"),
            ("Meme_stock", "Meme Stocks"),
        ],
    }),

    # ── CLIMATE & ESG ────────────────────────────────────────────────
    ("climate_esg", {
        "name": "CLIMATE & ESG",
        "articles": [
            ("Paris_Agreement", "Paris Agreement"),
            ("Kyoto_Protocol", "Kyoto Protocol"),
            ("Carbon_emission_trading", "Carbon Emission Trading"),
            ("Environmental,_social,_and_corporate_governance", "ESG"),
            ("Green_bond", "Green Bonds"),
        ],
    }),

    # ── HOUSING & REAL ESTATE ────────────────────────────────────────
    ("housing", {
        "name": "HOUSING & REAL ESTATE",
        "articles": [
            ("United_States_housing_bubble",
             "US Housing Bubble"),
            ("Mortgage-backed_security", "Mortgage-Backed Securities"),
            ("Collateralized_debt_obligation", "CDOs"),
            ("Credit_default_swap", "Credit Default Swaps"),
            ("United_States_housing_market_correction",
             "US Housing Market Correction"),
        ],
    }),

    # ── LABOR MARKETS ────────────────────────────────────────────────
    ("labor_markets", {
        "name": "LABOR MARKETS",
        "articles": [
            ("Great_Resignation", "Great Resignation"),
            ("Gig_economy", "Gig Economy"),
            ("Unemployment_in_the_United_States",
             "US Unemployment"),
            ("United_States_labor_law", "US Labor Law"),
        ],
    }),

    # ── EMERGING MARKETS ─────────────────────────────────────────────
    ("emerging_markets", {
        "name": "EMERGING MARKETS",
        "articles": [
            ("BRICS", "BRICS"),
            ("Economy_of_India", "Economy of India"),
            ("Economy_of_Brazil", "Economy of Brazil"),
            ("Sri_Lankan_economic_crisis_(2019\u20132024)", "Sri Lanka Economic Crisis"),
            ("Turkish_economic_crisis_(2018\u2013current)",
             "Turkish Economic Crisis (2018-present)"),
            ("Economy_of_South_Africa", "Economy of South Africa"),
            ("Economy_of_Indonesia", "Economy of Indonesia"),
        ],
    }),
])

CATEGORY_ORDER = list(TIMELINE_REGISTRY.keys())


# --- PRISM "State of the World" Design Notes ---------------------------------
#
# PROBLEM
#   Raw Wikipedia articles are 30-100KB each. A single category like
#   geopolitical/ is ~590KB (~150k tokens). Far too large for context
#   injection. For an L2 context module, target is ~3-8k tokens.
#   That implies 10-30x compression from raw scraped content.
#
# TIER CLASSIFICATION
#   Which categories belong in always-on "state of the world" context
#   vs. on-demand reference that PRISM fetches via `get`/`get-category`.
#
#   TIER 1 -- ACTIVE / EVOLVING (candidates for state-of-world context)
#     geopolitical       Active conflicts, alliance shifts
#     trade_tariffs      Current tariff regime
#     sanctions          Active sanctions regimes
#     monetary_policy    Where central banks are in cycle
#     energy             Supply dynamics, OPEC decisions
#
#   TIER 2 -- BACKGROUND / STRUCTURAL (useful on-demand, not always-on)
#     us_fiscal           Debt ceiling, budget posture
#     us_legislation      Active legislation effects
#     china_economy       Structural trajectory
#     emerging_markets    Active crises
#     climate_esg         Policy regime
#
#   TIER 3 -- HISTORICAL REFERENCE (strictly on-demand via `get`)
#     financial_crises    Precedent library
#     recessions          Precedent library
#     market_events       Precedent library
#     currency_fx         Precedent library
#     housing, labor_markets, sovereign_debt, financial_regulation,
#     global_central_banks, inflation_deflation, trade_organizations,
#     technology_markets, us_presidents, elections, brexit, pandemic,
#     commodities
#
# CONDENSATION OPTIONS
#
#   Option A: Curated Markdown (manual / semi-manual)
#     Hand-write and periodically update a concise "sitrep" file per
#     domain. ~500-1000 words each. Lives as a static L2 context module.
#     Updated when things materially change.
#       PRO: Total control over what goes in. Very concise. Cheap,
#            no LLM call at context-build time.
#       CON: Goes stale. Requires manual maintenance.
#       BEST FOR: Tier 2 structural stuff that changes slowly.
#
#   Option B: Runtime Condensation (LLM-generated)
#     A runtime generator reads scraped Wikipedia markdown, feeds it to
#     an LLM with a structured prompt, and produces a concise sitrep.
#     Runs at context-build time or on a schedule (cached).
#       PRO: Always fresh (as fresh as the scrape). Scales to many
#            topics. No manual maintenance.
#       CON: LLM cost per generation. Variable quality. Latency if
#            not pre-cached.
#       BEST FOR: Tier 1 active situations that evolve fast.
#
#   Option C: Hybrid (RECOMMENDED)
#     Hand-designed template with fixed structure (headings, sections).
#     Content within each section is LLM-filled from scraped data.
#     Cached and refreshed weekly alongside the scrape cycle.
#     Example output shape:
#
#       # Geopolitical Situation Report
#       ## Active Conflicts
#         - Russia-Ukraine: [status] [key dates] [market impact]
#         - Israel-Hamas: [status] [key dates] [market impact]
#       ## Trade Regime
#         - US-China: [current tariff levels] [recent actions]
#       ## Sanctions
#         - Russia: [scope] [enforcement trends]
#         - Iran: [scope]
#       ## Monetary Policy Stance
#         - Fed: [rate] [direction] [last action]
#         - ECB/BOJ/BOE: [rate] [direction]
#       ## Energy
#         - Oil: [price context] [OPEC posture]
#
#       PRO: Structured + concise + auto-fresh. Best of both worlds.
#       CON: Template needs designing. Still has LLM cost (but cached).
#       BEST FOR: The main state-of-world module serving Tier 1 content.
#
# STATUS: Not yet implemented. The `catalog`/`get`/`get-category` commands
# serve as the raw data layer. Condensation pipeline TBD.
# -----------------------------------------------------------------------------


def _all_articles():
    """Flat list of (category, wiki_title, display_name) tuples."""
    out = []
    for cat, info in TIMELINE_REGISTRY.items():
        for wiki_title, display in info["articles"]:
            out.append((cat, wiki_title, display))
    return out


def _find_article(query):
    """Find a registered article by wiki title or display name (fuzzy)."""
    q = query.lower().replace(" ", "_").replace("-", "_").replace("\u2013", "_")
    for cat, wt, dn in _all_articles():
        wt_norm = wt.lower().replace("\u2013", "_").replace("-", "_")
        dn_norm = dn.lower().replace(" ", "_").replace("-", "_").replace("\u2013", "_")
        if q == wt_norm:
            return cat, wt, dn
        if q == dn_norm:
            return cat, wt, dn
    for cat, wt, dn in _all_articles():
        wt_norm = wt.lower().replace("\u2013", "_")
        dn_norm = dn.lower().replace(" ", "_")
        if q in wt_norm or q in dn_norm:
            return cat, wt, dn
    return None, query, query


# --- HTML-to-Markdown Converter -----------------------------------------------

class WikiToMarkdown:
    """Converts Wikipedia parsed HTML to clean markdown."""

    def convert(self, html, title=None):
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".mw-parser-output")
        if not root:
            root = soup

        self._clean(root)
        md = self._walk(root)
        md = self._strip_sections(md)
        md = re.sub(r'\n{3,}', '\n\n', md)
        md = md.strip()
        return md

    def _clean(self, soup):
        selectors = [
            ".reference", ".reflist", ".mw-editsection", ".navbox",
            ".toc", ".metadata", ".ambox", ".tmbox", ".shortdescription",
            ".noprint", ".sistersitebox", ".side-box", ".infobox",
            ".mbox-small", ".mw-empty-elt", ".thumb", ".mw-jump-link",
            ".hatnote", ".navigation-not-searchable", ".catlinks",
            ".sidebar", ".vertical-navbox", ".nomobile", ".mw-indicators",
            ".portal", ".authority-control", ".wikitable.collapsible",
            "style", "script", "noscript",
        ]
        for sel in selectors:
            for el in soup.select(sel):
                el.decompose()

        for sup in soup.find_all("sup", class_="reference"):
            sup.decompose()

        from bs4 import Comment
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            comment.extract()

    def _walk(self, node):
        if isinstance(node, NavigableString):
            text = str(node)
            return text
        if not isinstance(node, Tag):
            return ""
        return self._render_tag(node)

    def _render_tag(self, tag):
        name = tag.name

        if name in ("style", "script", "img", "figure", "figcaption",
                     "audio", "video", "noscript"):
            return ""

        if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(name[1])
            text = tag.get_text(strip=True)
            if not text:
                return ""
            return f"\n\n{'#' * level} {text}\n\n"

        if name == "p":
            inner = self._walk_children(tag).strip()
            return f"\n{inner}\n" if inner else ""

        if name in ("ul", "ol"):
            return self._render_list(tag, ordered=(name == "ol"))

        if name in ("b", "strong"):
            inner = self._walk_children(tag).strip()
            return f"**{inner}**" if inner else ""

        if name in ("i", "em"):
            inner = self._walk_children(tag).strip()
            return f"*{inner}*" if inner else ""

        if name == "a":
            return self._walk_children(tag)

        if name == "br":
            return "\n"

        if name == "table":
            return self._render_table(tag)

        if name == "blockquote":
            inner = self._walk_children(tag).strip()
            lines = inner.split("\n")
            return "\n" + "\n".join(f"> {l}" for l in lines) + "\n"

        if name == "dt":
            inner = self._walk_children(tag).strip()
            return f"\n**{inner}**" if inner else ""

        if name == "dd":
            inner = self._walk_children(tag).strip()
            return f"\n: {inner}\n" if inner else ""

        if name == "hr":
            return "\n---\n"

        if name == "sup":
            inner = self._walk_children(tag).strip()
            return inner

        if name == "sub":
            return self._walk_children(tag)

        return self._walk_children(tag)

    def _walk_children(self, node):
        parts = []
        for child in node.children:
            parts.append(self._walk(child))
        return "".join(parts)

    def _render_list(self, node, ordered=False, depth=0):
        items = node.find_all("li", recursive=False)
        if not items:
            return ""
        result = "\n"
        for i, item in enumerate(items, 1):
            text_parts = []
            sub_lists = []
            for child in item.children:
                if isinstance(child, Tag) and child.name in ("ul", "ol"):
                    sub_lists.append(child)
                else:
                    text_parts.append(self._walk(child))

            text = "".join(text_parts).strip()
            if not text and not sub_lists:
                continue
            prefix = "  " * depth
            marker = f"{i}." if ordered else "-"
            result += f"{prefix}{marker} {text}\n"

            for sl in sub_lists:
                result += self._render_list(
                    sl, ordered=(sl.name == "ol"), depth=depth + 1)
        return result

    def _render_table(self, table):
        rows = table.find_all("tr")
        if not rows:
            return ""

        md_rows = []
        max_cols = 0
        for row in rows:
            cells = row.find_all(["th", "td"])
            cell_texts = []
            for c in cells:
                txt = self._walk_children(c).strip()
                txt = txt.replace("|", "/").replace("\n", " ")
                txt = re.sub(r'\s+', ' ', txt)
                cell_texts.append(txt)
            if cell_texts:
                md_rows.append(cell_texts)
                max_cols = max(max_cols, len(cell_texts))

        if not md_rows or max_cols == 0:
            return ""

        for row in md_rows:
            while len(row) < max_cols:
                row.append("")

        lines = []
        for idx, row in enumerate(md_rows):
            lines.append("| " + " | ".join(row) + " |")
            if idx == 0:
                lines.append("| " + " | ".join(["---"] * max_cols) + " |")

        return "\n\n" + "\n".join(lines) + "\n\n"

    def _strip_sections(self, md):
        cut = md.find("\nNewPP limit report")
        if cut != -1:
            md = md[:cut]

        lines = md.split("\n")
        result = []
        skipping = False
        skip_level = 0

        for line in lines:
            m = re.match(r'^(#{1,6})\s+(.+)$', line)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                if title in SKIP_SECTIONS:
                    skipping = True
                    skip_level = level
                    continue
                elif skipping and level <= skip_level:
                    skipping = False

            if not skipping:
                result.append(line)

        return "\n".join(result)


CONVERTER = WikiToMarkdown()


# --- HTTP Layer ---------------------------------------------------------------

def _fetch_parsed_html(title):
    """Fetch parsed HTML for a Wikipedia article via MediaWiki API.
    Returns (display_title, html_string) or (None, None) on failure.
    """
    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text|displaytitle",
        "redirects": "",
        "disabletoc": "",
    }
    try:
        resp = SESSION.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        print(f"    [timeout fetching {title}]")
        return None, None
    except requests.exceptions.ConnectionError:
        print(f"    [connection error fetching {title}]")
        return None, None
    except Exception as e:
        print(f"    [error fetching {title}: {str(e)[:60]}]")
        return None, None

    if "error" in data:
        code = data["error"].get("code", "unknown")
        print(f"    [API error: {code} for {title}]")
        return None, None

    parse = data.get("parse", {})
    display_title = parse.get("displaytitle", title.replace("_", " "))
    display_title = BeautifulSoup(display_title, "html.parser").get_text()
    html = parse.get("text", {}).get("*", "")
    time.sleep(0.5)
    return display_title, html


def _search_wikipedia(query, limit=20):
    """Search Wikipedia for articles matching a query."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    try:
        resp = SESSION.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        time.sleep(0.3)
        return data.get("query", {}).get("search", [])
    except Exception as e:
        print(f"    [search error: {str(e)[:60]}]")
        return []


# --- File Helpers -------------------------------------------------------------

def _sanitize_filename(title):
    name = title.replace("%E2%80%93", "-").replace("%e2%80%93", "-")
    name = name.replace("_", " ")
    name = name.replace("\u2013", "-").replace("\u2014", "-")
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'\s+', '_', name.strip())
    return name.lower() + ".md"


def _output_path(category, wiki_title):
    cat_dir = os.path.join(OUTPUT_DIR, category)
    fname = _sanitize_filename(wiki_title)
    return os.path.join(cat_dir, fname)


def _is_recently_scraped(path, max_age_days=None):
    if max_age_days is None:
        max_age_days = RESCRAPE_DAYS
    if not os.path.exists(path):
        return False
    mtime = os.path.getmtime(path)
    age_days = (time.time() - mtime) / 86400
    return age_days < max_age_days


def _ensure_dir(path):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)


# --- Scraping Logic -----------------------------------------------------------

def scrape_article(wiki_title, display_name=None, category=None):
    """Scrape a single Wikipedia article and return markdown string."""
    label = display_name or wiki_title.replace("_", " ")
    print(f"    Fetching: {label}...", flush=True)

    display_title, html = _fetch_parsed_html(wiki_title)
    if not html:
        return None

    print(f"    Converting ({len(html):,} bytes HTML)...", flush=True)
    body = CONVERTER.convert(html, title=display_title)

    source_url = f"{WIKI_BASE}/{quote(wiki_title, safe='')}"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    header = f"# {display_title}\n\n"
    header += f"> Source: {source_url}\n"
    header += f"> Scraped: {now}\n"
    if category:
        cat_name = TIMELINE_REGISTRY.get(category, {}).get("name", category)
        header += f"> Category: {cat_name}\n"
    header += "\n---\n\n"

    md = header + body
    return md


def save_article(md, path):
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)


# --- PRISM-Facing Commands (clean stdout, status to stderr) -------------------

def _log(msg):
    """Status messages to stderr so stdout stays clean for PRISM."""
    print(msg, file=sys.stderr, flush=True)


def cmd_catalog(category=None):
    """Output clean JSON catalog of all available timelines.
    PRISM calls this to discover what's available before requesting content.
    """
    if category and category not in TIMELINE_REGISTRY:
        _log(f"Unknown category: {category}")
        return

    cats_to_show = [category] if category else CATEGORY_ORDER
    out = {}
    for cat in cats_to_show:
        info = TIMELINE_REGISTRY[cat]
        articles = []
        for wt, dn in info["articles"]:
            path = _output_path(cat, wt)
            entry = {
                "key": wt,
                "display_name": dn,
                "available": os.path.exists(path),
            }
            if os.path.exists(path):
                stat = os.stat(path)
                entry["size_bytes"] = stat.st_size
                entry["lines"] = sum(1 for _ in open(path, encoding="utf-8"))
                entry["scraped_days_ago"] = round(
                    (time.time() - stat.st_mtime) / 86400, 1)
            articles.append(entry)

        scraped = sum(1 for a in articles if a["available"])
        out[cat] = {
            "name": info["name"],
            "total": len(articles),
            "scraped": scraped,
            "articles": articles,
        }

    print(json.dumps(out, indent=2))


def cmd_get(query, scrape_if_missing=True):
    """Output a single timeline's markdown to stdout.
    Finds by wiki title or display name (fuzzy match).
    If not yet scraped, scrapes on-the-fly (unless disabled).
    All status messages go to stderr.
    """
    cat, wt, dn = _find_article(query)
    if cat is None:
        cat = "custom"

    path = _output_path(cat, wt)

    if not os.path.exists(path):
        if not scrape_if_missing:
            _log(f"Not scraped: {dn} ({wt})")
            _log(f"Run: python timelines.py scrape \"{wt}\"")
            return
        _log(f"Not cached, scraping: {dn}...")
        md = scrape_article(wt, display_name=dn, category=cat)
        if md:
            save_article(md, path)
            _log(f"Scraped and cached ({len(md):,} chars)")
        else:
            _log(f"FAILED to scrape: {dn}")
            return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(content)


def cmd_get_category(category, separator="\n\n---\n\n"):
    """Output all scraped timelines in a category to stdout, concatenated.
    Articles that haven't been scraped are skipped (logged to stderr).
    """
    if category not in TIMELINE_REGISTRY:
        _log(f"Unknown category: {category}")
        _log(f"Available: {', '.join(CATEGORY_ORDER)}")
        return

    info = TIMELINE_REGISTRY[category]
    parts = []
    for wt, dn in info["articles"]:
        path = _output_path(category, wt)
        if not os.path.exists(path):
            _log(f"Skipping (not scraped): {dn}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            parts.append(f.read())

    if not parts:
        _log(f"No scraped articles in {info['name']}")
        return

    _log(f"Outputting {len(parts)}/{len(info['articles'])} articles "
         f"from {info['name']}")
    print(separator.join(parts))


# --- Human-Facing Command Functions -------------------------------------------

def cmd_list(category=None, as_json=False):
    if category:
        if category not in TIMELINE_REGISTRY:
            print(f"  Unknown category: {category}")
            print(f"  Available: {', '.join(CATEGORY_ORDER)}")
            return
        info = TIMELINE_REGISTRY[category]
        if as_json:
            print(json.dumps(info, indent=2))
            return
        print(f"\n  {info['name']}")
        print(f"  {'=' * len(info['name'])}")
        for wt, dn in info["articles"]:
            path = _output_path(category, wt)
            status = "scraped" if os.path.exists(path) else "not scraped"
            print(f"    {dn:<45} [{status}]")
        print()
        return

    if as_json:
        out = {}
        for cat, info in TIMELINE_REGISTRY.items():
            out[cat] = {
                "name": info["name"],
                "articles": [{"wiki_title": wt, "display": dn}
                             for wt, dn in info["articles"]],
            }
        print(json.dumps(out, indent=2))
        return

    total = sum(len(info["articles"]) for info in TIMELINE_REGISTRY.values())
    print(f"\n  TIMELINE REGISTRY ({len(TIMELINE_REGISTRY)} categories, "
          f"{total} articles)")
    print("  " + "=" * 60)

    for cat in CATEGORY_ORDER:
        info = TIMELINE_REGISTRY[cat]
        scraped = sum(1 for wt, _ in info["articles"]
                      if os.path.exists(_output_path(cat, wt)))
        count = len(info["articles"])
        print(f"\n  {info['name']} [{cat}]  ({scraped}/{count} scraped)")
        print(f"  {'-' * len(info['name'])}")
        for wt, dn in info["articles"]:
            path = _output_path(cat, wt)
            if os.path.exists(path):
                age = (time.time() - os.path.getmtime(path)) / 86400
                status = f"scraped {age:.0f}d ago"
            else:
                status = "not scraped"
            print(f"    {dn:<45} [{status}]")

    print()


def cmd_scrape(wiki_title, force=False, output_dir=None):
    cat, wt, dn = _find_article(wiki_title)
    if cat is None:
        cat = "custom"

    out_dir = output_dir or OUTPUT_DIR
    path = os.path.join(out_dir, cat, _sanitize_filename(wt))

    if not force and _is_recently_scraped(path):
        age = (time.time() - os.path.getmtime(path)) / 86400
        print(f"  Already scraped {age:.0f}d ago: {dn}")
        print(f"  Use --force to re-scrape.")
        return

    print(f"\n  Scraping: {dn}")
    md = scrape_article(wt, display_name=dn, category=cat)
    if md:
        save_article(md, path)
        lines = md.count("\n") + 1
        print(f"    Saved: {path}")
        print(f"    ({lines} lines, {len(md):,} chars)")
    else:
        print(f"    FAILED: could not scrape {dn}")
    print()


def cmd_scrape_category(category, force=False, output_dir=None):
    if category not in TIMELINE_REGISTRY:
        print(f"  Unknown category: {category}")
        print(f"  Available: {', '.join(CATEGORY_ORDER)}")
        return

    info = TIMELINE_REGISTRY[category]
    articles = info["articles"]
    out_dir = output_dir or OUTPUT_DIR

    print(f"\n  Scraping {info['name']} ({len(articles)} articles)...\n")

    results = {"success": 0, "skipped": 0, "failed": 0}
    for idx, (wt, dn) in enumerate(articles, 1):
        path = os.path.join(out_dir, category, _sanitize_filename(wt))

        print(f"  [{idx}/{len(articles)}] {dn}")

        if not force and _is_recently_scraped(path):
            age = (time.time() - os.path.getmtime(path)) / 86400
            print(f"    Skipped (scraped {age:.0f}d ago)")
            results["skipped"] += 1
            continue

        md = scrape_article(wt, display_name=dn, category=category)
        if md:
            save_article(md, path)
            lines = md.count("\n") + 1
            print(f"    Saved ({lines} lines, {len(md):,} chars)")
            results["success"] += 1
        else:
            print(f"    FAILED")
            results["failed"] += 1

    print(f"\n  Done: {results['success']} saved, "
          f"{results['skipped']} skipped, {results['failed']} failed\n")


def cmd_scrape_all(force=False, output_dir=None):
    all_articles = _all_articles()
    total = len(all_articles)
    out_dir = output_dir or OUTPUT_DIR

    print(f"\n  Scraping ALL timelines ({total} articles across "
          f"{len(TIMELINE_REGISTRY)} categories)...\n")

    results = {"success": 0, "skipped": 0, "failed": 0}
    t0 = time.time()

    for idx, (cat, wt, dn) in enumerate(all_articles, 1):
        path = os.path.join(out_dir, cat, _sanitize_filename(wt))
        cat_name = TIMELINE_REGISTRY[cat]["name"]
        elapsed = time.time() - t0
        rate = idx / elapsed if elapsed > 0 else 0
        remaining = (total - idx) / rate if rate > 0 else 0

        print(f"  [{idx}/{total}] ({cat_name}) {dn}  "
              f"[~{remaining:.0f}s remaining]")

        if not force and _is_recently_scraped(path):
            age = (time.time() - os.path.getmtime(path)) / 86400
            print(f"    Skipped (scraped {age:.0f}d ago)")
            results["skipped"] += 1
            continue

        md = scrape_article(wt, display_name=dn, category=cat)
        if md:
            save_article(md, path)
            lines = md.count("\n") + 1
            print(f"    Saved ({lines} lines, {len(md):,} chars)")
            results["success"] += 1
        else:
            print(f"    FAILED")
            results["failed"] += 1

    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.0f}s: {results['success']} saved, "
          f"{results['skipped']} skipped, {results['failed']} failed\n")


def cmd_search(query, limit=20, as_json=False):
    print(f"\n  Searching Wikipedia for: {query}\n")
    results = _search_wikipedia(query, limit=limit)

    if not results:
        print("  No results found.\n")
        return

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print(f"  {'#':>4}  {'Title':<55} {'Snippet'}")
    print(f"  {'-'*4}  {'-'*55} {'-'*40}")

    for i, r in enumerate(results, 1):
        title = r.get("title", "?")
        snippet = r.get("snippet", "")
        snippet = re.sub(r'<[^>]+>', '', snippet)
        snippet = snippet[:80] + "..." if len(snippet) > 80 else snippet
        print(f"  {i:>4}  {title:<55} {snippet}")

    print(f"\n  {len(results)} results. Use wiki title with 'scrape' command.\n")


def cmd_preview(wiki_title, max_lines=60):
    cat, wt, dn = _find_article(wiki_title)
    if cat:
        path = _output_path(cat, wt)
    else:
        path = os.path.join(OUTPUT_DIR, "custom", _sanitize_filename(wt))

    if not os.path.exists(path):
        print(f"  Not found: {path}")
        print(f"  Scrape first with: scrape \"{wiki_title}\"")
        return

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    total = len(lines)
    show = min(max_lines, total)

    print(f"\n  PREVIEW: {dn} ({total} total lines, showing first {show})")
    print("  " + "=" * 60)
    for line in lines[:show]:
        print(f"  {line}")
    if total > show:
        print(f"\n  ... {total - show} more lines ...")
    print()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   Wikipedia Timeline Scraper
  =====================================================

   BROWSE
     1) list             List all categories and articles
     2) search           Search Wikipedia for articles

   SCRAPE
     3) article          Scrape a single registered article
     4) custom           Scrape any Wikipedia article by title
     5) category         Scrape all articles in a category
     6) all              Scrape all registered articles

   READ (PRISM)
     7) catalog          JSON catalog of available timelines
     8) get              Output a timeline to stdout
     9) get-category     Output all timelines in a category

   VIEW
     10) preview         Preview a scraped markdown file

   q) quit
"""


def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")


def _prompt_choice(msg, choices, default=None):
    choices_str = "/".join(choices)
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {msg} ({choices_str}){suffix}: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return default or choices[0]
    if val and val in choices:
        return val
    return default or choices[0]


def _pick_registered_article():
    """Let user pick from registered articles by number."""
    all_arts = _all_articles()
    print()
    for i, (cat, wt, dn) in enumerate(all_arts, 1):
        cat_name = TIMELINE_REGISTRY[cat]["name"]
        print(f"  {i:>3}) {dn:<45} ({cat_name})")
    print()
    val = _prompt("Article number (or title)")
    if not val:
        return None, None, None
    try:
        idx = int(val) - 1
        if 0 <= idx < len(all_arts):
            return all_arts[idx]
    except ValueError:
        pass
    return _find_article(val)


def _i_list():
    print(f"\n  Categories: {', '.join(CATEGORY_ORDER)}")
    cat = _prompt("Category (or blank for all)", "")
    if cat and cat in TIMELINE_REGISTRY:
        cmd_list(category=cat)
    else:
        cmd_list()


def _i_search():
    query = _prompt("Search query")
    if not query:
        return
    limit = int(_prompt("Max results", "20"))
    cmd_search(query=query, limit=limit)


def _i_article():
    cat, wt, dn = _pick_registered_article()
    if not wt:
        return
    force = _prompt_choice("Force re-scrape?", ["n", "y"], "n") == "y"
    cmd_scrape(wt, force=force)


def _i_custom():
    title = _prompt("Wikipedia article title (exact)")
    if not title:
        return
    title = title.replace(" ", "_")
    force = _prompt_choice("Force re-scrape?", ["n", "y"], "n") == "y"
    cmd_scrape(title, force=force)


def _i_category():
    print(f"\n  Categories: {', '.join(CATEGORY_ORDER)}")
    cat = _prompt("Category")
    if not cat or cat not in TIMELINE_REGISTRY:
        print(f"  Unknown category. Available: {', '.join(CATEGORY_ORDER)}")
        return
    force = _prompt_choice("Force re-scrape?", ["n", "y"], "n") == "y"
    cmd_scrape_category(cat, force=force)


def _i_all():
    force = _prompt_choice("Force re-scrape all?", ["n", "y"], "n") == "y"
    confirm = _prompt_choice(
        f"Scrape {len(_all_articles())} articles? This may take a while",
        ["y", "n"], "y")
    if confirm == "y":
        cmd_scrape_all(force=force)


def _i_catalog():
    print(f"\n  Categories: {', '.join(CATEGORY_ORDER)}")
    cat = _prompt("Category (or blank for all)", "")
    cat = cat if cat and cat in TIMELINE_REGISTRY else None
    cmd_catalog(category=cat)


def _i_get():
    cat, wt, dn = _pick_registered_article()
    if not wt:
        return
    cmd_get(wt)


def _i_get_category():
    print(f"\n  Categories: {', '.join(CATEGORY_ORDER)}")
    cat = _prompt("Category")
    if not cat or cat not in TIMELINE_REGISTRY:
        print(f"  Unknown category. Available: {', '.join(CATEGORY_ORDER)}")
        return
    cmd_get_category(cat)


def _i_preview():
    cat, wt, dn = _pick_registered_article()
    if not wt:
        return
    lines = int(_prompt("Lines to show", "60"))
    cmd_preview(wt, max_lines=lines)


INTERACTIVE_MAP = {
    "1": _i_list,
    "2": _i_search,
    "3": _i_article,
    "4": _i_custom,
    "5": _i_category,
    "6": _i_all,
    "7": _i_catalog,
    "8": _i_get,
    "9": _i_get_category,
    "10": _i_preview,
}


def interactive_loop():
    print(MENU)
    while True:
        choice = _prompt("\n  Command").strip().lower()
        if choice in ("q", "quit", "exit"):
            break
        if choice in INTERACTIVE_MAP:
            try:
                INTERACTIVE_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  [interrupted]")
            except Exception as e:
                print(f"  [error: {e}]")
        else:
            print(f"  Unknown command: {choice}")
            print("  Enter 1-10 or q to quit")


# --- Argparse -----------------------------------------------------------------

def build_argparse():
    p = argparse.ArgumentParser(
        prog="timelines.py",
        description="Wikipedia Timeline Scraper -- scrape, catalog, and serve "
                    "timelines as markdown. PRISM-compatible: catalog/get/get-category "
                    "output clean content to stdout (status to stderr).",
    )
    sub = p.add_subparsers(dest="command")

    # -- PRISM-facing (clean stdout) --
    s = sub.add_parser("catalog",
                       help="[PRISM] JSON catalog of available timelines")
    s.add_argument("--category", "-c", choices=CATEGORY_ORDER,
                   help="Limit to one category")

    s = sub.add_parser("get",
                       help="[PRISM] Output a single timeline's markdown to stdout")
    s.add_argument("title", help="Wiki title or display name (fuzzy match)")
    s.add_argument("--no-scrape", action="store_true",
                   help="Don't auto-scrape if missing")

    s = sub.add_parser("get-category",
                       help="[PRISM] Output all timelines in a category to stdout")
    s.add_argument("category", choices=CATEGORY_ORDER)

    # -- Human-facing --
    s = sub.add_parser("list", help="List categories and articles")
    s.add_argument("--category", "-c", choices=CATEGORY_ORDER,
                   help="Show only this category")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("scrape", help="Scrape a single article")
    s.add_argument("title", help="Wikipedia article title or display name")
    s.add_argument("--force", "-f", action="store_true",
                   help="Re-scrape even if recently done")
    s.add_argument("--output-dir", help="Custom output directory")

    s = sub.add_parser("scrape-category",
                       help="Scrape all articles in a category")
    s.add_argument("category", choices=CATEGORY_ORDER)
    s.add_argument("--force", "-f", action="store_true")
    s.add_argument("--output-dir", help="Custom output directory")

    s = sub.add_parser("scrape-all", help="Scrape all registered articles")
    s.add_argument("--force", "-f", action="store_true")
    s.add_argument("--output-dir", help="Custom output directory")

    s = sub.add_parser("search", help="Search Wikipedia for articles")
    s.add_argument("query", help="Search query")
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("preview", help="Preview scraped markdown")
    s.add_argument("title", help="Article title or display name")
    s.add_argument("--lines", type=int, default=60)

    return p


def run_noninteractive(args):
    if args.command == "catalog":
        cmd_catalog(category=args.category)

    elif args.command == "get":
        cmd_get(args.title, scrape_if_missing=not args.no_scrape)

    elif args.command == "get-category":
        cmd_get_category(args.category)

    elif args.command == "list":
        cmd_list(category=args.category, as_json=args.json)

    elif args.command == "scrape":
        cmd_scrape(args.title, force=args.force,
                   output_dir=args.output_dir)

    elif args.command == "scrape-category":
        cmd_scrape_category(args.category, force=args.force,
                            output_dir=args.output_dir)

    elif args.command == "scrape-all":
        cmd_scrape_all(force=args.force, output_dir=args.output_dir)

    elif args.command == "search":
        cmd_search(args.query, limit=args.limit, as_json=args.json)

    elif args.command == "preview":
        cmd_preview(args.title, max_lines=args.lines)


# --- Main ---------------------------------------------------------------------

def main():
    parser = build_argparse()
    args = parser.parse_args()

    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
