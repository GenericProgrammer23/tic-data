# TIC data

Tools for locating, streaming, filtering, and exporting **Transparency in Coverage (TiC)** machine-readable files without loading giant payer files into memory.

The primary use case is: give the project a payer TiC file (upload/local path or HTTPS URL), identify an organization by **NPI**, **TIN/EIN**, or **business name**, optionally restrict to CPT/HCPCS/etc. codes, and return the negotiated rates attached to that organization.

## What this MVP does

- Reads `.json` and `.json.gz` TiC in-network files.
- Downloads remote files as a stream to temporary disk rather than RAM.
- Uses streaming JSON parsing (`ijson`) for very large files.
- Matches organizations by NPI, TIN/EIN, or `tin.business_name`.
- Resolves root-level `provider_references` to negotiated rates.
- Also handles files that embed `provider_groups` inside negotiated-rate objects.
- Filters by billing code, billing-code type, place-of-service code, billing class, and negotiated type.
- Exports JSON or flat CSV.
- Reads TiC Table-of-Contents files and finds the in-network URLs associated with matching plans.
- Provides both a command-line interface and a FastAPI service for URL ingestion or file upload.

## Important design choice

TiC in-network files can be extremely large. This project intentionally does **not** call `json.load()` on the whole file. For provider-reference files it makes two streaming passes: one to identify matching provider-group IDs and one to extract the rates tied to those IDs. URL inputs are downloaded to a temporary local file so both passes are possible.

Raw TiC files are ignored by git and are not intended to be committed to this repository.

## Install

```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
# source .venv/bin/activate

pip install -e .
```

For development/tests:

```bash
pip install -e ".[dev]"
pytest
```

## CLI examples

### Local file, organization TIN, specific PT codes

```bash
tic-data extract \
  --file payer-in-network.json.gz \
  --tin 12-3456789 \
  --code 97110 \
  --code 97140 \
  --code 97530 \
  --billing-class professional \
  --format csv \
  --output rates.csv
```

### Remote file, organization NPI

```bash
tic-data extract \
  --url "https://payer.example/in-network.json.gz" \
  --npi 1234567890 \
  --code-type CPT \
  --format json \
  --output rates.json
```

### Find the correct in-network file from a Table of Contents

```bash
tic-data toc \
  --url "https://payer.example/table-of-contents.json" \
  --plan-sponsor-name "Example Employer"
```

The `toc` command can filter by `--plan-name`, `--issuer-name`, `--plan-id`, and/or `--plan-sponsor-name`. Multiple supplied filters are ANDed.

## API

Start the service:

```bash
uvicorn tic_data.service:app --reload
```

Then open `/docs` for Swagger UI.

### Extract from URL

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

Use `POST /extract/url.csv` with the same JSON body for CSV output.

### Upload a file

`POST /extract/upload` as `multipart/form-data` with:

- `file`: `.json` or `.json.gz`
- `organization_json`: e.g. `{"tins":["12-3456789"]}`
- `filters_json`: optional, e.g. `{"billing_codes":["97110"]}`

### Read a Table of Contents

`POST /toc/url`

```json
{
  "url": "https://payer.example/table-of-contents.json",
  "plan_sponsor_name": "Example Employer"
}
```

## Output fields

Rate rows include:

- billing code type/version and billing code
- item/service name and description
- negotiation arrangement
- negotiated type and negotiated rate
- expiration date
- place-of-service codes
- billing class and setting
- billing-code modifiers
- provider-reference IDs or embedded provider details
- additional information when supplied by the payer

The JSON response also includes the publisher metadata, matching provider group IDs, matched provider identifiers, rate count, and a `truncated` flag when the configured result limit is reached.

## Scope / next extensions

This first version focuses on **in-network negotiated rates** and Table-of-Contents discovery. Logical next additions are:

1. payer-specific URL/index adapters when a payer publishes a custom index page;
2. resumable/parallel ingestion for multi-hundred-GB files;
3. DuckDB/Parquet indexing so a downloaded file only has to be parsed once;
4. organization profiles that store a known list of NPIs/TINs;
5. batch comparisons across payers and CPT codes;
6. normalized Excel output for contracting analysis.

## Data handling

TiC machine-readable files are public payer disclosures, but organization identifiers and downloaded source files can still be operationally sensitive. The application writes URL/upload sources only to temporary storage and deletes them when processing is complete. Do not commit downloaded payer files or credentials.
