# NDM-zh-Hans — Neat Download Manager 简体中文汉化补丁

[![Release](https://img.shields.io/github/v/release/xyford/NDM-zh-Hans)](https://github.com/xyford/NDM-zh-Hans/releases/latest)

一键把 [Neat Download Manager](https://www.neatdownloadmanager.com) (Windows) 的界面汉化为简体中文。纯二进制补丁方式：按字符串内容定位英文界面文本，将译文写入 exe 新增的 `.l10n` 节并重定向所有代码引用，**不依赖固定偏移**——NDM 更新后重跑补丁依然有效。

## 下载使用 (免安装)

到 [Releases](https://github.com/xyford/NDM-zh-Hans/releases/latest) 下载 `ndm-zh-patch.exe`，双击运行（会请求管理员权限）：

- **一键汉化**：自动结束运行中的 NDM → 打补丁 → 自动拉起 NDM
- **恢复原版**：用备份还原英文原版（汉化时会自动备份原版到 `%ProgramData%\NDM-zh\`）
- **自动检查更新**：启动时检查本仓库 Releases，有新版可一键下载
- **更新后自动保持（可选）**：勾选界面上的复选框后，注册一个静默计划任务（登录时 + 每小时，无窗口），NDM 更新回英文版时自动重打汉化；取消勾选即停用。默认关闭。

命令行/静默模式（供计划任务、脚本调用）：

```
ndm-zh-patch.exe --silent [NeatDM.exe路径]    :: 静默汉化
ndm-zh-patch.exe --restore [NeatDM.exe路径]   :: 静默恢复原版
```

## 特性

- 内容匹配定位，兼容 NDM 后续更新（字符串位置变了也能找到）
- 只修补带 HIGHLOW 重定位项的引用位置，ASLR 安全
- 自动识别并同步修补 `std::wstring(ptr, len)` 构造中的长度操作数（基于 capstone 反汇编）
- 幂等：已汉化的 exe 直接退出，不会重复打
- 翻译表 279 条，覆盖主界面/设置/下载窗口/浏览器页/错误提示等全部界面文本
- 刻意保留品牌名、浏览器名、URL、窗口类名等，避免破坏 ShellExecute/单实例检测等功能

## 从源码构建

```
pip install capstone pyinstaller
build_exe.ps1
```

## 工作原理

NDM (1.4.x) 是 32 位 MSVC 原生程序，界面字符串是 `.rdata` 节里的 UTF-16 宽字符串，代码通过 32 位绝对地址引用。本补丁器：

1. 把英文原文 UTF-16LE 编码后按内容搜索定位（要求串尾 00 00）
2. 全文件扫描指向这些地址的 4 字节引用，用重定位表过滤掉数值巧合
3. 译文写入新增 `.l10n` 节，原字符串保留不动
4. 重写所有引用指针；对 `push len; push ptr` 形式的 wstring 构造同步改写长度
5. 设置窗口选项卡标签等长度敏感场景按原字符数等长补齐

## 许可

补丁器代码 MIT。NDM 本体归其作者所有，本仓库仅包含翻译与补丁逻辑，不包含 NDM 程序本体。
