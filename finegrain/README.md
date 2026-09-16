# Finegrain 双击启动包（测试版）

开发分支预览修复：使用 Gradio 自带双图画廊显示原图和结果，点击图片放大查看；
输出预览缓存使用 PNG，避免额外 WebP 有损压缩。处理异常直接显示错误，不再返回空结果。
此修改只针对结果显示与错误报告，不代表材质效果改善。

不需要 ComfyUI 或 Pinokio。首次会自动下载独立 Python、PyTorch、Finegrain 源码与模型。
需要 Windows 10/11 64 位、NVIDIA 显卡、可访问 GitHub / PyTorch / Hugging Face 的网络；建议预留至少 20GB。

1. 完整解压 ZIP 到例如 `D:\Finegrain`，不要在 ZIP 内直接运行。
2. 双击 **Start.cmd**。首次下载较大，请保持黑色窗口打开。失败会显示错误并保留 `setup.log`，可再次运行重试。
3. 准备完成后自动在浏览器打开本机界面。上传图片，点击 **Enhance Image**。
4. 默认 2×、Denoise Strength 0.15、潜空间分块 64×64（对应图像分块 512×512）。关闭两个额外渲染 LoRA 的强度，减少夸张渲染。作者声明针对 8GB 显存优化，本启动包尚未在 RTX 5060 Ti 上实际出图测试。
5. 在 Prompting 中描述需要的材质；不用点击 Florence-2 自动提示词按钮也能精修。这个按钮会额外下载模型。
6. 图片保存到 `runtime\source\outputs`，或点击 **Open Outputs Folder**。关闭终端停止程序。以后仍双击 Start.cmd。

建议先上传没有文字的小块产品图：

正向提示词：
```
professional product photograph, original shape and colors, clean refined surface, subtle realistic microtexture, soft restrained highlights, crisp edges
```

负向提示词：
```
waxy surface, excessive gloss, chrome, noise, dirty speckles, warped geometry, extra holes, altered colors, oversharpening
```

该软件重绘整张输入图，不含 ClearScale 的框选保护；请先裁出产品，避开文字。结果可能改变细节和颜色，不能承诺保持孔位结构。保留原图。

## 验证范围

Windows CI 检查安装依赖、真实界面构造和启动脚本语法。为避免把无 GPU 检查冒充精修实测，CI 不下载模型、不生成图片。用户端启动前会检查 CUDA 并执行小型 GPU 运算；模型下载与实际出图仍需在用户电脑上完成。

## 来源与修改

- 上游 https://github.com/pinokiofactory/clarity-refiners-ui 固定提交 a632fb6b948fa6b1a55d816982655d6dc8ed995e。
- Refiners 固定提交 a5d3c2971b84f6faa4762b1cf5a07f4f812bb1f5。
- 本包仅包含 ClearScale 编写的启动脚本；下载的上游源码保留 LICENSE，原 app.py 备份为 app.upstream.py。
- 修改：低分块默认值、关闭附加 LoRA 强度、修复启动按钮、本机浏览器自动打开。
- 上游涉及多个模型，模型的使用条件以其各自发布页为准；本包不额外授予模型使用权。
- 本包不会关闭系统安全软件、修改显卡驱动或安装系统服务。

## 输出验证

安装完成后双击 **Verify.cmd**，依次选择同一裁切区域的原图和结果图。也可以把两个文件拖到 Verify.cmd（原图在前）。报告保存在 `verification_reports`，检查文件解码、实际尺寸/比例、整体 RGB 变化、与普通 Lanczos 放大的差异、边缘相关性和小型 CUDA 运算。报告不会执行模型推理，也不把像素变化指标解释为材质质量或结构保真评分。
