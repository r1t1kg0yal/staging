# API Documentation | U.S. Treasury Fiscal Data

*An official website of the U.S. government — Here's how you know*  
*Home / API Documentation*

> Converted from the uploaded PDF **“API Documentation _ U.S. Treasury Fiscal Data.pdf.”**

---

## Getting Started

The U.S. Department of the Treasury is building a suite of open-source tools to deliver standardized information about federal finances to the public. We are working to centralize publicly available financial data, and this website will include datasets from the Fiscal Service on topics including debt, revenue, spending, interest rates, and savings bonds.

Our API is based on Representational State Transfer, otherwise known as a RESTful API. Our API accepts **GET** requests, returns **JSON** responses, and uses standard HTTP response codes. Each endpoint on this site is accessible through unique URLs that respond with data values and metadata from a single database table.

### What is an API?

API stands for **Application Programming Interface**. APIs make it easy for computer programs to request and receive information in a usable format.

If you're looking for federal financial data that's designed to be read by humans rather than computers, head to our website to search for data (available in **CSV**, **JSON**, and **XML** formats) or visit our partner site, **USAspending** ‒ the official source for spending data for the U.S. Government. There, you can follow the money from congressional appropriations to federal agencies down to local communities and businesses. For more general information, visit **Your Guide to America's Finances**, where Fiscal Data breaks down complex government finance concepts into easy-to-understand terms.

### What is a Dataset?

We present data to you in collections called **datasets**. We define a dataset as a group of data that has historically been published together as one report. In some cases, datasets consist of multiple tables, which correspond to sections of reports. When this is the case, datasets are powered by more than one API. For example, the **Monthly Treasury Statement (MTS)** dataset contains multiple APIs, corresponding with information on federal government spending, revenue, debt, and more.

Search and filter our datasets to explore more.

### API Endpoint URL Structure

For simplicity and consistency, endpoint URLs are formatted with all lower case characters. Underscores are used as word separators. Endpoints use names in singular case.

The components that make up a full API request are below.

**Base URL + Endpoint + Parameters and Filters (optional)**

**BASE URL EXAMPLE:**  
```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
```

**ENDPOINT EXAMPLE:**  
```
v1/accounting/od/rates_of_exchange
```

**PARAMETERS AND FILTERS EXAMPLE:**  
```
?fields=country_currency_desc,exchange_rate,record_date&filter=record_date:gte:2015-01-01
```

**FULL API REQUEST EXAMPLE:**  
```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date&filter=record_date:gte:2015-01-01
```

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 1/11 -->

---

## How to Access our API

Our API is open, meaning that it does not require a user account or registration for a token. To begin using our API, you can type the **GET**, **R**, or **Python** request below directly into a web browser (or script in a data analysis tool), which will return a JSON-formatted response. You can also request CSV- or XML-formatted data by using the `format` filter.

**EXAMPLE API REQUEST USING GET:**  
```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date&filter=country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2024-01-01
```

**EXAMPLE RESPONSE:**  
```json
{
  "data": [
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.426","record_date":"2020-03-31"},
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.26","record_date":"2021-03-31"},
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.275","record_date":"2020-12-31"},
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.368","record_date":"2020-06-30"},
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.239","record_date":"2021-06-30"},
    {"country_currency_desc":"Canada-Dollar","exchange_rate":"1.338","record_date":"2020-09-30"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"19.913","record_date":"2020-12-31"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"23.791","record_date":"2020-03-31"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"23.164","record_date":"2020-06-30"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"20.067","record_date":"2020-09-30"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"20.518","record_date":"2021-03-31"},
    {"country_currency_desc":"Mexico-Peso","exchange_rate":"19.838","record_date":"2021-06-30"}
  ],
  "meta": {
    "count": 12,
    "labels": {
      "country_currency_desc": "Country-CurrencyDescription",
      "exchange_rate": "ExchangeRate",
      "record_date": "RecordDate"
    },
    "dataTypes": {
      "country_currency_desc": "STRING",
      "exchange_rate": "NUMBER",
      "record_date": "DATE"
    },
    "dataFormats": {
      "country_currency_desc": "String",
      "exchange_rate": "10.2",
      "record_date": "YYYY-MM-DD"
    },
    "total-count": 12,
    "total-pages": 1
  },
  "links": {
    "self": "&page%5Bnumber%5D=1&page%5Bsize%5D=100",
    "first": "&page%5Bnumber%5D=1&page%5Bsize%5D=100",
    "prev": null,
    "next": null,
    "last": "&page%5Bnumber%5D=1&page%5Bsize%5D=100"
  }
}
```

