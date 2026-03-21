# Dashboard Design for Analysts

**User:** Ritik Goyal (goyalritik2000@gmail.com)  
**Created:** 3/20/2026 18:19:49  
**Updated:** 3/20/2026 18:21:51  
**Exported:** 3/20/2026 22:25:30  
**Link:** [https://chatgpt.com/c/69bdc804-b390-832b-a6ff-86280ebe3eb1](https://chatgpt.com/c/69bdc804-b390-832b-a6ff-86280ebe3eb1)  

## Prompt:
Okay, so I'm a growth macro analyst now. I want to build four dashboards, each for different purposes, and I'll obviously discuss what each of those should look like. The thing I'm looking for is:
- a leading indicators dashboard
- a macro lead-lags dashboard
- a short rates dashboard
- a rates relative value dashboard

What is the set of exhibits? These have to be entirely quantitative, which means no really textual, subjective interpretation, but should make use of significant gradient conditional formatting of cells, charts, and interactivity. It should be in HTML, with interactivity (sliders, etc.) to be able to really just play with the thing that's being laid fully formed. I want this to look like, but for example, in the leading indicators one, it should really just be a way to browse and weigh and net the entire universe of leading indicators. Sort through them, filter them, chart them, see the percentile ranks, where they stack up, so useful tables, drop-downs for sorting, etc., really full-fledged.

Don't worry about the formatting; it's more like a core few principles. It has to be entirely quantitative, meaning objective information to achieve tables, charts, and interactivity. We should have a formatting or style guideline at some point, but for now we're not worried about that.

I want to imagine what those four dashboards look like that deliver a way to really see a ton of information about those subjects in a really great way.

## Response:
Below is a practical exhibit set for each dashboard, designed for HTML delivery with strong interactivity and fully quantitative content.

The governing idea should be: each dashboard has one **scan layer**, one **diagnostic layer**, and one **drilldown layer**. That gives you a fast read, then context, then analytical depth.

Shared design principles across all four dashboards
---------------------------------------------------

Every dashboard should have the same structural backbone:

**Top control bar**

*   Geography
*   Frequency
*   Sample window
*   Z-score / percentile / level toggle
*   Real-time latest vs history mode
*   Smoothing window
*   Lookback window
*   Regime filter
*   Export / snapshot / reset filters

**Left filter rail**

*   Asset class or indicator family
*   Sector
*   Cyclicality bucket
*   Survey vs hard data
*   Nominal vs real
*   Level / change / diffusion / breadth
*   Lead length
*   Signal direction
*   Volatility / reliability screen

**Main body layout**

*   Summary tiles
*   Ranked heatmap table
*   Time-series panel
*   Cross-section panel
*   Correlation / lead-lag / beta panel
*   Drilldown detail panel

**Core visual grammar**

*   Strong gradient fills for percentile rank, z-score, recent momentum, surprise, dispersion, and conviction
*   Sparklines in tables
*   Scatterplots with selectable axes
*   Term structure / curve charts where relevant
*   Rolling windows via sliders
*   Hover tooltips with exact definitions and latest values
*   Click-through from aggregate to component level

**Quantitative-only rule**  
Every exhibit should show one or more of:

*   level
*   change
*   rate of change
*   percentile
*   z-score
*   breadth
*   hit rate
*   correlation
*   beta
*   lead / lag
*   carry / rolldown
*   volatility
*   drawdown
*   regime conditional performance

No text interpretation panel is needed.

* * *

1) Leading Indicators Dashboard
===============================

This should function like a **marketplace of leading signals**. The user should be able to browse the universe, rank signals, filter by category, and build custom composites.

A. Summary exhibits
-------------------

### 1\. Leading Indicator Scoreboard

A top tile strip with:

*   Composite leading indicator score
*   Breadth of improving signals
*   Breadth of deteriorating signals
*   Median percentile rank across the universe
*   3m change in composite
*   Diffusion index
*   Signal dispersion
*   Number of indicators at extreme percentiles

Each tile clickable into constituent indicators.

### 2\. Indicator Breadth Heatmap

Rows:

*   Indicator families: housing, labor, credit, money, manufacturing, surveys, trade, consumption, sentiment, financial conditions, market-based

