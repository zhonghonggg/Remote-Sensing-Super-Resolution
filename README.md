# 遥感影像超分辨率工具 V1.0

Based on SRVGGNetCompact. Produced by ZhongHong.

[GitHub 仓库](https://github.com/zhonghonggg/Remote-Sensing-Super-Resolution) · [下载安装程序](https://github.com/zhonghonggg/Remote-Sensing-Super-Resolution/releases/latest)

程序顶部署名后提供仓库链接，支持鼠标点击或键盘 Tab 聚焦后按 Enter 打开。

Windows 10/11 64位离线安装版。运行 Setup，可选安装位置及桌面快捷方式；每用户安装，支持系统“已安装的应用”卸载。安装后无需 Python、CUDA 或网络。窗口、程序、安装器和快捷方式使用原创地图放大镜图标。

选择带坐标系的 GeoTIFF、成果目录，输入目标像元大小（米），点击“开始超分”。默认 DirectML，失败自动 CPU；可手选 CPU。日志显示阶段、设备、batch/tile 和进度；可以取消、另存日志、打开成果目录。取消要等待当前推理或磁盘分块完成后清理，期间请勿强行终止进程。

模型只进行一次 Real-ESRGAN realesr-general-x4v3 4倍人工增强，再重采样到目标网格；0.2m 表示输出像元，不代表新增0.2m真实测量精度。目标倍率超过4时继续插值，不递归虚构细节；倍率不足4时缩小增强结果。AI 可能改变纹理、制造细节，不适用于测量或定量遥感分析。

输入：uint8/uint16 单波段灰度、RGB、明确标记 Alpha 的 RGBA。uint16 按完整0–65535固定归一化，无自动拉伸；输出固定8位RGB+Alpha，单波段复制为RGB。不支持任意多光谱、浮点、调色板或无坐标影像。NoData/Alpha 无效区按波段掩膜交集保留为透明度；黑色有效像元不会自动作为NoData。无效区域附近的AI上下文填零，边缘可能产生纹理变化。

原图米制投影保留坐标系，包括旋转影像也重新覆盖到北向上网格。经纬度或英尺等非米制投影自动选择区域中心所在UTM：限纬度-80°至84°、跨度不超过6°且不跨日期变更线；其他范围明确拒绝，需事先转换到适合当地的米制投影。跨UTM带边缘可能有变形，自动选择不替代专业投影设计。目标像元严格为输入米数；网格左上角向外按像元对齐，因此范围可比输入扩大不足一个像元。

大图使用按窗口读取、外扩40像元上下文、分块写入，GDAL缓存128MiB，warp缓存128MiB。初始tile256/batch4，GPU推理错误后batch逐次减半至1、tile降至64、再CPU；重试次数有限，已完成块沿用。CPU最小块仍失败即终止。DirectML后端要求Windows兼容显卡与合适驱动，NVIDIA/AMD/Intel实际支持取决于驱动；不依赖CUDA。GUI每次只运行一项任务，不建议同时启动多个程序争抢显存。

所有临时影像位于输出目录内随机命名的专属 .geosr-task-* 子目录；成功、失败和取消均只清除此任务目录。强制结束/停电无法执行清理，确认无任务运行后可手工删除残留的该前缀目录。需要同时容纳4倍中间影像和最终影像，启动前按未压缩体积保守检查磁盘空间；全图任务可能需要数百GB。输出始终使用BigTIFF和Deflate压缩；最终逐块读取校验，成功后改名发布随机后缀正式文件，避免覆盖既有成果。日志默认仅留在界面（最近5000行），需要时另存。

## 源码与构建

源码位于src，测试位于tests；models含离线ONNX，vendor含原始权重、官方结构源码及BSD许可证。GeoSR.spec、installer.iss 和 build.ps1 为完整构建入口。Python 3.10 x64，依赖版本在 requirements-lock.txt；离线wheel在wheelhouse。运行 `powershell -ExecutionPolicy Bypass -File .\build.ps1`；需提供Inno Setup 6编译器路径，见脚本参数。运行测试 `.venv\Scripts\python.exe tests\acceptance.py`。

从 GitHub 克隆的仓库只保留源码、模型和许可证。完整离线构建材料（wheelhouse及安装器工具）在Release的Full-Source.zip中；或先用 `python -m pip download -r requirements-lock.txt -d wheelhouse` 下载依赖，并从Inno Setup官网下载编译器。

首次构建前，运行vendor/innosetup.exe，把编译工具安装在vendor/inno，或用build.ps1的-ISCC参数指定已安装编译器。编译工具的许可适用条件见vendor/inno/license.txt及官网；商业构建需自行满足相应许可。打包后程序的使用不需要安装该编译器。

重导出模型用CPU torch 2.x与onnx环境运行export_model.py；正常构建直接使用已附动态batch模型，无需torch。网络输入/输出均支持动态N/H/W。命令行也支持 `GeoSR.exe --input 原图.tif --output 输出目录 --resolution 0.2 --cpu --report 报告.json`。窗口版不输出控制台，用report记录结果。

本程序未作数字签名，Windows可能显示未知发布者。安装包可用release/SHA256SUMS.txt核对。验收记录在QA与验收说明.md；AMD/Intel和其他Win10/11实机尚需部署验证。
