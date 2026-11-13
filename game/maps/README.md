# 单张连续世界地图

- `seamless_world.tscn` 是一张 96×60 格（每格 32px）的连续地图，含村镇、森林、遗迹及跨河木桥。
- `seamless_world.gd` 使用 `AStarGrid2D` 和静态碰撞；`find_path(start_px, end_px)` 返回所有路点（像素坐标），NPC 可跨区域走动。
- 玩家场景含 Camera2D，镜头平滑跟随并受到世界边界限制。不再使用 T 键切场景。
- `overworld_data.json` 定义地图大小、spawn、障碍格和生态区标签；**它是当前客户端地图权威文件**，联调时要与 C 的世界坐标和地图阻挡规则统一。
- 这是一张可运行的程序化像素底图；D 可以替换成更精美的 TileMapLayer 美术，但要保留数据坐标和导航一致性。

**当前 A 原型未修改 `shared/regions.json`，真实后端需要由 C/D 协商同步成 `overworld`。**