Columns:

*   current percentile
*   1m change
*   3m change
*   6m trend
*   volatility-adjusted momentum
*   signal reliability score

Color scaling should be aggressive and intuitive.

### 3\. Leading Composite History Panel

Interactive chart with:

*   user-defined composite
*   benchmark growth series overlaid
*   recession or slowdown shading
*   toggle between level, YoY, z-score, percentile

Add banding for top/bottom historical quintiles.

* * *

B. Universe browsing exhibits
-----------------------------

### 4\. Master Indicator Table

This is the heart of the dashboard.

Columns:

*   Indicator name
*   Category
*   Region
*   Release lag
*   Latest value
*   1m / 3m / 6m change
*   Percentile rank
*   Z-score
*   Signal direction
*   Lead to target growth series
*   Rolling correlation
*   Stability score
*   False-positive rate
*   Last inflection date
*   Sparkline

Interactions:

*   sort any column
*   multi-select filters
*   search
*   pin favorites
*   create watchlist
*   hide inactive series
*   slider for minimum lead length
*   slider for minimum reliability

### 5\. Signal Distribution Panel

Histogram / KDE of current percentile ranks across all indicators, with filters by family and region.

Useful for seeing whether strength is broad or narrow.

### 6\. Indicator Extremes Table

Two side-by-side ranked lists:

*   strongest indicators
*   weakest indicators

Each with:

*   percentile
*   3m delta
*   lead length
*   hit rate
*   mini sparkline

* * *

C. Analytical exhibits
----------------------

### 7\. Lead vs Reliability Scatterplot

X-axis:

*   optimal lead to target variable

Y-axis:

*   historical reliability or out-of-sample hit rate

Bubble size:

*   economic importance or user-defined weight

Bubble color:

*   current signal strength

This is a very useful portfolio-construction style exhibit.

### 8\. Indicator Correlation Network / Matrix

Matrix of pairwise correlation across indicators or families.

Allow toggles:

*   contemporaneous correlation
*   correlation at best lead
*   rolling 3-year / 5-year / full sample

This helps identify redundancy.

### 9\. Lead Profile Panel

For a selected indicator:

*   cross-correlation curve against GDP / industrial production / payrolls / PMIs / inflation
*   optimal lead highlighted
*   stability of lead over rolling windows

### 10\. Signal Regime Performance Table

For each indicator:

*   average target growth outcome after signal enters top quintile
*   average outcome after bottom quintile
*   hit rate
*   median lead
*   average drawdown between signal and target outcome

### 11\. Custom Composite Builder

The key interactive feature.

User can:

*   include/exclude indicators
*   assign weights manually
*   equal-weight / inverse-vol / reliability-weight / PCA-weight schemes
*   set winsorization and smoothing
*   specify sign direction
*   backtest composite against target macro series

Outputs:

*   composite history
*   breadth contribution
*   rolling correlation to target
*   marginal contribution of each component

### 12\. Contribution Decomposition

Stacked bar or waterfall showing contribution to composite change by category or individual indicator.

* * *

2) Macro Lead-Lags Dashboard
============================

This dashboard should answer: **what leads what, by how much, and how stable is that relationship?**

A. Summary exhibits
-------------------

### 1\. Lead-Lag Matrix

Rows:

*   drivers: financial conditions, credit, housing, inventories, labor, policy, commodities, FX, rates, equities, sentiment

Columns:

*   targets: GDP, consumption, capex, payrolls, unemployment, core inflation, goods inflation, services inflation, PMIs

Cells:

*   best lead length
*   best correlation
*   sign
*   p-value or confidence score
*   stability score

Cell shading should encode both sign and strength.

### 2\. Current Macro Sequence Tracker

A visual sequencing exhibit showing the current position of major macro blocks:

*   financial conditions
*   housing
*   manufacturing
*   labor
*   inflation
*   earnings
*   policy

Each block has:

*   percentile
*   momentum
*   inferred stage in cycle
*   relative timing versus other blocks

Still fully quantitative if shown as relative position and timing metrics rather than text labels.

* * *

B. Structural relationship exhibits
-----------------------------------

