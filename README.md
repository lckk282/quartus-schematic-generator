# Quartus 原理图批量生成器

在网页上勾元件、填数量，一键生成 **Quartus II 的 .bdf 原理图**，省掉在 Quartus 里一个个拖元件、连导线的时间。

面向数字电路 / EDA 实验课（计数器、分频、数码管、跑马灯、电子钟等），内置 21 个常用电路模板和 480 个元件符号。

> 原理图生成完会直接调用 Quartus 打开，可以马上编译、画波形仿真。

## 特点

- **不用手画原理图**：选模板或搜元件 → 填数量 → 预览 → 一键生成 .bdf，Quartus 自动打开
- **自带安装程序**：自动找到 Quartus、自动写配置、自动建桌面快捷方式，无需联网
- **打开 Quartus 就自动弹出**：装好后开机自启，打开 Quartus 时插件页面自动弹出来
- **纯本地**：只监听 127.0.0.1，不写注册表、不装系统服务、不联网上传任何东西，卸载 = 删文件夹

## 环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11（64 位） |
| Python | 3.6 及以上（安装时勾选 **Add python.exe to PATH**） |
| Quartus | Quartus II 9.x / 13.x / 20.x 均可（只用于「生成后自动打开」，不装也能生成文件） |
| 网络 | 安装与使用都不需要联网 |

## 快速开始

1. **下载**：点右上角 `Code` → `Download ZIP`，解压到任意目录（路径别带空格更稳）；或用 git 克隆：

   ```bat
   git clone https://github.com/lckk282/quartus-schematic-generator.git
   ```

2. **安装**：双击 `安装.bat`。它会自动完成：检查 Python → 检查文件完整性 → 定位 Quartus → 写配置 → 建桌面快捷方式 → 装好「Quartus 一打开就自动弹出」→ 试启动。

3. **使用**：直接打开 Quartus，插件页面会自动弹出；也可以双击桌面上的「Quartus原理图生成器」手动打开。

> 图文版安装教程：安装完成后会自动打开 `安装教程.html`，也可以随时双击查看。

## 日常使用

1. 打开 Quartus（或桌面快捷方式）→ 浏览器出现插件页面 `http://127.0.0.1:8765/`
2. 左侧选模板，或在元件库里搜器件型号（如 `7490`、`74160`）
3. 设置数量、位宽、标签，点「预览」看效果
4. 点「生成」，.bdf 文件写到 `文档\QuartusBatch`，并自动用 Quartus 打开

## 常用命令

```bat
安装.bat --check              只做环境自检，不改动任何东西
安装.bat --no-autostart       不要「Quartus 一开就弹」，只手动启动
安装.bat --no-shortcut        不建桌面快捷方式
安装.bat --quartus "D:\altera\91\quartus\bin64\quartus.exe"
启动插件.bat                  手动打开插件
卸载.bat                      删桌面快捷方式、取消自动弹出
```

## 配置参数

安装后生成 `app\config.json`，用记事本即可修改：

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `quartus_exe` | Quartus 主程序路径 | 安装时自动探测 |
| `quartus_lib` | Quartus 元件库目录 | 安装时自动探测 |
| `output_dir` | 生成的工程放在哪 | `文档\QuartusBatch` |
| `port` | 本地端口 | `8765` |
| `auto_open` | 启动服务后是否自动开浏览器 | `true` |

## 目录结构

```text
quartus-schematic-generator/
├─ 安装.bat              一键安装
├─ 启动插件.bat          手动启动
├─ 卸载.bat              卸载
├─ 安装教程.html         图文安装教程（离线单页）
├─ install.py            安装程序
├─ launcher.py           启动器
├─ uninstall.py          卸载程序
└─ app/
   ├─ server.py          本地网页服务（127.0.0.1:8765）
   ├─ static/index.html  插件前端页面
   ├─ generator.py       .bdf 原理图生成
   ├─ templates.py       21 个电路模板
   ├─ symbols.json       480 个元件符号索引
   ├─ waveform.py        波形图生成
   ├─ watch_quartus.py   检测到 Quartus 启动就弹出页面
   └─ config.py          配置读写
```

## 常见问题

**打开 Quartus 没有自动弹出？**
先确认安装时没加 `--no-autostart`；再看 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup` 里有没有 `QuartusBatchPlacer.bat`；日志在 `app\watcher.log`（能看到「监控启动，等待 Quartus」「已弹出页面」两行就说明在正常工作）。

**端口被占用 / 页面打不开？**
用记事本改 `app\config.json` 里的 `port`（如 8766），再运行 `卸载.bat` + `安装.bat` 让自动弹出跟随新端口。

**生成后 Quartus 没自动打开？**
说明安装时没找到 `quartus.exe`。把 `app\config.json` 的 `quartus_exe` 改成实际路径即可（文件本身已经正常生成了）。

**想彻底删掉？**
运行 `卸载.bat`，然后删除整个文件夹。插件不写注册表、不装系统服务。

## 许可

仅供学习与教学交流使用。