**EXAMPLE API REQUEST USING R:**  
```r
library(httr)
library(jsonlite)
request <- "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/mts/mts_table_9?filter=line_code_nbr:eq:120&sort=-record_date&page[size]=1"
response <- GET(request)
out <- fromJSON(rawToChar(response$content))
data <- out$data
head(data)
```

**EXAMPLE API REQUEST USING PYTHON:**  
```python
# MTS Table 1 API - JSON Format
# Import necessary packages
import requests
import pandas as pd

# Create API variables
baseUrl = 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service'
endpoint = '/v1/accounting/mts/mts_table_1'
fields = '?fields=record_date,parent_id,classification_id,classification_desc,current_month_gross_rcpt_amt'
filter = '&filter=record_date:eq:2023-05-31'
sort = '&sort=-record_date'
format = '&format=json'
pagination = '&page[number]=1&page[size]=3'
API = f'{baseUrl}{endpoint}{fields}{filter}{sort}{format}{pagination}'

# Call API and load into a pandas dataframe
data = requests.get(API).json()
pd.DataFrame(data['data'])
```

### License and Authorization

The U.S. Department of the Treasury, Bureau of the Fiscal Service is committed to providing open data as part of its mission to promote the financial integrity and operational efficiency of the federal government. The data is offered free, without restriction, and available to copy, adapt, redistribute, or otherwise use for non‑commercial or commercial purposes.

### API Versioning

Our APIs are currently in **v1.0.0** or **v2.0.0**. To determine which version the API is in, please refer to the specific dataset detail page and navigate to the **API Quick Guide > Endpoint** section.

### Endpoints

Many datasets are associated with only one data table, and thus, one API endpoint. There are some datasets comprised of more than one data table, and therefore have more than one endpoint.

#### List of Endpoints

The table below lists the available endpoints by dataset and data table, along with a brief description of the corresponding endpoint.

> Note that every API URL begins with the base URL:  
> `https://api.fiscaldata.treasury.gov/services/api/fiscal_service`  
> Thus, the full API request URL would be the Base URL + Endpoint. For example:  
> `https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates`

| Dataset | Table Name | Endpoint | Endpoint Description |
|---|---|---|---|
| 120 Day Delinquent Debt Referral Compliance Report | 120 Day Delinquent Debt Referral Compliance Report | `/v2/debt/tror/data_act_compliance` | The 120 Day Delinquent Debt Referral Compliance Report provides access to tracking and benchmarking compliance with the requirements of a key provision of the Digital Accountability and Transparency Act of 2014 (the DATA Act). This table provides quick insights into federal agency compliance rates, as well as information on the number of eligible debts and debts referred or not referred each quarter, beginning in Fiscal Year 2016. |
| Accrual Savings Bonds Redemption Tables (Discontinued) | Redemption Tables | `/v2/accounting/od/redemption_tables` | The Redemption Tables dataset contains monthly tables that list the redemption value, interest earned, and yield of accrual savings bonds purchased since 1941. Each monthly report lists the redemption value of all bonds at the time of publication. Investors and bond owners can use this dataset as an easy and understandable reference to know the redemption value of the bonds they hold. |
| Advances to State Unemployment Funds (Social Security Act Title XII) | Advances to State Unemployment Funds (Social Security Act Title XII) | `/v2/accounting/od/title_xii` | Monthly balances for securities outstanding and principal outstanding for State and Local Government Series (SLGS) securities. |
| Average Interest Rates on U.S. Treasury Securities | Average Interest Rates on U.S. Treasury Securities | `/v2/accounting/od/avg_interest_rates` | Average interest rates for marketable and non-marketable securities. |
| Daily Treasury Statement (DTS) | Operating Cash Balance | `/v1/accounting/dts/operating_cash_balance` | This table represents the Treasury General Account balance. Additional detail on changes to the Treasury General Account can be found in the Deposits and Withdrawals of Operating Cash table. All figures are rounded to the nearest million. |
| Daily Treasury Statement (DTS) | Deposits and Withdrawals of Operating Cash | `/v1/accounting/dts/deposits_withdrawals_operating_cash` | This table represents deposits and withdrawals from the Treasury General Account. A summary of changes to the Treasury General Account can be found in the Operating Cash Balance table. All figures are rounded to the nearest million. |
| Daily Treasury Statement (DTS) | Public Debt Transactions | `/v1/accounting/dts/public_debt_transactions` | This table represents the issues and redemption of marketable and nonmarketable securities. All figures are rounded to the nearest million. |
| Daily Treasury Statement (DTS) | Adjustment of Public Debt Transactions to Cash Basis | `/v1/accounting/dts/adjustment_public_debt_transactions_cash_basis` | This table represents cash basis adjustments to the issues and redemptions of Treasury securities in the Public Debt Transactions table. All figures are rounded to the nearest million. |
| Daily Treasury Statement (DTS) | Debt Subject to Limit | `/v1/accounting/dts/debt_subject_to_limit` | This table represents the breakdown of total public debt outstanding as it relates to the statutory debt limit. All figures are rounded to the nearest million. |
| Daily Treasury Statement (DTS) | Inter-Agency Tax Transfers | `/v1/accounting/dts/inter_agency_tax_transfers` | This table represents the breakdown of inter-agency tax transfers within the federal government. All figures are rounded to the nearest million. |

