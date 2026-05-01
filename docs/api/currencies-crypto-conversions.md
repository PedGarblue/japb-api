# Crypto conversion — frontend API guide

How to read Binance-backed spot rates and USD equivalents for cryptocurrencies. Rates are populated by the hourly Celery task (`update_crypto_spot_conversions`) into `CurrencyConversionHistorial` with source `binance_spot`.

## Base URL and authentication

- API prefix: **`/api/v1/`** (see [`japb_api/urls.py`](../../japb_api/urls.py)).
- Default API auth is **JWT**: send  
  `Authorization: Bearer <access_token>`  
  (see [`japb_api/config/common.py`](../../japb_api/config/common.py) — `REST_FRAMEWORK` / `simplejwt`).
- Token endpoints: `POST /api/v1/token/`, `POST /api/v1/token/refresh/`.

The currencies viewset uses **`IsAdminOrReadOnly`**: **GET** is allowed without authentication for safe methods; **writes** require staff. Most apps still send the user JWT for list/detail calls.

---

## Primary endpoint: currencies (includes crypto)

### `GET /api/v1/currencies/`

Returns paginated currencies. Serializer: [`CurrencySerializer`](../../japb_api/currencies/serializers.py).

**Query parameters**

| Parameter       | Example           | Description                                      |
|----------------|-------------------|--------------------------------------------------|
| `asset_kind`   | `crypto`          | Filter to crypto-only (`fiat` also supported). |
| `ordering`     | `name`, `-name`   | Optional; view exposes ordering fields.        |
| `page`, etc.   |                   | Standard pagination (`PAGE_SIZE` from env).      |

**Response fields (per item)**

| Field                             | Type           | Description |
|-----------------------------------|----------------|-------------|
| `id`                              | integer        | Currency primary key. |
| `name`                            | string         | e.g. `BTC`, `ETH`. |
| `symbol`                          | string \| null | Display symbol. |
| `asset_kind`                      | string         | `"fiat"` or `"crypto"`. |
| `default_decimal_places`        | integer        | Hint for formatting amounts. |
| `balance`                         | string         | Sum of the **authenticated user’s** balances in accounts using this currency (formatted). |
| `balance_as_main_currency`       | string \| null | Approximate **USD** total for `balance`; `null` if no rate. |
| `latest_conversion_rate_to_main` | number \| null | Latest historial rate for this currency → USD using `default_conversion_source` (crypto uses `binance_spot` when configured). |

### `GET /api/v1/currencies/{id}/`

Same payload shape for a single currency.

---

## Meaning of `latest_conversion_rate_to_main` (critical for UI)

The backend converts to main currency (USD) as:

**USD amount ≈ balance ÷ `latest_conversion_rate_to_main`**

So the stored rate is **units of that currency per 1 USD** (consistent with VES/EUR), **not** “USD per coin.”

For crypto dashboards that need a **spot-style price** (“USD per 1 BTC”):

```text
usdPerUnit = 1 / latest_conversion_rate_to_main
```

(Only when the rate is non-null and non-zero.)

Treat displayed values as **USDT ≈ USD** for spot quotes.

---

## `GET /api/v1/currency-conversion/` — not used for crypto

[`CurrencyConversionViewSet`](../../japb_api/currencies/views.py) returns a **VES-centric** snapshot (`VES` → `USD` / `EUR`, sources `paralelo` / `bcv`). It does **not** expose `binance_spot` crypto rates.

For crypto rates and USD balances, use **`/api/v1/currencies/`** (optionally `?asset_kind=crypto`).

---

## Example requests

```http
GET /api/v1/currencies/?asset_kind=crypto HTTP/1.1
Host: your-api-host
Authorization: Bearer <access_token>
Accept: application/json
```

```http
GET /api/v1/currencies/12/ HTTP/1.1
Host: your-api-host
Authorization: Bearer <access_token>
Accept: application/json
```

**Illustrative JSON** (shape only; numbers are examples):

```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 12,
      "name": "BTC",
      "symbol": "₿",
      "asset_kind": "crypto",
      "default_decimal_places": 8,
      "balance": "0.50000000",
      "balance_as_main_currency": "25000.00",
      "latest_conversion_rate_to_main": 0.00002
    }
  ]
}
```

If Celery has not written historial yet, `latest_conversion_rate_to_main` and `balance_as_main_currency` may be **`null`** until the next successful hourly run.

---

## Related server behaviour

- Transaction USD helpers use the same historial semantics (`currency_to` matching **USD** by name); see [`convert_transaction_to_usd`](../../japb_api/transactions/utils.py).
- Aggregations such as **cashflow** / **expenses** summaries convert using those rules; there is no separate “crypto-only” conversion endpoint beyond currencies + transactions.
