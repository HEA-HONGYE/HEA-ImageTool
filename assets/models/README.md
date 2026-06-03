# HEA 项目模型库

这里是 HEA 的项目内置模型库。运行时模型应优先放在这里，外部素材库只作为一次性迁移来源。

模型文件通常很大，不建议提交到 Git。本项目的 `.gitignore` 会忽略真实模型文件，只保留目录结构和 README。

目录对应关系：

- `realesrgan/`：Real-ESRGAN 模型，例如 `realesrgan-x4plus`、`realesrgan-x4plus-anime`、`realesrnet-x4plus`
- `waifu2x/`：Waifu2x 模型，例如 `cunet`、`upconv_7`、`anime_style_art_rgb`
- `realcugan/`：Real-CUGAN 模型，例如 `models-se`、`models-pro`、`models-nose`
- `realsr/`：RealSR 模型，例如 `models-DF2K`、`models-DF2K_JPEG`
- `srmd/`：SRMD 模型，例如 `srmd`、`srmdnf`
- `anime4k/`：Anime4K 相关配置或自定义资源

使用方式：

1. 打开软件的“引擎设置”。
2. 点击“迁移模型库”，选择旧的外部素材库根目录。
3. 软件会识别模型并复制到 `assets/models/` 下对应目录。
4. 迁移完成后，引擎设置会恢复为项目模型库路径。

如果模型缺失，AI 超分页会提示去“引擎设置”迁移或导入模型。不要直接把外部路径作为模型运行路径。

打包发布时，如果希望用户开箱即用，需要随包携带 `assets/models/` 中的模型文件；如果不携带模型，保留目录和 README 即可，用户可后续迁移或导入。