*Showing 1 - 10 rows of 179 rows*  
*Rows Per Page — 1 2 3 4 18*

### Fields by Endpoint

To discover what fields are available within each endpoint, check out the corresponding dataset’s details page for dataset-specific API documentation, or refer to its data dictionary. Not sure which dataset you need? Head over to our **Datasets** page to search and filter for datasets by topic, dates available, file type, and more.

### Fiscal Service Data Registry

The data registry contains information about definitions, authoritative sources, data types, formats, and uses of common data across the federal government.

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 3–4/11 -->

---

## Methods

All requests will be **HTTP GET** requests. Our APIs accept the GET method, one of the most common HTTP methods. The GET method is used to request data only (not modify). Note that GET requests can be cached, remain in browser history, be bookmarked, and have length restrictions.

## Parameters

Parameters can be included in an API request by modifying the URL. This will specify the criteria to determine which records will be returned, as well as the order and format of the data returned. More information about each parameter can be found below.

Available parameters include:

- **Fields**  
- **Filters**  
- **Sorting**  
- **Format**  
- **Pagination**  

### Fields

**Parameter:** `fields=`

**Definition:** The `fields` parameter allows you to select which field(s) should be included in the response.

**Accepts:** The `fields=` parameter accepts a comma-separated list of field names.

**Required:** No, specifying fields is not required to make an API request.

**Default:** If desired fields are not specified, all fields will be returned.

**Notes:** When a field name passed to the `fields` parameter is not available for the endpoint accessed, an error will occur. Note that omitting fields can result in automatically aggregated and summed data results. For more information, view the full documentation on **Aggregation and Sums**.

**Examples:**

- Only return the following fields from a dataset: `country_currency_desc`, `exchange_rate`, and `record_date`.  
  ```
  ?fields=country_currency_desc,exchange_rate,record_date
  ```

- Return the following fields from the Treasury Reporting Rates of Exchange dataset: `country_currency_desc`, `exchange_rate`, and `record_date`.  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date
  ```

#### Data Types

All fields in a response will be treated as **strings** and enclosed in quotation marks (e.g., `"field_name"`). The data type listed in a dataset's data dictionary or **Fields** table in dataset-specific API documentation indicates what the field is meant to be (e.g., date).

> **Note:** This includes null values, which will appear as strings (`"null"`) rather than a blank or system-recognized null value. This allows you to convert it to that data type in your language of choice. For example, the **Pandas** library for Python helps you convert strings to “datetime objects,” and **R** allows you to convert characters to date objects using `as.Date`.

**Fields by Endpoint**: To discover what fields are available within each endpoint, check out the corresponding dataset's detail page for dataset-specific API documentation or refer to its data dictionary.

Looking for field names for a specific dataset? Jump to the **Endpoints by Dataset** section to find your dataset of interest. Select any dataset name to view that dataset's details, including metadata, data dictionary, a preview table, graphs, and more!

Not sure which dataset you need? Head over to our **Datasets** page to search and filter for datasets by topic, dates available, file type, and more.

### Filters

**Parameter:** `filter=`

**Definition:** Filters are used to view a subset of the data based on specific criteria. For example, you may want to find data that falls within a certain date range, or only show records which contain a value larger than a certain threshold.

**Accepts:** The `filter` parameter accepts filters from the list below, as well as specified filter criteria. Use a colon at the end of a filter parameter to pass a value or list of values. For lists passed as filter criteria, use a comma-separated list within parentheses. Filter for specific dates using the format `YYYY-MM-DD`. To filter by multiple fields in a single request, **do not repeat a filter call**. Instead, apply an additional field to include in the filter separated by a comma, as shown in the following template:  
`&filter=field:prm:value,field:prm:value`

**Required:** No, filters are not required to make an API request.

**Default:** When no filters are provided, the default response will return all fields and all data.

The `filter` parameter accepts the following filters:

- `lt=` Less than  
- `lte=` Less than or equal to  
- `gt=` Greater than  
- `gte=` Greater than or equal to  
- `eq=` Equal to  
- `in=` Contained in a given set  

**Examples:**

- Return data if the fiscal year falls between 2007–2010.  
  ```
  ?filter=reporting_fiscal_year:in:(2007,2008,2009,2010)
  ```

- Return data if the funding type ID is 202.  
  ```
  ?filter=funding_type_id:eq:202
  ```

- From the Treasury Reporting Rates of Exchange dataset,  
  only return specific fields (`country_currency_desc`, `exchange_rate`, `record_date`),  
  only return data on the Canadian Dollar and Mexican Peso, and  
  only return data that falls between January 1, 2020 and the present.  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date&filter=country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2020-01-01
  ```

