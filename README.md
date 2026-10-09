# BabblelabReel

**BabblelabReel** 是一个可独立使用的视频创作技能包，支持视频下载、压缩、
素材混剪、分镜、配乐、英文配音、图片生成和剪映草稿交付。
包含制作流程、脚本、模板、素材索引、参考资料和测试，技能名为 `babblelabreel`。

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
| 图片生成 | 支持已适配服务的浏览器操作流程与 API 配置、生成脚本；需相应工具、账号和服务权限，具体支持范围见包内图片生成说明 |
| 剪映草稿 | 实验性国内桌面剪映草稿适配、分轨、转场/关键帧交付说明；不是剪映软件，Mac 打开/最终导出仍未验证 |

曲库包内是音乐目录、检索适配器和许可处理，不包含第三方音乐录音全集。
模型权重、FFmpeg、yt-dlp、Node、Remotion 的 node_modules、剪映软件、账号、
cookies、API 密钥以及个人素材都没有打包。安装技能不等于这些依赖已经可用。

## 安装到 Codex 或 Claude Code

在 Codex 或 Claude Code 中发送：

```text
Install https://github.com/yn-fan/BabblelabReel as a personal skill. Keep the entire repo intact.
```

完整仓库的根目录 `SKILL.md` 是技能入口；请保留所有子目录，不能只复制单个文件。
安装完成后，说“用 babblelabreel……”即可开始。如果没有识别到技能，新建会话或重启工具再试。
FFmpeg、配音模型等外部依赖按具体任务安装。Claude 普通网页对话不适用上述本地安装方式。

### 其他支持本地 Skills 的工具

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

未配置时，优先在路径解析器检测到的可用云盘目录下使用 `BabblelabReel` 文件夹，
否则使用 `~/BabblelabReel`。用户配置和产物独立保存。
如需固定保存位置，请显式设置上面的环境变量。
不要把产物写进安装缓存。下载、模型与付费服务仍受原来的授权规则约束。

## 来源、验证和更新

`PROVENANCE.json` 记录源代码提交与完整文件清单；
`SHA256SUMS.json` 可供完整性比对。`VERIFICATION.md` 记录本次打包验证范围。
这是独立快照，不会自动同步上游更新。

来源署名与第三方许可说明见 [NOTICE.md](NOTICE.md)。
本包不另行授予源代码、模型或音乐的开源许可；使用与再分发须遵守各自的许可条件。
