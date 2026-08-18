# TIC data

A local browser app, API, and CLI for mapping **Transparency in Coverage (TiC)** machine-readable files and extracting negotiated rates for specific provider organizations.

The main workflow is:

1. upload a payer Table-of-Contents/index JSON or provide its URL;
2. TIC data collapses thousands of employer-plan references into a deduplicated list of actual in-network rate files;
3. choose the network/rate file;
4. enter the provider organization's **TIN/EIN, NPI, or business name** and optional CPT/HCPCS filters;
5. extract and export the matching negotiated rates.

## Current capabilities

- Browser UI at `/` for the complete workflow.
- Reads `.json`, `.json.gz`, and `.zip` TiC files.
- Downloads remote files to temporary disk rather than loading them into RAM.
- Uses streaming JSON parsing (`ijson`) for very large disclosures.
- Maps Table-of-Contents files to the actual in-network rate files.
- Deduplicates signed URLs by canonical path, which is important for payer indexes such as Cigna's.
- Builds a user-facing network catalog with:
  - normalized network/file name;
  - source classification (payer vs shared/affiliate network);
  - file format;
  - plan types;
  - number of plan sponsors referencing the rate file;
  - sample plan sponsors.
- Matches providers by NPI, TIN/EIN, or `tin.business_name`.
- Treats punctuated and unpunctuated TINs as equivalent; for example, `12-3456789` and `123456789` match the same provider value.
- Resolves root-level `provider_references` and embedded `provider_groups`.
- Filters rates by billing code, billing-code type, place of service, billing class, and negotiated type.
- Provides extraction diagnostics when a search returns zero rows.
- JSON and CSV output.
- CLI and FastAPI endpoints for automation.

## Install and run the browser app

Python 3.11+ is required.

The easiest Windows option is the standalone `Run_TIC_Data.py` launcher. It downloads/updates the application, prepares its private Python environment, starts the server, and opens the browser.

Manual setup is also supported:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e .
uvicorn tic_data.service:app --reload
```

macOS/Linux:

```bash
source .venv/bin/activate
pip install -e .
uvicorn tic_data.service:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```

The API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

## Using a Cigna index

Cigna's index is a Table-of-Contents file, not the negotiated-rate file itself. One index can contain tens of thousands of employer-plan rows that repeatedly reference a much smaller set of actual rate files.

In the browser:

1. **Load a payer index** — upload the Cigna index JSON or paste its URL.
2. TIC data scans the index and displays the unique rate files/networks once.
3. Filter by plan type such as `OAP`, `Local Plus`, `HMO`, or `PPO`, or search the network name.
4. Deliberately select the network you want to query. The app does not silently choose the first Cigna/affiliate file for you. For a standard OAP comparison, start by filtering/searching for **National OAP**; use Pathwell, regional, or affiliate networks only when that is the network you intend to analyze.
5. Enter your provider TIN/EIN and/or NPI. A TIN may be entered as either `12-3456789` or `123456789`; punctuation is ignored during matching.
6. Enter a billing code and type a comma or press Enter. Each accepted code appears as a removable chip so you can confirm exactly what will be searched.
7. Click **Find negotiated rates**.
8. Review the results and download CSV.

The application preserves the current signed URL from the index for downloading, while using a signature-free canonical URL only for deduplication.

## Troubleshooting zero results

When a search completes with zero rates, expand **Troubleshooting details**. TIC data now reports the major stages of the extraction so you can identify where the match stopped:

- **Requested codes seen** — confirms whether the selected rate file actually contains the CPT/HCPCS codes you requested.
- **Provider groups matched** — confirms whether the TIN/NPI/business name matched the provider data in the file.
- **Service rows after filters** — shows whether code type or other service-level filters excluded the requested services.
- **Rate groups linked to provider** — confirms whether the payer linked the matched provider group to a negotiated-rate record for the requested code.
- **Price rows after filters** — confirms whether billing class, place of service, or negotiated-type filters removed the remaining prices.
- **Billing classes present** — shows the classes actually found on linked prices; if the app is filtering for `professional` and only `institutional` is present, set Billing class to **any** and retry.

A useful troubleshooting order is:

1. verify the normalized TIN shown by the app;
2. confirm **Requested codes seen** contains your requested code;
3. confirm **Provider groups matched** is greater than zero;
4. if the provider matched but no rate groups were linked, try another network variant from the index;
5. if rate groups were linked but price rows are zero, set Billing class to **any** and retry;
6. if the TIN does not match, try the organization's Type 2 NPI and then the business name to determine how the payer represented the provider.

## Direct rate-file upload

If you already downloaded an in-network MRF, you can skip the index step. The browser accepts:

- `.json`
- `.json.gz`
- `.zip`

Enter the provider identifiers and codes, upload the rate file under **Direct rate-file upload**, and search it locally.

For ZIP archives, TIC data selects the largest JSON/JSON.GZ member, which matches the normal payer pattern of one large MRF plus small metadata/readme files.

## CLI

### Build a compact catalog from a payer index

```bash
tic-data catalog \
  --file 2026-08-01_cigna-health-life-insurance-company_index.json \
  --plan-name OAP