### Sorting

**Parameter:** `sort=`

**Definition:** The `sort` parameter allows a user to sort a field in ascending (least to greatest) or descending (greatest to least) order.

**Accepts:** The `sort` parameter accepts a comma-separated list of field names.

**Required:** No, sorting is not required to make an API request.

**Default:** When no sort parameter is specified, the default is to sort by the first column listed. Most API endpoints are thus sorted by date in ascending order (historical to most current).

**Notes:** You can nest sorting by passing the `sort=` parameter a comma-separated list.

**Examples:**

- Sort the records returned by date in **descending** order, i.e., starting with the most recent date.  
  ```
  ?sort=-record_date
  ```

- Sort the Treasury Report on Receivables dataset by the `Funding Type ID` field in ascending order, i.e., least to greatest.  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/debt/tror?sort=funding_type_id
  ```

- Nested sorting (year, then month).  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?fields=record_calendar_year,record_calendar_month&sort=-record_calendar_year,-record_calendar_month
  ```

### Format

**Parameter:** `format=`

**Definition:** The `format` parameter allows a user to define the output method of the response (**CSV**, **JSON**, **XML**).

**Accepts:** The `format=` parameter accepts `xml`, `json`, or `csv` as an input.

**Required:** No, format is not required to make an API request.

**Default:** When no format is specified, the default response format is **JSON**.

**Example:**

