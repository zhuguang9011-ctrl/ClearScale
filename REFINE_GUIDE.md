# 局部材质精修（实验功能）

这个版本通过本机 ComfyUI + Ultimate SD Upscale 对框选区域低强度分块重绘。适用于 AI 产品图的表面细节修饰。不是恢复真实细节，也不能保证产品孔位、颜色完全不变；定稿前请检查。选区外保留原图的普通 Lanczos 放大结果，不参与生成。框内的文字不会自动受到保护。

## 第一次准备

1. 从 [ComfyUI 官方 Releases](https://github.com/Comfy-Org/ComfyUI/releases) 下载 NVIDIA Windows portable 包，解压到例如 `D:\ComfyUI`。RTX 5060 Ti 请使用支持 Blackwell 的新版 NVIDIA 包；不要使用旧 CUDA 环境。
2. 按 [Ultimate SD Upscale 官方安装说明](https://github.com/ssitu/ComfyUI_UltimateSDUpscale) 安装节点。使用 Git 时，在 `ComfyUI/custom_nodes` 下运行：

   ```bat
   git clone --recursive https://github.com/ssitu/ComfyUI_UltimateSDUpscale.git
   ```

   `--recursive` 不可省略。已经安装但报子模块错误时，在节点目录执行 `git submodule update --init --recursive`。
3. 将你有权使用的 **SD1.5 完整 checkpoint（含 VAE，优先 safetensors）** 放进 `ComfyUI/models/checkpoints`。此版本不自动下载模型；不同模型的商用许可需按其模型页确认。不要选择 SDXL、Flux、SD3 或 LoRA。
4. 在 portable 根目录打开终端，启动低显存模式：

   ```bat
   .\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build --lowvram --listen 127.0.0.1 --port 8188
   ```

   保持窗口打开。模型与环境可能占用数 GB 到数十 GB，取决于所选版本。

## 在 ClearScale 中使用

1. 只选择 **一张** 原图；选择导出文件夹。
2. 处理模式选“局部材质精修”，点击“检测精修引擎 / 刷新模型”。
3. 选择 SD1.5 模型，选材质。丝绸打印件用“丝绸 PLA”；黑色线盘用“黑色注塑”。不要把两种材质同时框进同一个选区。
4. 在左侧拖动框选产品区域，避开标题、标签和图标。
5. 先用 **2×、0.15** 试一小块；默认每块 512×512、批量 1、分块 VAE 解码。若显存不足，退出其他 GPU 软件或改用 1×、更小选区。
6. 完成后拖动对比线检查结果。“重新框选原图”可再次选择。导出为单独 PNG，不覆盖原图；下一次精修仍以最初选择的原图为输入。需要累积编辑时请重新载入上次导出的 PNG。

基础高清模式的倍率、格式、降噪和色泽设置不应用到精修模式。

## 取消与排错

- “停止等待”只停止 ClearScale 等待和保存。已提交的 ComfyUI 任务可能继续运行，可在 ComfyUI 中自行取消。软件不会中断其他程序的任务。
- 连接失败：检查 ComfyUI 窗口是否报错、端口是否为 8188。
- 缺少 UltimateSDUpscaleNoUpscale：检查节点和子模块安装，重启 ComfyUI。
- 色彩、形状变化太大：用 0.15，缩小选区；生成模型无法承诺结构完全不变。必须逐像素保真的图片请使用基础高清模式。
- 精修输出上限 1600 万像素；接口等待上限 60 分钟。实际速度和可用显存尚未在 RTX 5060 Ti 实测。
- 图片只发送到 `127.0.0.1:8188`，上传裁剪和生成中间图会保留在 ComfyUI 的 input/output 文件夹。

## 已验证与未验证

自动测试覆盖裁剪坐标边界、合成时选区外像素及透明度保留、工作流参数、现有高清降噪回归。接口模拟验证不代表 GPU 实际精修效果。当前执行环境没有可用 NVIDIA GPU，尚未完成真实模型出图、5060 Ti 8GB 性能或成品材质效果验证。