```

Optional index filters:

- `--plan-name`
- `--issuer-name`
- `--plan-id`
- `--plan-sponsor-name`

EIN plan IDs are compared without punctuation, so `59-1031071` and `591031071` match.

### Extract rates from an actual rate file

```bash
tic-data extract \
  --url "https://payer.example/in-network.json.gz" \
  --tin 12-3456789 \
  --code 97110 \
  --code 97140 \
  --code 97530 \
  --billing-class professional \
  --format csv \
  --output rates.csv
```

A local ZIP works the same way:

```bash
tic-data extract \
  --file payer-in-network.zip \
  --npi 1234567890 \
  --code 97110
```

## API

### Catalog an index URL

`POST /catalog/url`

```json
{
  "url": "https://payer.example/index.json",
  "plan_name": "OAP"
}
```

### Upload an index

`POST /catalog/upload` as multipart form data with `file` and optional plan filters.

### Extract from a rate-file URL

`POST /extract/url`

```json
{
  "url": "https://payer.example/in-network.json.gz",
  "organization": {
    "tins": ["12-3456789"],
    "npis": [],
    "business_names": []
  },
  "filters": {
    "billing_codes": ["97110", "97140", "97530"],
    "billing_code_types": ["CPT"],
    "billing_classes": ["professional"],
    "service_codes": [],
    "negotiated_types": [],
    "limit": 5000
  }
}
```

Extraction responses include a `diagnostics` object in addition to the matching providers and rate rows.

Use `POST /extract/url.csv` for CSV output.

### Upload a rate file

`POST /extract/upload` as multipart form data with:

- `file`
- `organization_json`, e.g. `{"tins":["12-3456789"]}`
- optional `filters_json`, e.g. `{"billing_codes":["97110"]}`

## Large-file behavior

National payer files can be many gigabytes. URL inputs are downloaded to temporary disk because provider-reference MRFs generally require more than one streaming pass: first to determine which provider group IDs belong to the organization, then to find the negotiated rates referencing those groups.

This avoids loading the full MRF into RAM, but the initial download can still be large and slow. A future persistent DuckDB/Parquet cache would make repeated queries against the same payer file substantially faster.

## Output

Rate rows include:

- billing code type/version and billing code;
- item/service name and description;
- negotiation arrangement;
- negotiated type and negotiated rate;
- expiration date;
- place-of-service codes;
- billing class and setting;
- billing-code modifiers;
- provider-reference IDs or embedded provider details;
- additional payer information when supplied.

## Data handling

Downloaded URL sources and uploaded files are written only to temporary storage during a request and removed afterward. Raw payer MRFs are ignored by git and should not be committed to the repository.