- Return all data from the **Debt to the Penny** dataset in JSON format.  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?format=json
  ```

### Pagination

**Parameters:** `page[size]=` and `page[number]=`

**Definition:** The page size will set the number of rows that are returned on a request, and page number will set the index for the pagination, starting at 1. This allows the user to paginate through the records returned from an API request.

**Accepts:** Both parameters accept integers.

**Required:** No, neither pagination parameter is required to make an API request.

**Default:** When no sort parameter is specified, the default is to sort by the first column listed. As a result, most API endpoints are sorted by date in ascending order (historical to most current).

**Notes (defaults when not specified):**  
- Page number: **1**  
- Page size: **100**

**Example:**

- From the Treasury Offset Program dataset, return data with 50 records per page, and return the 10th page of data.  
  ```
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/top/top_state?page[number]=10&page[size]=50
  ```

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 5–7/11 -->

---

## Responses and Response Objects

The response will be formatted according to the **Format** input parameter specified in the Format section and will be **json**, **xml** or **csv**. When format is not specified, the default response will be JSON. The response will be **utf-8** and will have **gzip** support.

### Response Codes

| Response Code | Description |
|---|---|
| **200** | OK - Response to a successful GET request |
| **304** | Not modified - Cached response |
| **400** | Bad Request - Request was malformed |
| **403** | Forbidden - API Key is not valid |
| **404** | Not Found - When a non-existent resource is requested |
| **405** | Method Not Allowed - Attempting anything other than a GET request |
| **429** | Too Many Requests - Request failed due to rate limiting |
| **500** | Internal Server Error - The server failed to fulfill a request |

### Meta Object

The `meta` object provides metadata about the resulting payload from your API request. The object will contain the following:

- `count`: Record count for the response.  
- `labels`: Mapping from result field to logical field names.  
- `dataTypes`: Data type for each returned field.  
- `dataFormats`: Size or format for each returned field.  
- `total-count`: Total number of rows available in the dataset.  
- `total-pages`: Total number of pages of data available based on the page size in the meta count response.

**Example Meta Object:**  
```json
"meta": {
  "count": 3790,
  "labels": {
    "country_currency_desc": "Country - Currency Description",
    "exchange_rate": "Exchange Rate",
    "record_date": "Record Date"
  },
  "dataTypes": {
    "country_currency_desc": "STRING",
    "exchange_rate": "NUMBER",
    "record_date": "DATE"
  },
  "dataFormats": {
    "country_currency_desc": "String",
    "exchange_rate": "10.2",
    "record_date": "YYYY-MM-DD"
  },
  "total-count": 3790,
  "total-pages": 1
}
```

### Links Object

The `links` object is an API argument to access the current (`self`), `first`, `previous`, `next`, and `last` page of data. It is suitable for creating URLs under user interface elements such as pagination buttons.

**Example Links Object:**  
```json
"links": {
  "self": "&page%5Bnumber%5D=1&page%5Bsize%5D=-1",
  "first": "&page%5Bnumber%5D=1&page%5Bsize%5D=-1",
  "prev": null,
  "next": null,
  "last": "&page%5Bnumber%5D=1&page%5Bsize%5D=-1"
}
```

### Data Object

The `data` object is the section of the response where the requested data will be returned. The other objects (e.g., `meta`, `links`) are sent to enable use of the requested data. The data object begins with `{"data":`.

### Error Object

If something goes wrong while creating the API response, an **error object** will be returned to the user. The error object will contain the following information:

- **Error:** The error name.  
- **Message:** A detailed explanation of why the error occurred and how to resolve it.

**Example Error Object:**  
```json
{
  "error": "Invalid Query Param",
  "message": "Invalid query parameter 'sorts' with value '[-record_date]'. For more information please see the documentation."
}
```

### Pagination Header

The pagination header will contain the `Link:` header and allows a user to navigate pagination using just the APIs.

```
Link <url first> ; rel="first", <url prev> ; rel="prev"; <url next> ; rel="next"; <url last> ; rel="last"
```

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 8–9/11 -->

---

## Aggregation and Sums

In some cases, using a field list that excludes some of an endpoint’s available fields will trigger automatic aggregation of non-unique rows and summing of their numeric values, etc. You should use this when searching for the sum total of a specific field.

For example, the API call for the sum total of the opening monthly balance within the **Daily Treasury Statement** dataset would read as:

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?fields=record_date,transaction_today_amt
```

Running this API call will yield a sum of all the totals in the selected field. In this case, the call yields the total sum of all opening monthly balances over the course of all dates available in the dataset.

## Examples and Code Snippets

### Fields

For the **Treasury Reporting Rates of Exchange** dataset,  
Return only the following fields: `country_currency_desc`, `exchange_rate`, and `record_date`  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date
```

### Filters

For the **Treasury Reporting Rates of Exchange** dataset,  
return the following fields: `country_currency_desc`, `exchange_rate`, and `record_date`  
return data only for the Canadian Dollar and Mexican Peso  
return data only if the date is on or after January 1, 2020.  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/rates_of_exchange?fields=country_currency_desc,exchange_rate,record_date&filter=country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2020-01-01
```

### Sorting

For the **Debt to the Penny** dataset,  
return the following fields: `record_calendar_year`, `record_calendar_month`  
return the most recent data first, i.e., return data sorted by year (descending order) and then month (descending order)  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?fields=record_calendar_year,record_calendar_month&sort=-record_calendar_year,-record_calendar_month
```

### Format

For the **Debt to the Penny** dataset,  
return all the data  
return the data in JSON format  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny?format=json
```

### Pagination

For the **Treasury Offset Program** dataset,  
return the data on the 10th page, and each page returns 50 records of data  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/debt/top/top_state?page[number]=10&page[size]=50
```

### Aggregation

For the **Daily Treasury Statement** dataset,  
Return the sum of all transactions today amounts for each transaction type on each record date  

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/deposits_withdrawals_operating_cash?fields=record_date,transaction_type,transaction_today_amt
```

### Multi-dimension Datasets

Many Fiscal Data datasets contain multiple tables or APIs, which relate to each other. Please see the **Data Dictionary**, **Data Tables**, **Metadata**, and **Notes & Known Limitations** tabs within the dataset properties section of each dataset page for more information.

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 10/11 -->

---

## Table of Contents

- Help  
- FAQ  
- Contact Us  
- Community Site  
- About Us  
- About Fiscal Data  
- Release Calendar  

## Subscribe to Our Mailing List

## Our Sites

- USAspending

© 2025 Data Transparency  
Accessibility • Privacy Policy • Freedom of Information Act

<!-- Page footer from PDF: 9/20/25, 11:13 PM API Documentation | U.S. Treasury Fiscal Data — Page 11/11 -->
