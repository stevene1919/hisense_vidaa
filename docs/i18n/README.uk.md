# Інтеграція VIDAA Smart TV для Home Assistant

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-blue?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-gray?style=flat-square" alt="简体中文"></a>
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![Відкрийте Home Assistant і перейдіть до репозиторію в HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

Офіційна інтеграція Home Assistant для смарт-телевізорів і проекторів на базі **VIDAA OS** (Hisense, Toshiba, Loewe, Philips, Sharp, JVC, TOPTRO та партнерських брендів).

Підключається **безпосередньо** до внутрішнього MQTT-брокера телевізора (порт TLS `36669`) за допомогою клієнтських сертифікатів. Забезпечує миттєві локальні push-оновлення, керування мультимедіа, запуск застосунків, Wake-on-LAN та віртуальний пульт керування без хмарних сервісів чи зовнішніх мостів.

---

## 🔰 Швидкий старт (Посібник для початківців)

Налаштування займає менше 3 хвилин у 3 простих кроки:

### 1️⃣ Встановлення через HACS
Натисніть кнопку нижче (або знайдіть **VIDAA Smart TV** у HACS → Інтеграції → Завантажити):

[![Відкрити HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

### 2️⃣ Розміщення файлу ключа (`El.p12`)
Телевізорам VIDAA потрібне взаємне шифрування TLS на порту 36669. Скопіюйте універсальний файл **`El.p12`** у каталог Home Assistant **`/config/ssl/`**.
- Завантажте безкоштовний застосунок **VIDAA Smart TV** (APK) у браузері, перейменуйте `.apk` на `.zip` та видобудьте `res/El.p12`.
- *Пристрій Android або емулятор не потрібні!*

> [!TIP]
> **Потрібна детальна покрокова інструкція?**  
> Див. **[Посібник для початківців](../quick_start_beginners.md)** зі скріншотами (для PEM-сертифікатів і команд OpenSSL див. [Сертифікати SSL](../certificates.md)).

### 3️⃣ З'єднання за допомогою PIN-коду на екрані
1. Перезапустіть Home Assistant (`Налаштування` → `Система` → `Перезапустити`).
2. Перейдіть до **Налаштування → Пристрої та служби → Додати інтеграцію** і знайдіть **VIDAA Smart TV**.
3. Введіть локальну IP-адресу телевізора та натисніть **Надіслати**.
4. Введіть **4-значний PIN-код**, показаний на екрані телевізора. Готово!

---

## 📺 Підтримувані бренди та моделі телевізорів

Офіційна підтримка **всіх смарт-телевізорів на VIDAA OS** (з'єднання через **4-значний PIN-код на екрані**):

- 📺 **Hisense** (Серії U6, U7, U8, UX, A6, A7 — U4 - U8, модельні роки з 2018 по 2026+)
- 📺 **Loewe** (Серії We. SEE, stellar на базі VIDAA OS)
- 📺 **Toshiba** (Моделі C350, M550, Z670 на VIDAA)
- 📺 **Philips / TPV** (Серії OLED, The One, PUS на базі VIDAA OS)
- 📺 **Metz, Schneider, Telefunken, Beko, Sharp, JVC** та інші партнери за ліцензією
- 📽️ **TOPTRO** (Портативні смарт-проектори на базі VIDAA OS)

---

## ✨ Основні можливості

- **100% локальне керування по LAN (`iot_class: local_push`)**: Повна автономність без хмари, підтримка ізольованих IoT VLAN.
- **Медіаплеєр (`media_player`)**: Увімкнення/вимкнення, гучність, джерела входу, перемикання каналів, запуск застосунків і контекстні кнопки (перемикання каналів у ТБ, треків у додатках).
- **Налаштування зображення та звуку (`select` і `number`)**: Режими зображення (`Стандартний`, `Кіно`, `Динамічний`, `Спорт`, `Filmmaker`), яскравість, контраст і підсвічування; звукові режими та аудіовихід.
- **Віртуальний пульт (`remote`)**: Стрілки навігації, цифрові кнопки, меню, кольорові клавіші та налаштовуваний повтор натискань.
- **Тригери увімкнення (`device_trigger`)**: Вбудована підтримка тригера `vidaa.turn_on` для розумних розеток або Wake-on-LAN.

---

## 📚 Бібліотека документації

| Посібник | Опис |
| :--- | :--- |
| 🔰 **[Швидкий старт для початківців](../quick_start_beginners.md)** | Покрокова інструкція з легким видобуванням `El.p12`. |
| ⚙️ **[Конфігурація та параметри](../parameters.md)** | Повний довідник з усіх параметрів та меню налаштувань. |
| ⚡ **[Параметри живлення та режиму очікування](../power_and_standby_settings.md)** | Режим очікування, швидкий старт і захист від втрати токенів. |
| 📱 **[Панелі Lovelace та картки](../lovelace_cards.md)** | Картки пультів, кнопкові картки та шаблони інтерфейсу. |
| 🛠️ **[Служби та автоматизації](../services_and_automations.md)** | Приклади YAML для режиму кіно, вибору входів і послідовностей команд. |
| 🔒 **[Сертифікати SSL](../certificates.md)** | Шляхи до файлів, власні PEM-сертифікати та команди OpenSSL. |
| 🧪 **[CLI-утиліти тестування та діагностики](../cli_tools.md)** | Автономні інструменти (`scripts/test_client.py`, `scripts/debug_tv.py`). |
| 🩺 **[Виправлення неполадок](../troubleshooting.md)** | Діагностика та вирішення помилок підключення і з'єднання. |
