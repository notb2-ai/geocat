# GeoCat 🐈

Компактные GeoSite и GeoIP базы для v2rayNG на основе RunetFreedom. Выбранные категории сохраняются без изменения содержимого.

**[Статус обновлений](STATUS.md)**


[![Auto Update](https://img.shields.io/github/actions/workflow/status/notb2-ai/geocat/build.yml?branch=main&event=schedule&label=Auto%20Update)](https://github.com/notb2-ai/geocat/actions/workflows/build.yml?query=event%3Aschedule+branch%3Amain)
[![GeoSite](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeosite.dat.json&query=%24.rule_count&label=GeoSite&suffix=%20rules&color=blue)](https://github.com/notb2-ai/geocat/blob/main/metadata/geosite.dat.json)
[![GeoIP](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeoip.dat.json&query=%24.rule_count&label=GeoIP&suffix=%20CIDR&color=blue)](https://github.com/notb2-ai/geocat/blob/main/metadata/geoip.dat.json)


Статус бар показывает результат последнего запуска по расписанию, а не свежесть баз; дата запуска — по нажатию.

## Скачать

**[geosite.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geosite.dat)**

```text
https://raw.githubusercontent.com/notb2-ai/geocat/main/geosite.dat
```

**[geoip.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geoip.dat)**

```text
https://raw.githubusercontent.com/notb2-ai/geocat/main/geoip.dat
```

## Подключить в v2rayNG

1. Открой **Asset files → + → URL**.
2. Добавь ссылки выше с именами **geosite.dat** и **geoip.dat**.
3. Нажми **☁️**, дождись загрузки и переподключи VPN.

Если источники уже добавлены, достаточно заменить их URL. Штатный **geoip-only-cn-private.dat** оставь без изменений.

## Обновления

Проверка новых баз — каждые 6 часов, примерно в **02:07, 08:07, 14:07 и 20:07 МСК**. Это через 1 час 37 минут после планового запуска RunetFreedom; возможны задержки GitHub. Дата последней успешной проверки и результат для каждого файла указаны в статусе.

На телефоне обновляй файлы через **Asset files → ☁️**. Отсутствие изменений — нормальный результат: выбранные категории могут остаться прежними.

## Состав баз

<!-- categories:start -->
<details>
<summary>GeoSite — категорий: 16 — показать список</summary>

```text
ru-available-only-inside
category-bank-ru
category-ecommerce-ru
category-retail-ru
category-entertainment-ru
yandex
mailru-group
category-ai-ru
category-medicine-ru
category-travel-ru
megafon
mts-ru
rostelecom
t2-ru
category-public-tracker
private
```

</details>

<details>
<summary>GeoIP — категорий: 1 — показать список</summary>

```text
private
```

</details>
<!-- categories:end -->

Состав хранится в [списке GeoSite](config/geosite-categories.txt) и [списке GeoIP](config/geoip-categories.txt). Категории сохраняются при ежедневном обновлении.

Направления direct/proxy/block задаются в клиенте. Все категории, используемые его правилами, должны присутствовать в соответствующей базе.

## Источники

Данные: [RunetFreedom](https://github.com/runetfreedom/russia-v2ray-rules-dat). Генератор GeoSite: [russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite).

GeoCat — независимый проект, не официальная сборка RunetFreedom. Лицензия репозитория — [GPL-3.0](LICENSE); условия отдельных исходных списков смотри у их авторов.