### 3\. Cross-Correlation Explorer

For selected driver and target:

*   full lead-lag correlation function
*   positive and negative lead ranges
*   rolling best lead
*   confidence interval bands

Add a slider for sample start date.

### 4\. Rolling Lead Stability Chart

For the selected pair:

*   lead length over time
*   rolling max correlation over time

This is essential because static lead relationships often break.

### 5\. Directed Heatmap by Horizon

Instead of one lead number, show correlations at:

*   1m
*   3m
*   6m
*   9m
*   12m
*   18m

Useful for mapping where the strongest horizon sits.

### 6\. Event-Aligned Sequence Chart

For cycle peaks, troughs, or tightening episodes:

*   align variables around event date
*   show average path before/after event
*   compare current cycle path to historical median

Quantitative and highly useful.

* * *

C. Breadth and causality-like diagnostics
-----------------------------------------

### 7\. Breadth of Leads Panel

For a target series, show:

*   how many drivers lead it positively
*   how many lead it negatively
*   median lead
*   median correlation
*   share of statistically meaningful leads

### 8\. Lead Consensus Table

For each target:

*   top 10 leading series by correlation
*   median lead
*   rolling stability
*   current percentile
*   current implied direction

### 9\. Change-on-Change Table

A matrix of:

*   level vs level
*   first difference vs first difference
*   second derivative vs first difference
*   surprise vs target change

This matters because many macro relationships work better in changes than levels.

### 10\. Regime-Conditional Lead Matrix

Same lead-lag matrix, but conditional on:

*   rising inflation regime
*   falling inflation regime
*   tightening cycle
*   easing cycle
*   high vol
*   low vol
*   recession / expansion

This should be filterable.

### 11\. Cluster Map / Dendrogram

Cluster drivers and targets by similarity of timing structure. This helps identify macro blocks that move together or in sequence.

### 12\. Forecast Mapping Panel

For a selected target, convert signals from multiple leading drivers into:

*   weighted implied direction
*   weighted implied percentile
*   distribution of lead horizons
*   uncertainty band from relationship instability

No narrative required.

* * *

3) Short Rates Dashboard
========================

This should be the **operating dashboard for front-end rates**, centered on policy expectations, curve structure, repricing, and macro linkage.

A. Summary exhibits
-------------------

### 1\. Front-End Scoreboard

Top tiles:

*   current policy rate
*   implied terminal
*   number of cuts/hikes priced over next 12m
*   2s yield
*   1y1y, 1y2y, 2y1y forwards
*   front-end realized vol
*   policy uncertainty index
*   nearest meeting implied move

### 2\. Meeting-by-Meeting Pricing Table

Rows:

*   policy meetings

Columns:

*   meeting date
*   implied rate
*   implied hike/cut probability
*   incremental change since prior meeting
*   1d / 1w / 1m repricing
*   percentile of historical meeting pricing

This is one of the most important tables.

### 3\. Front-End Curve Strip Chart

Interactive line chart for:

*   OIS strip
*   futures strip
*   last day / week / month overlays
*   scenario overlays

Slider for horizon out to 24m or 36m.

* * *

B. Curve and forwards exhibits
------------------------------

### 4\. Short-End Term Structure Grid

Rows:

*   tenors or contract points

Columns:

*   yield
*   change
*   z-score
*   percentile
*   carry
*   rolldown
*   realized vol
*   slope to next point
*   butterfly positioning

Strong conditional formatting.

### 5\. Forward Curve Explorer

Plot:

*   OIS forwards
*   FRA/OIS
*   cash-futures or swap-cash equivalents where relevant
*   policy path comparison to historical episodes

### 6\. Repricing Waterfall

Contribution of:

*   terminal repricing
*   timing repricing
*   meeting premium
*   macro data surprise window
*   central bank event window

Even if approximate, this can be fully quantitative.

### 7\. Slope and Curvature Panel

Metrics:

*   3m-6m
*   6m-1y
*   1y-2y
*   front-end butterflies
*   PCA loadings: level, slope, curvature

Display current percentile and recent change.

* * *

C. Macro linkage and regime exhibits
------------------------------------

