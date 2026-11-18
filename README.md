# GeoCat 🐈

Компактные базы GeoSite и GeoIP для v2rayNG и наборы правил для sing-box на основе RunetFreedom.

Выбранные категории сохранены без изменения содержимого.

**[Статус обновлений](STATUS.md)**




[![Last Update](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fstatus.json&query=%24.checked_at_moscow&label=Last%20Update&color=blue)](https://github.com/notb2-ai/geocat/blob/main/STATUS.md)
[![Last Trigger](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fnotb2-ai%2Fgeocat%2Factions%2Fworkflows%2Fbuild.yml%2Fruns%3Fper_page%3D1&query=%24.workflow_runs%5B0%5D.event&label=Last%20Trigger&color=blue)](STATUS.md)

[![GeoSite](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeosite.dat.json&query=%24.rule_count&label=GeoSite&suffix=%20rules&color=blue)](https://github.com/notb2-ai/geocat/blob/main/metadata/geosite.dat.json)
[![GeoCat RU](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeosite.dat.json&query=%24.category_counts%5B%22geocat-ru%22%5D&label=GeoCat%20RU&suffix=%20rules&color=blue)](https://github.com/notb2-ai/geocat/blob/main/metadata/geosite.dat.json)
[![GeoIP](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeoip.dat.json&query=%24.rule_count&label=GeoIP&suffix=%20CIDR&color=blue)](https://github.com/notb2-ai/geocat/blob/main/metadata/geoip.dat.json)
[![GeoSite Size](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeosite.dat.json&query=%24.output_bytes&label=GeoSite%20Size&suffix=%20B&color=blue)](https://github.com/notb2-ai/geocat/blob/main/geosite.dat)
[![GeoIP Size](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2Fnotb2-ai%2Fgeocat%2Fmain%2Fmetadata%2Fgeoip.dat.json&query=%24.output_bytes&label=GeoIP%20Size&suffix=%20B&color=blue)](https://github.com/notb2-ai/geocat/blob/main/geoip.dat)







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

## Подключить в sing-box

GeoCat публикует бинарные наборы правил `.srs`. Общий набор `geocat-ru.srs` содержит все выбранные категории GeoSite и ручные домены. Для отдельных категорий доступны свои файлы `geosite-<категория>.srs` и `geoip-<категория>.srs`.

| Набор | Содержимое |
| --- | --- |
| [geocat-ru.srs](https://raw.githubusercontent.com/notb2-ai/geocat/main/sing-box/geocat-ru.srs) | Общий набор доменных правил GeoCat |
| [geoip-private.srs](https://raw.githubusercontent.com/notb2-ai/geocat/main/sing-box/geoip-private.srs) | Приватные IP-сети |
| [geoip-yandex.srs](https://raw.githubusercontent.com/notb2-ai/geocat/main/sing-box/geoip-yandex.srs) | IP-сети Яндекса |
| [Все наборы .srs](sing-box/) | Полный список категорий GeoSite и GeoIP |

```text
https://raw.githubusercontent.com/notb2-ai/geocat/main/sing-box/geocat-ru.srs
```

Добавь набор в `route.rule_set` и укажи его тег в `route.rules`. В примере совпадения идут через существующий выход с тегом `direct`. Добавь записи в свои списки, сохранив текущие правила и выходы.

```json
{
  "route": {
    "rule_set": [
      {
        "type": "remote",
        "tag": "geocat-ru",
        "format": "binary",
        "url": "https://raw.githubusercontent.com/notb2-ai/geocat/main/sing-box/geocat-ru.srs"
      }
    ],
    "rules": [
      {
        "rule_set": "geocat-ru",
        "action": "route",
        "outbound": "direct"
      }
    ]
  }
}
```

sing-box проверяет обновления удалённого набора раз в сутки по умолчанию. Интервал можно изменить в `update_interval`. [Документация sing-box](https://sing-box.sagernet.org/configuration/rule-set/)

## Обновления

GitHub Actions проверяет новые базы ежедневно в 16:10 МСК. Возможны задержки запуска на GitHub. Файлы `.dat` и `.srs` собираются в одном запуске, а изменения публикуются одним коммитом. Дата последней успешной проверки баз указана в [статусе](STATUS.md).


## Состав баз

<!-- categories:start -->
<details>
<summary>GeoSite — категорий: 26 — показать список</summary>

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
category-forums-ru
category-tech-media-ru
category-education-ru
category-media-ru
regru
nic-ru
2gis
cdek
kontur
bitrix
geocat-ru
```

</details>

<details>
<summary>GeoIP — категорий: 2 — показать список</summary>

```text
private
yandex
```

</details>

<details>
<summary>Ручные домены geocat-ru — 9</summary>

```text
dom.ru
beeline.ru
pachca.com
qplus.ru
megamarket.ru
megamarket.tech
sbermegamarket.ru
eapteka.ru
samokat.ru
```

</details>
<!-- categories:end -->

Состав хранится в [списке GeoSite](config/geosite-categories.txt) и [списке GeoIP](config/geoip-categories.txt). Категории сохраняются при обновлении.

### Категории в маршрутах

В поле Domain можно указать весь набор GeoCat одной строкой или выбрать отдельную категорию:

```text
geosite:geocat-ru
```

`geocat-ru` объединяет все выбранные категории GeoSite и дополнительные доменные правила. Каждая исходная категория доступна отдельно.

Направления direct/proxy/block задаются в клиенте. Все категории, используемые его правилами, должны присутствовать в соответствующей базе.

## Источники

Данные: [RunetFreedom](https://github.com/runetfreedom/russia-v2ray-rules-dat). Генератор GeoSite: [russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite).

GeoCat — независимый проект, не официальная сборка RunetFreedom. Лицензия репозитория — [GPL-3.0](LICENSE); условия отдельных исходных списков смотри у их авторов.
