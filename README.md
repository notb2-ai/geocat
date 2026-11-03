# RunetFreedom Lite — GeoSite for v2rayNG

This repository produces **minimal, lossless subsets** of [RunetFreedom's GeoSite and GeoIP databases](https://github.com/runetfreedom/russia-v2ray-rules-dat). Original selected category payloads are copied byte-for-byte, preserving matching behavior.

## Download

- **[geosite.dat](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geosite.dat)** — ready-to-use Xray/V2Ray GeoSite database
- **[geoip.dat](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geoip.dat)** — ready-to-use GeoIP database containing **only** `private`
- [geosite.dat.json](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geosite.dat.json) and [geoip.dat.json](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geoip.dat.json) — source release, SHA-256, sizes and selected categories

In v2rayNG, go to **Asset files → + → URL** and add or change the source for each database. Use the exact names **`geosite.dat`** and **`geoip.dat`** and their corresponding raw links above; tap the download/cloud icon and verify that both file sizes changed before reconnecting VPN.

Keep **`geoip-only-cn-private.dat`** from v2rayNG unchanged. v2rayNG internally rewrites `geoip:private` to refer to this special built-in file, so a PRIVATE-only main GeoIP usually provides a download/storage optimization rather than another runtime saving for that rule.

**Important:** the GeoIP Lite file has **only `geoip:private`**, not `geoip:ru`, `geoip:cn`, ASN or other GeoIP categories. If your client routing / DNS config needs another GeoIP category, use the full `geoip.dat` instead or extend the builder. The same limitation applies to GeoSite categories outside the selected set.

## Preserved GeoSite categories

Direct routing:

- `ru-available-only-inside`
- `category-bank-ru`
- `category-ecommerce-ru`
- `category-retail-ru`
- `category-entertainment-ru`
- `yandex`
- `mailru-group`
- `category-ai-ru`
- `category-medicine-ru`
- `category-travel-ru`
- `megafon`
- `mts-ru`
- `rostelecom`
- `t2-ru`

Block routing:

- `category-public-tracker`

Explicit domain rules such as `domain:beeline.ru` and `domain:dom.ru` are not part of a GeoSite database and stay in the client routing configuration.

**Compatibility warning:** This is NOT a general-purpose replacement for RunetFreedom's full `geosite.dat`. If your routing configuration refers to any other `geosite:...` category, add that category to `CATEGORIES` in the script or use `--extra CATEGORY`, and rebuild **before** enabling this file.

## Build and publishing

The [GitHub Actions workflow](.github/workflows/build.yml) runs daily at **12:30 UTC (15:30 Moscow time)**, supports manual **Run workflow**, and rebuilds on changes to the builder scripts/workflow. The scripts:

1. Fetch the latest RunetFreedom release and verify the upstream SHA-256 of each source.
2. Preserve 15 GeoSite categories and **only PRIVATE** from GeoIP without changing the selected payloads.
3. Validate each output's structure and fail on missing categories, malformed CIDRs or a failed post-build check.
4. Generate `geosite.dat`, `geoip.dat` and JSON metadata; commit changed outputs to `main`.

One-time local build:

```bash
python3 build_geosite_lite.py --output geosite.dat
python3 build_geoip_lite.py --output geoip.dat
```

To include an additional category for testing:

```bash
python3 build_geosite_lite.py --extra google --output geosite.dat
```

## Credits and licensing

- Upstream GeoSite data: [runetfreedom/russia-v2ray-rules-dat](https://github.com/runetfreedom/russia-v2ray-rules-dat), **GPL-3.0**.
- Upstream GeoSite generator: [runetfreedom/russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite), **GPL-3.0**.
- Some upstream lists have separate conditions or unclear licensing; consult the upstream sources for details.
- This repository carries a [GPL-3.0 license](LICENSE). The upstream data are redistributed in modified form (selected categories only), with source attribution and changes documented here.

This project is independent and is not an official RunetFreedom distribution.
