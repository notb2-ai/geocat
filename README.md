# GeoCat 🐈 — compact GeoSite & GeoIP for v2rayNG

[![Build GeoCat databases](https://github.com/notb2-ai/geocat/actions/workflows/build.yml/badge.svg)](https://github.com/notb2-ai/geocat/actions/workflows/build.yml)

**🐈 [Последняя успешная проверка: версия, изменения, время → STATUS.md](STATUS.md)**

This repository produces **minimal, lossless subsets** of [RunetFreedom's GeoSite and GeoIP databases](https://github.com/runetfreedom/russia-v2ray-rules-dat). Original selected category payloads are copied byte-for-byte, preserving matching behavior.

## Download

- **[geosite.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geosite.dat)** — ready-to-use Xray/V2Ray GeoSite database
- **[geoip.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geoip.dat)** — ready-to-use GeoIP database containing **only** `private`
- [geosite.dat.json](https://raw.githubusercontent.com/notb2-ai/geocat/main/geosite.dat.json) and [geoip.dat.json](https://raw.githubusercontent.com/notb2-ai/geocat/main/geoip.dat.json) — source release, SHA-256, sizes and selected categories

In v2rayNG, go to **Asset files → + → URL** and add or change the source for each database. Use the exact names **`geosite.dat`** and **`geoip.dat`** and their corresponding raw links above; tap the download/cloud icon and wait for successful downloads before reconnecting VPN. File sizes may remain unchanged even when an update succeeds.

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

The [GitHub Actions workflow](.github/workflows/build.yml) checks **both** databases daily at **12:30 UTC (15:30 Moscow time)** and on builder/test/workflow changes.

### Как проверить результат

Открой **[STATUS.md](STATUS.md)**: там дата последней успешной проверки в МСК, исходный релиз, результат для каждой базы, количество записей и SHA-256. Машиночитаемый отчёт: [status.json](status.json).

- **Файл изменился** — изменились байты базы.
- **Новый исходный релиз; файл прежний** — проверен новый RunetFreedom, выбранные категории остались такими же.
- **Изменений нет** — версия и содержимое прежние; проверка выполнена успешно.

В [Actions](https://github.com/notb2-ai/geocat/actions/workflows/build.yml) открой последний запуск: в **Summary** есть тот же отчёт и отдельный результат публикации. Зелёный запуск означает успешное завершение. При ошибке старые опубликованные базы и STATUS.md остаются от предыдущего успешного запуска — всегда проверяй дату отчёта и последний запуск Actions.

Для ручного запуска: **Actions → Build GeoCat databases → Run workflow → main**. Не используй **Re-run jobs** у старой сборки: GitHub повторяет сохранённую старую версию workflow (первые сборки обновляли только GeoSite). Опция **force** принудительно скачивает и пересобирает обе базы.

### Как устроена сборка

1. One request selects one latest upstream release for both files.
2. The builder compares upstream SHA-256, asset identity/size, selected categories, builder fingerprint and verified local output SHA-256. If all match, it skips the large source download. Changes to builder code invalidate this fast path.
3. When needed, the two source files download in parallel. Downloads log progress, retry transient errors up to three times, and have time/size bounds. Hash mismatches stop publication.
4. Original category payloads are copied byte-for-byte. Both outputs must pass validation before output files are written. The workflow commits both databases, metadata and reports together; it never force-pushes.
5. Every successful check records its timestamp, even when database bytes do not change. Thus a status-only commit is normal. A bot status commit does not match the build-trigger paths.

The workflow has a 15-minute overall job limit and a 10-minute database-step limit. Queue and checkout time depend on GitHub; the report's duration covers only checking/building. The builder uses Python's standard library; no pip installs or external cache services are required.

One-time local check/build of both databases:

```bash
python3 build_all.py
# Force source downloads and rebuild:
python3 build_all.py --force
# Offline unit tests:
python3 -m unittest discover -s tests -v -b
```

The original `build_geosite_lite.py` and `build_geoip_lite.py` commands remain available for individual/local builds, but the shared workflow uses `build_all.py`.

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

