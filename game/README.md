# Godot Client — 《未定之境》

Godot 4.5.2 Standard / GDScript / Compatibility / 640×360（窗口放大至 1280×720）。

**目前 `main.tscn` 是 A 模块的连续世界 MOCK 测试**，不连接真实 LLM 或后端。F5 可测试移动、战斗、NPC 路径、背包、钱币、掉落。正式游戏由 D 集成时换成自己的主场景，但复用 `maps/seamless_world.tscn`、`actors/*.tscn` 和接口。

详见 [`INTEGRATION_V4.md`](INTEGRATION_V4.md)：控制方式、文件所有权、装备槽、单地图全局坐标、NPC 动态生成以及必须由 C 升级的协议。
