# 素材来源 · D 维护 · 2026-11-14

| 素材 | 来源与处理 |
|---|---|
| references/player_original.png | 用户指定 D:\google_download\紫晶幻想角色精灵图-2.png，第五张玩家参考图，原样复制 |
| references/npc_*.png | 用户提供的村庄、森林、遗迹动作图和 NPC 总览；原名与 SHA-256 见 references/SOURCES.json |
| characters/*.png | Godot 从用户原图裁切、去除设定图底色、最近邻适配到 48×64；参考图权利归原权利人 |
| painted/architecture_source.png | 内置 ImageGen 本轮生成的九种建筑图集 |
| painted/nature_source.png | 内置 ImageGen 本轮生成的树木、集市、营地和船等图集 |
| painted/props_source.png | 内置 ImageGen 本轮生成的木桶、箱子、栅栏、石柱、花草等十六种细节图集 |
| environment/*.png | Godot 切分上述图集；地形和部分细节由 build_environment.gd 绘制 |
| pixel/*.png | 第一版由 pixel_art.gd 绘制的历史素材；当前工程保留部分环境物件 |
| maps/world_chart.png | Godot 根据本项目布局生成，无第三方底图 |
| 中文字形 | Godot SystemFont 使用本机系统字体，未打包微软雅黑等字体文件 |

建筑、环境、布局、地点和对白为本项目生成/编写，没有从《紫色晶石》游戏包提取素材或复制对白。风格研究参考官方 [Steam 商店](https://store.steampowered.com/app/625960/_?l=schinese)、[Osbrook](https://stoneshard.com/wiki/Osbrook)、[Mannshire](https://stoneshard.com/wiki/Mannshire)：乡镇服务设施、农田/磨坊、低饱和材质、深色铜边界面。相关生成规格记录在 [painted/PROMPTS.md](painted/PROMPTS.md)。

本轮无第三方音效或音乐。Godot 使用 MIT 许可；交付为工程源文件，不包含引擎二进制。
