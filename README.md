# GeoCat 🐈

Компактные GeoSite и GeoIP базы для v2rayNG на основе RunetFreedom. Выбранные категории сохраняются без изменения содержимого.

**[Статус обновлений](STATUS.md)**

## Скачать

| Файл | Состав |
|---|---|
| [geosite.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geosite.dat) | 15 выбранных категорий |
| [geoip.dat](https://raw.githubusercontent.com/notb2-ai/geocat/main/geoip.dat) | Только `private` |

## Подключить в v2rayNG

1. Открой **Asset files → + → URL**.
2. Добавь ссылки из таблицы с именами **geosite.dat** и **geoip.dat**.
3. Нажми **☁️**, дождись загрузки и переподключи VPN.

Если источники уже добавлены, достаточно заменить их URL. Штатный **geoip-only-cn-private.dat** оставь без изменений.

## Обновления

Проверка новых баз — ежедневно примерно в **15:30 МСК**. Дата последней успешной проверки и результат для каждого файла указаны в статусе.

На телефоне обновляй файлы через **Asset files → ☁️**. Отсутствие изменений — нормальный результат: выбранные категории могут остаться прежними.

## Категории GeoSite

<details>
<summary>Показать все 15 категорий</summary>

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
```

</details>

Базы содержат только перечисленные категории и `geoip:private`. Для правил, использующих другие категории, нужна полная база или расширение состава GeoCat.

Направления direct/proxy/block задаются в клиенте. Явные правила `domain:beeline.ru` и `domain:dom.ru` также остаются в клиенте.

## Источники

Данные: [RunetFreedom](https://github.com/runetfreedom/russia-v2ray-rules-dat). Генератор GeoSite: [russia-blocked-geosite](https://github.com/runetfreedom/russia-blocked-geosite).

GeoCat — независимый проект, не официальная сборка RunetFreedom. Лицензия репозитория — [GPL-3.0](LICENSE); условия отдельных исходных списков смотри у их авторов.
