# ClearScale 清晰放大

## v1.1.0 图片优化

默认开启自动降噪和轻度色泽均匀优化，可关闭或改用标准强度。
减轻局部颗粒和小范围杂色，保留明显边界及自然明暗；无法保证消除大面积光照不均。
修正 2×/3×：固定先以原生 4× 模型推理，再用 Lanczos 缩放。
PNG/WebP 保留原图透明度，重复导出自动添加序号。
建议始终使用未处理的原图，不要继续放大旧版错位结果。

一款本地运行的 Windows AI 图片高清放大工具。适合电商产品图、照片、3D 打印件渲染图和插画，支持 2× / 3× / 4× 放大、批量处理与前后拖动对比。

## 功能

- 本地 AI 处理，图片不上传服务器
- 照片 / 产品图与插画 / 动漫两套模型
- 2×、3×、4× 高清放大
- PNG、JPG、WebP 导出
- 多图批量队列、任务进度与取消
- 原图 / 高清图拖动对比
- 自动保留原图，输出名为 `原文件名_HD_4x.png`

底层使用 [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN) 的便携式 NCNN Vulkan 引擎，无需安装 CUDA 或 PyTorch。首次从源码启动时会下载官方 Windows 引擎；GitHub Release 安装包会直接内置引擎。

## 普通用户

在仓库的 **Releases** 页面下载：

- 文件名带 `Setup`：一键安装版
- 文件名不带 `Setup`：绿色免安装版

安装后双击桌面的“ClearScale 清晰放大”即可。

## 源码运行

需要 Windows 10/11、Node.js 20+ 和支持 Vulkan 的 Intel / AMD / NVIDIA 显卡。

```powershell
npm install
npm run engine:win
npm start
```

也可以直接双击 `启动开发版.bat`。

## 打包 Windows 程序

```powershell
npm install
npm run dist:win
```

推送 `v1.0.0` 这类标签后，GitHub Actions 会自动生成安装包并发布到 Releases。

## 说明

AI 高清放大可以重建合理细节、减少锯齿和模糊，但无法百分百还原原图中从未记录下来的文字、五官或纹理。重要商品细节请在输出后人工核对。

## 开源许可

应用代码采用 MIT License。Real-ESRGAN 及其模型采用 BSD 3-Clause License，完整文本见 `THIRD_PARTY_NOTICES.md`。
