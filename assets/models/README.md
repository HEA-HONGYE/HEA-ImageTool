# HEA 项目模型库

这里是 HEA 的项目内置模型库。运行时模型必须来自这里，外部 `ai超分参考文件` 或其他素材库只作为一次性迁移来源。

模型文件通常较大，不提交到 Git。`.gitignore` 会忽略真实模型文件，只保留目录结构和 README。

## 图片超分模型

图片超分和视频逐帧超分复用同一套图片模型：

- `realesrgan/`：Real-ESRGAN 模型
- `waifu2x/`：Waifu2x 模型
- `realcugan/`：Real-CUGAN 模型
- `realsr/`：RealSR 模型
- `srmd/`：SRMD 模型
- `anime4k/`：Anime4K 相关资源

视频超分不要重复复制模型到 `video_upscale/`，直接使用上述目录。

## 视频插帧模型

视频插帧模型单独放在：

- `video_interpolation/rife/`
- `video_interpolation/dain/`
- `video_interpolation/cain/`
- `video_interpolation/ifrnet/`

RIFE、DAIN、CAIN、IFRNet 的运行命令必须使用这些项目内模型目录，不能直接引用素材库路径。

## 从素材库导入

1. 打开“引擎设置”或模型库管理入口。
2. 点击“迁移模型库”或“从素材库导入模型”。
3. 选择旧的 `ai超分参考文件` 根目录。
4. 程序会扫描图片超分模型和视频插帧模型。
5. 导入后模型会复制到 `assets/models/` 对应目录。

导入完成后，可以删除、移动或断开外部素材库；运行时不应再依赖素材库模型。

## 工具和引擎程序

FFmpeg、FFprobe 和各类 `.exe` 属于工具或引擎程序，不放在模型库中。它们可以由用户配置路径、放在 `tools/ffmpeg/` 或 `engines/`，但模型仍必须来自 `assets/models/`。

## 打包发布

如果希望开箱即用，需要随包携带 `assets/models/` 中的模型文件。如果不携带模型，保留目录和 README，用户可后续从素材库迁移。
