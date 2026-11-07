# Интеграция Hisense VIDAA TV для Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-blue?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![Откройте Home Assistant и перейдите в репозиторий HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

Официальная интеграция Home Assistant для смарт-телевизоров и проекторов на базе **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO и брендов-партнеров).

Подключается **напрямую** к встроенному MQTT-брокеру телевизора (порт TLS `36669`) с использованием клиентских сертификатов. Обеспечивает мгновенные локальные push-обновления, управление воспроизведением, запуск приложений, Wake-on-LAN и виртуальный пульт дистанционного управления без облачных сервисов или внешних мостов.

---

## 🔰 Быстрый старт (Руководство для начинающих)

Настройка занимает менее 3 минут и состоит из 3 простых шагов:

### 1️⃣ Установка через HACS
Нажмите кнопку ниже (или найдите **Hisense VIDAA TV** в HACS → Интеграции → Скачать):

[![Открыть HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

### 2️⃣ Размещение файла ключа (`El.p12`)
Телевизорам VIDAA требуется взаимное шифрование TLS на порту 36669. Скопируйте универсальный файл **`El.p12`** в каталог Home Assistant **`/config/ssl/`**.
- Загрузите бесплатное приложение **VIDAA Smart TV** (APK) в браузере, переименуйте `.apk` в `.zip` и извлеките `res/El.p12`.
- *Устройство Android или эмулятор не требуются!*

> [!TIP]
> **Требуется подробная пошаговая инструкция?**  
> См. **[Руководство для начинающих](../quick_start_beginners.md)** со скриншотами (для PEM-сертификатов и команд OpenSSL см. [Сертификаты SSL](../certificates.md)).

### 3️⃣ Сопряжение с PIN-кодом на экране
1. Перезапустите Home Assistant (`Настройки` → `Система` → `Перезагрузить`).
2. Перейдите в **Настройки → Устройства и службы → Добавить интеграцию** и найдите **Hisense VIDAA TV**.
3. Введите локальный IP-адрес телевизора и нажмите **Отправить**.
4. Введите **4-значный PIN-код**, отображаемый на экране телевизора. Готово!

---

## 📺 Поддерживаемые бренды и модели телевизоров

Официальная поддержка **всех смарт-телевизоров на VIDAA OS** (сопряжение через **4-значный PIN-код на экране**):

- 📺 **Hisense** (Серии U6, U7, U8, UX, A6, A7 — U4 - U8, модельные годы с 2018 по 2026+)
- 📺 **Loewe** (Серии We. SEE, stellar на базе VIDAA OS)
- 📺 **Toshiba** (Модели C350, M550, Z670 на VIDAA)
- 📺 **Philips / TPV** (Серии OLED, The One, PUS на базе VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** и другие партнеры по лицензии
- 📽️ **TOPTRO** (Портативные смарт-проекторы на базе VIDAA OS)

---

## ✨ Основные возможности

- **100% локальное управление по LAN (`iot_class: local_push`)**: Никаких облаков, полная автономность, работа в изолированных IoT VLAN.
- **Медиаплеер (`media_player`)**: Включение/выключение, громкость, выбор источников, переключение каналов, запуск приложений и контекстные клавиши (переключение каналов в ТВ, треков в приложениях).
- **Настройки изображения и звука (`select` и `number`)**: Режимы изображения (`Стандартный`, `Кино`, `Динамический`, `Спорт`, `Filmmaker`), яркость, контраст и подсветка; звуковые режимы и вывод аудио.
- **Уведомления на экране (`notify`)**: Отправка сообщений прямо на экран телевизора.
- **Виртуальный пульт (`remote`)**: Стрелки навигации, цифровой блок, меню, цветные кнопки и настраиваемый повтор клавиш.
- **Триггеры включения (`device_trigger`)**: Встроенная поддержка триггера `hisense_vidaa.turn_on` для умных розеток или Wake-on-LAN.

---

## 📚 Библиотека документации

| Руководство | Описание |
| :--- | :--- |
| 🔰 **[Быстрый старт для начинающих](../quick_start_beginners.md)** | Пошаговое руководство с простым извлечением `El.p12`. |
| ⚙️ **[Конфигурация и параметры](../parameters.md)** | Полное справочное руководство по всем параметрам и меню настроек. |
| ⚡ **[Параметры питания и режима ожидания](../power_and_standby_settings.md)** | Режим ожидания, быстрый старт и защита от сброса токенов. |
| 📱 **[Панели Lovelace и карточки](../lovelace_cards.md)** | Карточки пультов ДУ, кнопочные карточки и шаблоны интерфейса. |
| 🛠️ **[Службы и автоматизации](../services_and_automations.md)** | Примеры YAML для режима кино, переключения входов и последовательностей клавиш. |
| 🔒 **[Сертификаты SSL](../certificates.md)** | Пути к файлам, собственные PEM-сертификаты и команды OpenSSL. |
| 🧪 **[CLI-утилиты тестирования и диагностики](../cli_tools.md)** | Автономные инструменты (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Устранение неполадок](../troubleshooting.md)** | Диагностика и решение ошибок подключения и сопряжения. |
