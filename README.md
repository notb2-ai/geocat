# RunetFreedom Lite — GeoSite for v2rayNG

This repository produces a **minimal, lossless subset** of [RunetFreedom's geosite.dat](https://github.com/runetfreedom/russia-v2ray-rules-dat), preserving only selected GeoSite categories. Original category names and encoded category entries are copied byte-for-byte.

## Download

- **[geosite.dat](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geosite.dat)** — ready-to-use Xray/V2Ray GeoSite database
- [geosite.dat.json](https://raw.githubusercontent.com/notb2-ai/runetfreedom-lite/main/geosite.dat.json) — source release, SHA-256, size and retained categories

In v2rayNG, go to **Asset files → + → URL**, enter the asset name **`geosite.dat`** and the raw download link above, then use the download/cloud icon. Ensure the downloaded file is displayed and re-connect the VPN.

Keep `geoip.dat` from RunetFreedom and `geoip-only-cn-private.dat` from v2rayNG unchanged.

## Preserved categories

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

The [GitHub Actions workflow](.github/workflows/build.yml) runs daily at **12:30 UTC (15:30 Moscow time)** and supports manual **Run workflow**. The script:

1. Fetches the latest RunetFreedom release and verifies the upstream SHA-256.
2. Parses the original GeoSite protobuf and preserves each selected category's payload **without changing its contents**.
3. Fails if a required category is missing or the post-build verification fails.
4. Generates `geosite.dat` and `geosite.dat.json` and commits changed outputs to `main`.

One-time local build:

```bash
python3 build_geosite_lite.py --output geosite.dat
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
