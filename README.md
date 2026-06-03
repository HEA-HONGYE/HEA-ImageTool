# 图片工具箱 V2

一个基于 Python + PySide6 + Pillow 的桌面图片批量处理工具。V2 保留 V1 的图片压缩和格式转换，并新增批量改尺寸、批量添加水印、批量重命名、任务队列、日志输出和参数自动保存。

## 功能

- 图片压缩：支持 JPG、PNG、WEBP 等常用格式。
- 格式转换：支持 JPG、PNG、WEBP、BMP、TIFF 输出。
- 批量改尺寸：支持按比例缩放、按指定宽高缩放、保持原比例。
- 批量添加水印：支持文字水印和图片水印，可设置位置、透明度、字体大小。
- 批量重命名：支持前缀、后缀、自动编号、保留原文件名。
- 任务队列：显示每个文件处理状态，支持暂停、继续、取消。
- 日志系统：记录成功、失败、错误原因，并支持打开输出目录。
- 配置保存：自动保存各功能上一次使用的参数。

## 运行

```powershell
py -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m image_toolbox
```

也可以在已安装依赖的环境中直接运行：

```powershell
py -m image_toolbox
```

或使用启动脚本：

```powershell
.\hea.ps1
```

## 结构

- `image_toolbox/app.py`：应用启动。
- `image_toolbox/ui/`：主窗口、任务队列面板、主题。
- `image_toolbox/features/`：功能模块，新增功能继承 `ToolFeature` 并注册到主窗口。
- `image_toolbox/core/`：后台任务、配置保存、图片处理核心逻辑。
