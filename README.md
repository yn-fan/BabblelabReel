# BabblelabReel

从 Emma Reel 独立拆出的完整视频技能包。无需安装 Emma；保留原有制作流程、
脚本、模板、素材索引、参考资料和测试。公开名字为 **BabblelabReel**，
机器标识为 `babblelabreel`。内部 `skills/reel/` 路径保留以兼容脚本。

## 包含什么

| 能力 | 包含内容与边界 |
|---|---|
| 视频下载 | 抖音、小红书、B站、YouTube、Instagram 链接识别、授权下载、画质选择、文件验证与保存位置展示。平台/登录限制仍然存在；微信视频号是客户端辅助路径 |
| 视频压缩 | 本地 FFmpeg 普通压缩、目标 MB 上限、按需缩放、完整输出验证；保留原片。首版不自动转换 HDR、可变帧率和旋转等不支持输入 |
| 素材混剪 | 片段选择、拼接转场、字幕、音轨混合、配音压低背景音乐、MP4 导出 |
| 分镜与节拍 | 素材探测、联系表/分镜预览、音乐起音检测、剪切点对齐建议；不把起音候选当成可靠 BPM 网格 |
| Remotion | 完整 TypeScript 模板、字幕/旁白/音乐轨、署名组件、产品发布和愿景视频预设、故事及音乐验证脚本 |
| BGM | 情绪匹配、托管 AI 与已有本地 ACE-Step 服务适配、AI 不可用时授权曲库回退、许可证/来源记录、淡入淡出与旁白避让 |
| TTS | 完整 Audio Generator：英文基础模式和 Kokoro 增强模式，WAV 与来源记录。增强模型需另行下载；不包含中文 TTS |
| 图片生成 | Microsoft 365 Copilot、MAI Playground 的可见浏览器流程，以及 Azure OpenAI 的发现/配置/生成脚本；仍需相应工具和账号 |
| 剪映草稿 | 实验性国内桌面剪映草稿适配、分轨、转场/关键帧交付说明；不是剪映软件，Mac 打开/最终导出仍未验证 |

曲库包内是音乐目录、检索适配器和许可处理，不包含第三方音乐录音全集。
模型权重、FFmpeg、yt-dlp、Node、Remotion 的 node_modules、剪映软件、账号、
cookies、API 密钥以及个人素材都没有打包。安装技能不等于这些依赖已经可用。

## Install

### 方式一：作为 GitHub Copilot CLI 本地插件

解压后保留整个文件夹，不能只复制内部 `SKILL.md`。在终端执行，路径改为
你实际保存的位置：

无需安装，先在一个新会话中加载：

```bash
copilot --plugin-dir "/absolute/path/to/BabblelabReel"
```

若要持久安装，再执行：

```bash
copilot plugin marketplace add "/absolute/path/to/BabblelabReel"
copilot plugin install babblelabreel@babblelab
```

新建 Copilot 会话，选择 **BabblelabReel** agent 或调用 `babblelabreel` 技能。
插件带有独立的主技能、配音子技能和图片子技能，不会替换已有 Emma。
上述命令需要支持插件及本地 marketplace 的 Copilot CLI；不是普通网页聊天命令。
本次交付仅创建包，没有改动你的实际插件安装或注册。

### 方式二：在支持本地 Skills 的工具里使用

把**整个** `BabblelabReel` 文件夹放进该工具支持的 skill 目录，使用根目录
`SKILL.md` 作为入口。或者让可读取本地文件的 Agent 读取本包 `AGENTS.md`。
没有 Skills/终端/文件访问能力的聊天窗口无法仅靠上传 ZIP 自动执行这些脚本。

## 直接这样说

- “用 BabblelabReel 把这个视频压到 20 MB 以内，保留原文件。”
- “这些视频我有使用授权，下载后混剪成 30 秒短片。”
- “根据这些产品截图制作演示视频，先给我看分镜。”
- “按视频情绪匹配配乐，AI 做不了就选授权曲库。”
- “用增强模式把这份英文稿生成旁白。”
- “用这些片段生成可继续修改的剪映草稿。”

## 首次使用

Agent 按任务检查依赖，缺少时先征得安装同意。也可以进入本包目录手动查看：

```bash
python3 skills/reel/scripts/preflight_reel.py --engine compress
python3 skills/reel/scripts/preflight_reel.py --engine ffmpeg
python3 skills/reel/scripts/preflight_reel.py --engine remotion
python3 skills/reel/scripts/preflight_reel.py --engine download
python3 skills/reel/scripts/preflight_reel.py --engine jianying
python3 tools/audio-generator/scripts/kokoro_audio.py preflight --mode enhanced
```

这是依赖诊断，不会自动安装模型或工具。音频增强模式需要兼容的 Python；
具体版本和依赖见 `tools/audio-generator/references/compatibility.md`。
完整使用说明见 [视频快速开始](skills/reel/references/quickstart.md)。

## 文件保存与隔离

沿用包内路径解析器，使用独立的 `BABBLELABREEL_USER_HOME` 环境变量。例如：

```bash
export BABBLELABREEL_USER_HOME="$HOME/BabblelabReelData"
python3 tools/scripts/user_paths.py home
```

未配置时，在可用的 OneDrive 下使用 `BabblelabReel` 文件夹，否则使用
`~/BabblelabReel`。不读取 Emma 的用户配置，不复制或迁移原有 Emma 产物。
不要把产物写进安装缓存。下载、模型与付费服务仍受原来的授权规则约束。

## 来源、验证和更新

`PROVENANCE.json` 记录源代码提交与完整文件清单；
`SHA256SUMS.json` 可供完整性比对。`VERIFICATION.md` 记录本次打包验证范围。
这是本地独立快照，不会自动跟随 Emma 更新。

保留来源署名与第三方依赖/模型/素材的许可边界。原仓库未授予新的开源
再分发许可；本包不擅自把源代码、模型或音乐改为 MIT 等许可证。
对外发布前需确认你拥有所需权限。
