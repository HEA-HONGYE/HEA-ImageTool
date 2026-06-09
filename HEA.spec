# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets']
hiddenimports += collect_submodules('image_toolbox')

ENGINE_MODEL_DIRS = {
    'realcugan-ncnn-vulkan/models-nose',
    'realcugan-ncnn-vulkan/models-pro',
    'realcugan-ncnn-vulkan/models-se',
    'realesrgan-ncnn-vulkan/models',
    'realsr-ncnn-vulkan/models-DF2K',
    'realsr-ncnn-vulkan/models-DF2K_JPEG',
    'srmd-ncnn-vulkan/models-srmd',
    'waifu2x-ncnn-vulkan/models-cunet',
    'waifu2x-ncnn-vulkan/models-upconv_7_anime_style_art_rgb',
    'waifu2x-ncnn-vulkan/models-upconv_7_photo',
}


def collect_tree(source, target, excluded_dirs=None):
    source_root = Path(source)
    excluded_dirs = {item.replace('\\', '/').strip('/') for item in (excluded_dirs or set())}
    entries = []
    for path in source_root.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(source_root).as_posix()
        if any(relative == excluded or relative.startswith(excluded + '/') for excluded in excluded_dirs):
            continue
        entries.append((str(path), str(Path(target) / path.relative_to(source_root).parent)))
    return entries


datas = []
datas += collect_tree('assets', 'assets')
datas += collect_tree('engines', 'engines', ENGINE_MODEL_DIRS)
datas += collect_tree('tools', 'tools')
datas += [('versions.json', '.')]


a = Analysis(
    ['image_toolbox\\__main__.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)


def is_root_binary_from_runtime_folder(entry):
    target, source, kind = entry
    if kind != 'BINARY':
        return False
    normalized_target = target.replace('\\', '/')
    if '/' in normalized_target:
        return False
    normalized_source = source.replace('\\', '/')
    return '/engines/' in normalized_source or '/tools/' in normalized_source


a.binaries = [entry for entry in a.binaries if not is_root_binary_from_runtime_folder(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HEA',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets\\icons\\hea.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='HEA',
)
