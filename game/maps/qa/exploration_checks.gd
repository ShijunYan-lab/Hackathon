extends SceneTree
## V2 integration: real scene, real physics, native UI and exported shared coordinates.
const Layout=preload("res://maps/world_layout.gd")
var game:Node2D
var passed:=0
var failed:=0
func _initialize()->void: call_deferred("run")
func check(ok:bool,label:String)->void:
	if ok:
		passed+=1
		print("PASS ",label)
	else:
		failed+=1
		push_error("FAIL "+label)
func frames(count:int)->void:
	for i in range(count): await physics_frame
func walk(start:Vector2,actions:Array,count:int)->Vector2:
	game.player.position=start
	await frames(2)
	for action in actions: Input.action_press(action)
	await frames(count)
	for action in actions: Input.action_release(action)
	await frames(2)
	return game.player.position
func action(name:String)->void:
	var event:=InputEventAction.new()
	event.action=name
	event.pressed=true
	Input.parse_input_event(event)
	await process_frame
	event=InputEventAction.new()
	event.action=name
	event.pressed=false
	Input.parse_input_event(event)
	await process_frame
func run()->void:
	game=load("res://maps/offline_preview.tscn").instantiate()
	root.add_child(game)
	await frames(5)
	for npc in game.npcs: npc.movement_enabled=false
	var terrain:TileMapLayer=game.get_node("World/Terrain")
	check(terrain.get_used_cells().size()==71680,"71,680 editable native terrain cells; 4x original area")
	check(game.get_node("World/Entities").y_sort_enabled,"environment and actors use Y sorting")
	var forest_has_road:=false
	for y in range(112):
		for x in range(320):
			if terrain.get_cell_atlas_coords(Vector2i(x,y)).y==2: forest_has_road=true
	check(not forest_has_road,"entire enlarged forest has no dirt paths")
	check(game.get_node_or_null("FieldOfView")==null and game.get_node_or_null("Fog")==null,"no circular sight mask attached to main scene")
	for pair in [["move_left",KEY_LEFT],["move_right",KEY_RIGHT],["move_up",KEY_UP],["move_down",KEY_DOWN]]:
		var key:=InputEventKey.new()
		key.physical_keycode=pair[1]
		check(InputMap.event_is_action(key,pair[0]),"arrow input "+pair[0])
	check(game.player.sprite.texture.get_size()/Vector2(8,4)==Vector2(48,64),"male player uses exactly 48x64 frames")
	var original:Texture2D=game.player.sprite.texture
	game.player.switch_appearance()
	check(game.player.sprite.texture!=original and game.player.sprite.texture.get_size()/Vector2(8,4)==Vector2(48,64),"female source artwork switches and also uses 48x64 frames")
	game.player.switch_appearance()
	check(game.npcs.size()==15,"all 15 supplied NPC designs present")
	for npc in game.npcs:
		check(npc.sprite.texture.get_size()/Vector2(12,1)==Vector2(48,64),npc.data.appearance_key+" has 48x64 idle, walking and attack frames")
	var start:=Layout.SPAWN
	var end:=await walk(start,["move_right"],24)
	check(end.x-start.x>55 and end.x-start.x<68,"production player moves with input at walking speed")
	check(game.player.direction==2,"movement selects right-facing source art")
	end=await walk(start,["move_right","sprint"],24)
	check(end.x-start.x>92,"Shift increases real movement speed")
	game.player.set_controls_locked(true)
	end=await walk(start,["move_right"],15)
	check(end.distance_to(start)<0.1,"input lock prevents walking")
	game.player.set_controls_locked(false)
	var layout:=Layout.new()
	for bridge_y in [143,202]:
		var rx:=roundi(layout.river_x(bridge_y))
		end=await walk(Vector2(rx-10.5,bridge_y+0.5)*32,["move_right","sprint"],180)
		check(end.x>(rx+10)*32,"real player crosses bridge at y="+str(bridge_y))
	var river:=layout.river_x(155)
	end=await walk(Vector2(river-7.5,155.5)*32,["move_right","sprint"],75)
	check(end.x<(river-3)*32,"river blocks travel away from bridges")
	for edge in [[Vector2(45,5400),"move_left"],[Vector2(10195,5400),"move_right"],[Vector2(4000,45),"move_up"],[Vector2(4000,7120),"move_down"]]:
		end=await walk(edge[0],[edge[1],"sprint"],18)
		check(end.x>=39 and end.x<=10201 and end.y>=41 and end.y<=7133,"air wall/clamp prevents escape "+edge[1])
	for endpoints in [[Vector2(60,5400),Vector2(-60,5400)],[Vector2(10170,5400),Vector2(10300,5400)],[Vector2(4000,60),Vector2(4000,-60)],[Vector2(4000,7100),Vector2(4000,7230)]]:
		var query:=PhysicsRayQueryParameters2D.create(endpoints[0],endpoints[1],1)
		check(not game.get_world_2d().direct_space_state.intersect_ray(query).is_empty(),"physical boundary collider "+str(endpoints[1]))
	game.player.position=game.npcs[0].position+Vector2(0,45)
	await frames(12)
	await action("interact")
	check(game.hud.dialog_open and game.hud.current_npc==game.npcs[0],"E opens nearby named NPC dialogue")
	check(game.player.locked and game.npcs[0].talking,"dialogue locks player and talking NPC")
	var before:int=game.hud.message_count
	game.hud.entry.text="附近有什么传闻？"
	game.hud.entry.text_submitted.emit(game.hud.entry.text)
	check(game.hud.message_count==before+1 and game.hud.transcript.get_parsed_text().contains("商队"),"Chinese text submission appends original local dialogue")
	game.hud.submit_text("   ")
	check(game.hud.message_count==before+1,"empty chat is ignored")
	game.hud.topic_buttons[1].pressed.emit()
	check(game.hud.transcript.get_parsed_text().contains("刃口"),"craft topic uses the selected NPC's content")
	var locked_texture:Texture2D=game.player.sprite.texture
	await action("appearance")
	check(game.player.sprite.texture==locked_texture,"typing appearance shortcut cannot change avatar during dialogue")
	await action("ui_cancel")
	check(not game.hud.dialog_open and not game.player.locked and not game.npcs[0].talking,"Esc closes dialogue and restores movement")
	await action("toggle_map")
	check(game.hud.map_open and game.player.locked,"M opens world map and locks movement")
	await action("ui_cancel")
	check(not game.hud.map_open and not game.player.locked,"Esc closes world map")
	game.player.position=Layout.SPAWN
	await frames(2)
	var checkpoint:Dictionary=game.player.collect_checkpoint()
	check(checkpoint.region_id=="market" and checkpoint.positions[0].tile.y<112,"checkpoint reports region-local tiles")
	check_regions_and_routes()
	print("RESULT ",passed," passed / ",failed," failed")
	quit(1 if failed else 0)