### 8\. Short Rates vs Macro Scatter Matrix

Selectable x/y combinations:

*   front-end yields vs CPI
*   front-end yields vs payrolls
*   front-end yields vs PMIs
*   front-end yields vs unemployment
*   front-end yields vs growth surprise index

Allow:

*   contemporaneous
*   lead
*   lag
*   regime filter

### 9\. Data Surprise Sensitivity Table

Rows:

*   CPI, payrolls, retail sales, ISM, claims, wages, GDP, core PCE

Columns:

*   average 2y move
*   average 1y1y move
*   average terminal repricing
*   response asymmetry by sign of surprise
*   hit rate
*   current rolling beta

### 10\. Policy Function Proxy Panel

A quantitative policy reaction exhibit:

*   implied policy path vs fitted path from inflation/growth/labor inputs
*   residual gap
*   rolling fit quality

### 11\. Volatility and Uncertainty Dashboard

Exhibits:

*   realized vol
*   implied vol if available
*   vol term structure
*   event premium around meetings
*   rate move distribution by macro regime

### 12\. Historical Analog Explorer

Select current front-end configuration and pull historical closest matches by:

*   level
*   slope
*   priced cuts/hikes
*   inflation backdrop
*   unemployment backdrop

Then show subsequent 1m / 3m / 6m outcomes.

* * *

4) Rates Relative Value Dashboard
=================================

This should help identify **cheap/rich conditions, carry/rolldown opportunities, cross-market dislocations, and residuals versus fitted curves/models**.

A. Summary exhibits
-------------------

### 1\. RV Opportunity Scoreboard

Top tiles:

*   richest point on curve
*   cheapest point on curve
*   best carry-adjusted RV
*   best rolldown-adjusted RV
*   biggest cross-market dislocation
*   swap spread extreme
*   fly extreme
*   z-score breadth of dislocations

### 2\. Rich/Cheap Heatmap

Rows:

*   maturities or structures

Columns:

*   vs spline fitted curve
*   vs PCA fitted curve
*   vs historical regression fair value
*   z-score
*   percentile
*   carry-adjusted score
*   vol-adjusted score

### 3\. Opportunity Ranking Table

Columns:

*   trade structure
*   current spread
*   z-score
*   percentile
*   carry
*   rolldown
*   vol
*   Sharpe-like score
*   max historical excursion
*   half-life of mean reversion
*   current regime fit

Sortable and filterable.

* * *

B. Curve and structure exhibits
-------------------------------

### 4\. Fitted vs Actual Curve Panel

Show:

*   actual yield curve
*   fitted curve
*   residuals by maturity

Model toggles:

*   spline
*   Nelson-Siegel-Svensson
*   PCA reconstruction
*   macro-fair-value model

### 5\. Residual Heatmap by Tenor

A matrix of current residuals across:

*   nominal
*   real
*   OIS
*   swaps
*   govies

Gradient formatting should highlight mispricings instantly.

### 6\. Fly and Butterfly Explorer

For selectable 3-leg structures:

*   current fly
*   history
*   z-score
*   percentile
*   carry
*   rolldown
*   realized beta to curve level moves

### 7\. Cross-Market Relative Value Matrix

Rows and columns:

*   USD, EUR, GBP, CAD, AUD, NZD, JPY or your chosen universe

Cells:

*   spread differential
*   policy-adjusted spread
*   inflation-adjusted spread
*   hedged carry differential
*   z-score

### 8\. Swap Spread Dashboard

Rows:

*   tenors

Columns:

*   swap spread level
*   percentile
*   z-score
*   1m / 3m change
*   beta-adjusted residual
*   funding / liquidity proxy relation

* * *

C. Trade-quality and robustness exhibits
----------------------------------------

### 9\. Carry-Rolldown vs Rich/Cheap Scatterplot

X-axis:

*   rich/cheap score

Y-axis:

*   carry + rolldown

Bubble size:

*   liquidity or DV01

Bubble color:

*   mean reversion half-life or vol-adjusted expected value

This is one of the best decision exhibits in the whole platform.

### 10\. Mean Reversion Diagnostics Panel

For selected trade:

