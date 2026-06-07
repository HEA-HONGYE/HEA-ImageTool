# HEA ImageTool

High-quality Enhancement Assistant for images, animated images, and video.

HEA 是一个基于 Python + PySide6 的本地 AI 媒体增强工具，面向图片超分、视频插帧、动图处理和常用批量图片操作。项目内置多种本地推理引擎和工具链，支持模型库管理、任务队列、日志报告和 Windows 安装包发布。

![Version](https://img.shields.io/badge/version-4.1.7-blue)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![Qt](https://img.shields.io/badge/UI-PySide6-41CD52)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## 核心功能

- 图片 AI 超分：Real-ESRGAN、waifu2x、Real-CUGAN、RealSR、SRMD、Anime4K。
- 视频增强：视频拆帧、逐帧超分、插帧、重新合成、保留音频。
- 视频插帧引擎：RIFE、DAIN、CAIN、IFRNet。
- 动图处理：GIF、WebP、APNG 拆帧、增强和重新合成。
- 批量图片工具：压缩、格式转换、改尺寸、水印、重命名。
- 引擎设置：默认引擎、GPU、Tile、模型路径、模型启用状态。
- 一键检测：图片超分引擎、模型库、FFmpeg 和视频插帧工具。
- 个性化界面：窗口透明度、组件透明度、图片/视频背景。
- 任务日志：处理进度、失败原因、命令行和报告文件。
- Windows 安装包：支持安装、快捷方式、卸载和一键清理用户数据。

## 当前版本

当前版本：`v4.1.7`

这一版重点完成：

- 打包资源路径适配，支持 PyInstaller 目录版运行。
- Windows 安装包脚本和卸载清理工具。
- 工具路径回退修复，避免旧配置影响打包版内置工具。
- 设置页优化，一键检测引擎和模型。
- 个性化背景支持图片和视频。

## 安装包

项目使用 PyInstaller 生成 `dist\HEA`，再通过 Inno Setup 生成 Windows 安装包。

已生成的安装包路径：

```text
release\HEA-ImageTool-4.1.7-Setup.exe
```

安装包包含：

- HEA 主程序
- PySide6 运行时
- 内置 AI 引擎
- FFmpeg / FFprobe
- 视频插帧工具
- 模型资源
- 一键清理用户数据工具

卸载时会自动清理 HEA 用户配置、缓存和注册表项。开始菜单中也提供单独的“一键清理 HEA 用户数据”入口。

## 从源码运行

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m image_toolbox
```

也可以使用启动脚本：

```powershell
.\hea.ps1
```

## 重新打包

先生成 PyInstaller 目录版：

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm HEA.spec
```

再生成 Windows 安装包：

```powershell
& "E:\app\Inno Setup 7\ISCC.exe" installer\HEA.iss
```

输出文件：

```text
release\HEA-ImageTool-4.1.7-Setup.exe
```

## 项目结构

```text
image_toolbox/
  app.py                 应用启动入口
  ui/                    主窗口、主题、通用控件
  features/              功能页面
  core/                  任务、配置、引擎、模型库和媒体处理逻辑

assets/
  icons/                 UI 图标
  models/                模型库

engines/                 图片超分引擎
tools/                   FFmpeg 和视频插帧工具
installer/               Inno Setup 安装包脚本和卸载清理脚本
dist/                    PyInstaller 输出目录
release/                 安装包输出目录
```

## 说明

HEA 是本地工具，不依赖云端 API。模型、引擎和处理任务都在本机运行。由于完整模型包体积较大，完整版安装包接近 1GB，安装时间会受硬盘速度和杀毒软件扫描影响。

后续计划包括精简版安装包、模型包拆分、日志中心和更完整的模型库管理。