func check_regions_and_routes()->void:
	var data:Dictionary=JSON.parse_string(FileAccess.get_file_as_string("res://../shared/regions.json"))
	var blocked:Dictionary={}
	var grid:=AStarGrid2D.new()
	grid.region=Rect2i(Vector2i.ZERO,Layout.SIZE)
	grid.diagonal_mode=AStarGrid2D.DIAGONAL_MODE_NEVER
	grid.update()
	for region in data.regions:
		var offset:Vector2i=Layout.REGIONS[region.id].position
		for cell in region.blocked_tiles:
			var world_cell:=Vector2i(int(cell.x),int(cell.y))+offset
			blocked[world_cell]=true
			grid.set_point_solid(world_cell)
	for region in data.regions:
		var offset:Vector2i=Layout.REGIONS[region.id].position
		var spawn:=Vector2i(int(region.spawn_tile.x),int(region.spawn_tile.y))+offset
		check(not blocked.has(spawn),region.id+" shared spawn is clear")
		for e in region.exits:
			var src:=Vector2i(int(e.tile.x),int(e.tile.y))+offset
			var dst:Vector2i=Vector2i(int(e.destination_tile.x),int(e.destination_tile.y))+Layout.REGIONS[e.destination_region_id].position
			check(not blocked.has(src) and not blocked.has(dst),e.id+" shared exit endpoints are clear")
	var origin:=Vector2i(Layout.SPAWN/32)
	for target in [Vector2i(246,165),Vector2i(76,111),Vector2i(250,111),Vector2i(237,50),Vector2i(191,78),Vector2i(165,176),Vector2i(89,94),Vector2i(41,194),Vector2i(267,107)]:
		check(not grid.get_id_path(origin,target).is_empty(),"continuous grid route to "+str(target))
	for npc in game.npcs:
		var cell:=Vector2i(npc.home/32)
		check(not blocked.has(cell) and not grid.get_id_path(origin,cell).is_empty(),"NPC reachable without teleport: "+str(npc.data.name))
	# Close every alternate crossing to prove two independent village routes.
	for y in range(82,92):
		for x in range(140,180): grid.set_point_solid(Vector2i(x,y))
	for y in range(198,207):
		for x in range(140,180): grid.set_point_solid(Vector2i(x,y))
	check(not grid.get_id_path(origin,Vector2i(246,165)).is_empty(),"north route connects villages with other crossings closed")
	for y in range(198,207):
		for x in range(140,180): grid.set_point_solid(Vector2i(x,y),blocked.has(Vector2i(x,y)))
	for y in range(138,148):
		for x in range(140,180): grid.set_point_solid(Vector2i(x,y))
	check(not grid.get_id_path(origin,Vector2i(246,165)).is_empty(),"south route connects villages with other crossings closed")
