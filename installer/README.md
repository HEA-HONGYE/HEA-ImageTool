# HEA installer

Use Inno Setup 6 to build the Windows installer after `dist\HEA` has been generated.

```powershell
iscc installer\HEA.iss
```

The installer output is written to `release\HEA-ImageTool-4.1.7-Setup.exe`.

The uninstall flow automatically removes HEA user configuration, cache folders, and the `HKCU\Software\HEA` registry tree. The Start Menu also includes a separate "一键清理 HEA 用户数据" shortcut for manual cleanup.
