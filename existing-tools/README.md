# 产品修图：现成软件使用包
检索日期：2026-09-17。ClearScale 自研算法暂停。本目录不调用旧程序。

## 先读
这是 Krita AI Diffusion 官方插件 + 中文操作手册。不是离线整合安装器。
Krita、ComfyUI 运行环境和模型需要联网安装；由官方插件管理安装。
尚未在你的 RTX 5060 Ti 8GB 上实测，不保证精确重建每一根线材。
工作流使用插件内置流程，不提供未经验证的节点 JSON。

## 安装
1. 从 https://krita.org/en/download/ 下载 Krita 5（上游插件推荐 5.3.2.1）。不要用 Krita 6 搭配本包 1.x 插件。
2. 在 Krita：工具 → 脚本 → 从文件导入 Python 插件，选择本包的 krita_ai_diffusion-1.53.0.zip，启用后重启。
3. 打开产品图；设置 → 停靠面板 → AI Image Generation。
4. Configure → Local Managed Server；后端选 NVIDIA/CUDA；选新的独立安装目录。
5. 先安装 SDXL Photography 工作负载（RealVisXL）及其必要组件。参考图功能需要 SDXL IP-Adapter / CLIP Vision，可在 Individual Packages 查看。不要一开始全选模型。
6. 安装结束连接服务器，先做一个小选区测试。已有旧 ClearScale 不需要卸载，模型文件先保留。
7. 想直接用节点界面：另见 https://comfy.org/download 。这是可选方案，不要同时安装两套后端。
准备至少数十 GB 空间。首次联网下载可能很久；报错请保留完整日志。驱动使用 NVIDIA 官方当前适用版本。

## A：换背景（第一项实测）
- 打开原图，另存 KRA 工程；保留锁定的原图备份图层。
- 选中背景，避开线轴边缘与标签；使用插件 Selection Fill 流程。
- 先生成浅灰背景，接受结果到新图层。保持原产品图层在上方可保护主体。
- 接触阴影另做小选区，避免全图重绘。
- 描述提示词：
  A clean light blue-gray product photography studio, soft diffused lighting, a subtle natural contact shadow on a matte tabletop, minimal empty background, no text, no extra objects.
- 100% 放大检查：标签、孔位、轮廓不得变形；无白边、漂浮和重影。

## B：换线材材质（第二项实测）
- 只选线材，不选黑盘、蓝标签、孔洞和背景。
- 不同开窗先分开测试；参考图裁成纯线材区域，避免带入品牌和整个纸线盘。
- SDXL 使用 Reference 控制层，引入材质图片；它不保证严格分离颜色/材质/排列。
- 提示词描述目标，如：
  Neatly wound translucent red PETG filament, consistent strand diameter, smooth parallel winding following the spool curvature, realistic subtle highlights, clean product photography.
- 重绘强度先 50%，再比较 70%；这是试验起点，不是已验证最佳参数。
- 若只改颜色且原排列合格，优先用 Krita 选区与颜色调整，避免重新生成结构。
- 不要用原图凌乱线条的强 Canny 控制去强求整齐，它可能锁住旧缺陷。

## C：指令式换材质/参考替换（可选第二路线）
插件官方支持 Flux Kontext；Flux 2 Klein 和 Qwen Image Edit 标为实验性。
优先进一步试 Flux 2 Klein 4B 的量化版；8GB 下仍需实测，先单图、小选区。
从插件模型管理器安装，不混用旧版 Nunchaku 安装教程。
编辑模型用命令式提示词，通常 100% 强度；不要照搬 SDXL 的 50% 设置。
示例：
  Replace only the exposed red filament with the material appearance in the reference image. Keep the black spool, blue KELEIDI label, holes, ribs, camera angle and background unchanged. Preserve the original red color.
如改色，把末句换为明确目标色。排列要求另单独测试，不同时换背景。
选区约束和结果图层蒙版仍需检查，提示词不能保证产品完全不变。

## 保存及验收
- 文件 → 另存为 .kra 保留图层；导出 → PNG 输出图片。
- 先验收编辑结果，最后再用插件 Upscale，初次 2x；放大不是排列重绘。
- 保存每次模型名、强度、提示词、参考图和原图，避免无法复现。
- 本包验证：官方插件 ZIP 哈希和 ZIP 完整性、打包文件。未做 GPU 推理或画质通过认证。

## 项目筛选
| 项目 | 用途 | 选择 |
|---|---|---|
| Acly/krita-ai-diffusion | 选区、图层、参考、ComfyUI 后端 | 首选操作软件 |
| Comfy-Org/ComfyUI | 通用节点工作流 | 需要细调节点时使用 |
| black-forest-labs/flux2 | 指令编辑、多参考候选 | Klein 4B 量化待本机测试 |
| QwenLM/Qwen-Image | 语义图像编辑候选 | 非首装；8GB 资源与速度待验证 |
| lllyasviel/IC-Light | 背景与主体光照协调 | 后续选用，重打光可能影响真实商品颜色 |

官方来源：
https://github.com/Acly/krita-ai-diffusion/releases/tag/v1.53.0
https://docs.interstice.cloud/installation/
https://docs.interstice.cloud/models/
https://docs.interstice.cloud/edit-models/
https://docs.interstice.cloud/control-layers/
https://github.com/Comfy-Org/ComfyUI
https://github.com/black-forest-labs/flux2
https://github.com/QwenLM/Qwen-Image
https://github.com/lllyasviel/IC-Light

第三方插件未修改，GPL-3.0，附许可证；对应完整源代码随测试包附带。
模型不在包内，各模型许可单独适用，商用前查看其模型卡。
