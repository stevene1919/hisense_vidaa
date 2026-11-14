# VIDAA Smart TV 智能电视 Home Assistant 集成

<p align="center">
  <a href="../../README.md"><img src="https://img.shields.io/badge/🇬🇧_English-gray?style=flat-square" alt="English"></a>
  <a href="README.de.md"><img src="https://img.shields.io/badge/🇩🇪_Deutsch-gray?style=flat-square" alt="Deutsch"></a>
  <a href="README.it.md"><img src="https://img.shields.io/badge/🇮🇹_Italiano-gray?style=flat-square" alt="Italiano"></a>
  <a href="README.fr.md"><img src="https://img.shields.io/badge/🇫🇷_Français-gray?style=flat-square" alt="Français"></a>
  <a href="README.ru.md"><img src="https://img.shields.io/badge/🇷🇺_Русский-gray?style=flat-square" alt="Русский"></a>
  <a href="README.uk.md"><img src="https://img.shields.io/badge/🇺🇦_Українська-gray?style=flat-square" alt="Українська"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/🇨🇳_简体中文-blue?style=flat-square" alt="简体中文"></a>
</p>

[![HACS](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![Documentation](https://img.shields.io/badge/docs-stevene.enuff.com-blue.svg)](https://stevene.enuff.com/hisensevidaa)
[![GitHub Release](https://img.shields.io/github/v/release/stevene1919/hisense_vidaa)](https://github.com/stevene1919/hisense_vidaa/releases)
[![Support on Ko-fi](https://img.shields.io/badge/Support%20on-Ko--fi-FF5E5B?style=flat&logo=ko-fi&logoColor=white)](https://ko-fi.com/stevene_)

[![打开 Home Assistant 并在 HACS 中打开该仓库。](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

专为运行 **VIDAA OS** 操作系统的智能电视和投影仪（海信 Hisense、东芝 Toshiba、Loewe、飞利浦 Philips、夏普 Sharp、JVC、TOPTRO 及合作授权品牌）打造的 Home Assistant 原生集成。

通过客户端证书**直接连接**电视内置的 MQTT 代理服务器（TLS 端口 `36669`），实现毫秒级本地推送状态更新、媒体播放控制、应用启动、局域网唤醒（Wake-on-LAN）以及虚拟遥控器功能，无需任何云端连接或第三方网关桥接。

---

## 🔰 快速入门（新手教程）

只需 3 个简步，3 分钟内完成设置：

### 1️⃣ 通过 HACS 安装
点击下方按钮（或在 HACS 中搜索 **VIDAA Smart TV** → 集成 → 下载）：

[![打开 HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stevene1919&repository=hisense_vidaa&category=integration)

### 2️⃣ 放置证书密钥文件 (`client_mobile_android.p12` 或 `El.p12`)
VIDAA 电视要求在 36669 端口进行双向 TLS 认证。将通用秘钥文件 **`client_mobile_android.p12`**（或 `El.p12`）放置在 Home Assistant 的 **`/config/ssl/`** 目录中。
- 在浏览器中下载免费的 **VIDAA Smart TV** 应用安装包（APK），将扩展名 `.apk` 重命名为 `.zip`，解压提取其中的 `res/raw/client_mobile_android.p12`（若被混淆则为 `res/El.p12`）。
- *无需任何 Android 设备或模拟器！*

> [!TIP]
> **需要图文分步指导？**  
> 请参阅 **[新手快速入门指南](../quick_start_beginners.md)** 获取完整截图教程（高级 PEM 证书和 OpenSSL 命令请参阅 [SSL 证书指南](../certificates.md)）。

### 3️⃣ 屏幕 PIN 码配对
1. 重启 Home Assistant（`配置` → `系统` → `重新启动`）。
2. 前往 **配置 → 设备与服务 → 添加集成**，搜索 **VIDAA Smart TV**。
3. 输入电视的局域网 IP 地址，点击 **提交**。
4. 在弹出窗口中输入电视屏幕上显示的 **4 位数字 PIN 码** 即可完成配对！

---

## 📺 支持的电视品牌与型号

官方支持**所有搭载 VIDAA OS 系统的智能电视**（通过**屏幕 4 位 PIN 码**配对）：

- 📺 **海信 Hisense**（U6、U7、U8、UX、A6、A7 系列——U4 至 U8，2018 至 2026+ 年款）
- 📺 **Loewe**（We. SEE、stellar 等 VIDAA OS 系列）
- 📺 **东芝 Toshiba**（C350、M550、Z670 等 VIDAA 机型）
- 📺 **飞利浦 Philips / TPV**（OLED、The One、PUS 等搭载 VIDAA 系统的电视）
- 📺 **夏普 Sharp、JVC、Metz、Schneider、Telefunken、Beko** 及其他授权品牌
- 📽️ **TOPTRO**（搭载 VIDAA 系统的便携式智能投影仪）

---

## ✨ 核心特性

- **100% 局域网本地控制 (`iot_class: local_push`)**：完全脱机运行，无云端依赖，支持隔离的 IoT VLAN。
- **媒体播放器 (`media_player`)**：开关机、音量调节、输入源切换、频道切换、应用快速启动及上下文按键（电视模式换台、应用内切歌）。
- **画质与音效调节 (`select` 与 `number`)**：图像模式（`标准`、`影院`、`动态`、`体育`、`Filmmaker`）、亮度、对比度与背光微调；声音模式与音频输出设备切换。
- **专用虚拟遥控器 (`remote`)**：方向导航键、数字键、主页/菜单、四色按键及自定义长按连发。
- **开机自动化触发器 (`device_trigger`)**：原生支持 `vidaa.turn_on` 触发器，用于自动化控制智能插座通电或发送局域网唤醒。

---

## 📚 官方文档库

| 文档指南 | 说明 |
| :--- | :--- |
| 🔰 **[新手快速入门指南](../quick_start_beginners.md)** | 图文分步指导与 `El.p12` 提取教程。 |
| ⚙️ **[配置与选项说明](../parameters.md)** | 所有配置参数与选项菜单详解。 |
| ⚡ **[电源与待机设置](../power_and_standby_settings.md)** | 待机模式、快速开机与防止配对令牌失效配置。 |
| 📱 **[Lovelace 仪表盘与卡片](../lovelace_cards.md)** | 遥控器卡片、快捷按钮与界面范例。 |
| 🛠️ **[服务与自动化示例](../services_and_automations.md)** | 观影模式、输入源自动切换及按键宏 YAML 示例。 |
| 🔒 **[高级 SSL 证书](../certificates.md)** | 证书路径、自建 PEM 证书与 OpenSSL 命令行操作。 |
| 🧪 **[CLI 测试与诊断工具](../cli_tools.md)** | 独立排错工具（`scripts/test_client.py`、`scripts/debug_tv.py`）。 |
| 🩺 **[故障排除与排错指南](../troubleshooting.md)** | 网络连接、证书认证及配对失败排查方案。 |