*   half-life
*   frequency of zero-crossing
*   rolling z-score
*   conditional reversion probability
*   distribution of 1m / 3m forward returns after extreme entry

### 11\. Regime-Conditional RV Table

For each structure:

*   mean reversion strength in risk-on / risk-off
*   tightening / easing
*   high vol / low vol
*   inflation up / down

### 12\. PCA Residual Monitor

Show fitted moves from level/slope/curvature factors versus actual moves, isolating idiosyncratic dislocations.

### 13\. Relative Value Backtest Panel

For selected structure:

*   entry rule based on z-score percentile
*   holding horizon slider
*   stop-loss / take-profit sliders
*   carry included toggle
*   return distribution
*   hit rate
*   max drawdown
*   turnover

### 14\. Trade Map / Opportunity Surface

A 2D grid where users choose:

*   entry threshold
*   holding period

Output cells show:

*   median return
*   hit rate
*   Sharpe-like metric
*   drawdown

Very useful for parameter exploration.

* * *

Recommended dashboard page architecture
=======================================

For each of the four dashboards, I would use the same page template:

Header row
----------

*   Dashboard title
*   Global filters
*   Saved views
*   Download data / image / HTML state

Row 1: fast read
----------------

*   4 to 8 summary KPI tiles
*   one compact breadth heatmap

Row 2: primary exhibit
----------------------

*   large master table or matrix
*   sortable, filterable, exportable

Row 3: diagnostic charts
------------------------

*   one large time-series chart
*   one cross-sectional chart
*   one scatter or matrix panel

Row 4: drilldown
----------------

*   clicked-series detail panel
*   history
*   relationships
*   decomposition
*   event study

Footer utility row
------------------

*   definitions popover
*   transform selector
*   normalization selector
*   latest update stamps

* * *

Interactivity that matters most
===============================

For HTML, the most valuable controls are:

*   date range slider
*   rolling window slider
*   smoothing dropdown
*   transform dropdown: level / diff / YoY / z-score / percentile
*   single-click drilldown from table to chart
*   shift-click multi-select for comparison
*   hover tooltips with exact values and definitions
*   sort and rank everywhere
*   compare current to historical analogs
*   custom watchlists
*   custom composite builder
*   scenario sliders where applicable

Avoid gimmicks. The highest-value interactivity is always:

1.  filter,
2.  sort,
3.  rank,
4.  compare,
5.  drill down.

* * *

Minimum viable exhibit set by dashboard
=======================================

If you want each dashboard to feel full-fledged without being overloaded, I would start with this minimum set:

Leading indicators
------------------

*   Summary scoreboard
*   Master indicator table
*   Breadth heatmap
*   Composite history chart
*   Lead vs reliability scatter
*   Custom composite builder
*   Selected-indicator lead profile

Macro lead-lags
---------------

*   Lead-lag matrix
*   Cross-correlation explorer
*   Rolling lead stability chart
*   Regime-conditional matrix
*   Event-aligned sequence chart
*   Lead consensus table

Short rates
-----------

*   Front-end scoreboard
*   Meeting-by-meeting pricing table
*   OIS / futures strip chart
*   Slope-curvature panel
*   Data surprise sensitivity table
*   Historical analog explorer

Rates relative value
--------------------

*   RV scoreboard
*   Rich/cheap ranking table
*   Fitted vs actual curve panel
*   Carry/rolldown vs rich/cheap scatter
*   Fly explorer
*   Mean reversion diagnostics panel
*   RV backtest panel

* * *

Best way to think about the four dashboards together
====================================================

They should fit into one analytical chain:

*   **Leading indicators dashboard**: what is turning first?
*   **Macro lead-lags dashboard**: what tends to follow, and on what horizon?
*   **Short rates dashboard**: how is the front end pricing the path?
*   **Rates RV dashboard**: where are the relative dislocations and tradable residuals?

That gives you a coherent system rather than four disconnected tools.

The next useful step is to turn this into a **dashboard specification document** with, for each exhibit:

*   exact title
*   purpose
*   chart type
*   required fields
*   default transform
*   key interactions
*   priority level

I can draft that spec next in a way that is directly translatable into an HTML build.



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)