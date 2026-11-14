extends SceneTree
## Same authored geometry as realm.tscn, exported as C's single continuous region.
const Layout=preload("res://maps/world_layout.gd")
func _initialize()->void:
	var layout:=Layout.new()
	layout.build()
	var cells:Array=[]
	for cell in layout.blocked: cells.append([cell.x,cell.y])
	var spawns:Array=[]
	for npc in preload("res://maps/npc_catalog.gd").entries():
		var p:=clear_tile(layout,npc.tile)
		spawns.append({"name":npc.name,"appearance_key":npc.appearance_key,"role":npc.role,"place":npc.place,"goals":[npc.work],"tile":{"x":p.x,"y":p.y}})
	var sites:Array=[]
	for entry in [["herb",Vector2(84.5,96.5)],["iron",Vector2(83.5,169.5)],["wood",Vector2(89.5,96.5)],["herb",Vector2(245.5,168.5)]]:
		var p:=clear_tile(layout,entry[1])
		sites.append({"id":"site_"+str(sites.size()),"kind":entry[0],"region_id":"overworld","tile":{"x":p.x,"y":p.y},"remaining":20})
	var region:={"id":"overworld","reactive_npcs":true,"width_tiles":320,"height_tiles":224,"spawn_tile":{"x":Layout.SPAWN.x/32,"y":Layout.SPAWN.y/32},"blocked_tiles":cells,"npc_spawns":spawns,"sites":sites,"starter_weapons":["sword","axe","hammer","bow","crossbow","staff"]}
	FileAccess.open("res://maps/backend_world.json",FileAccess.WRITE).store_string(JSON.stringify({"schema_version":"v1","fixture_only":false,"tile_size_px":32,"regions":[region]}))
	var places:Array=[]
	for place in layout.landmarks:
		var p:Vector2=place.pos
		if place.kind=="village": p+=Vector2(0,4)
		if layout.blocked.has(Vector2i(p)): continue
		places.append({"id":"place_"+str(places.size()),"name":place.name,"region_id":"overworld","tile":{"x":p.x,"y":p.y},"tags":[place.kind,"migration_entry"] if place.kind=="village" else [place.kind]})
	FileAccess.open("res://maps/director_locations.json",FileAccess.WRITE).store_string(JSON.stringify({"enabled":true,"interval_ticks":3,"timeout_s":9,"npc_alive_limit":24,"max_proposals":2,"locations":places},"  "))
	print("BACKEND MAP: ",cells.size()," blocked cells, ",spawns.size()," NPC templates, ",sites.size()," resources.")
	quit()

func clear_tile(layout,point:Vector2)->Vector2:
	for radius in range(12):
		for y in range(-radius,radius+1):
			for x in range(-radius,radius+1):
				var cell:=Vector2i(point)+Vector2i(x,y)
				if not layout.blocked.has(cell): return Vector2(cell)+Vector2(0.5,0.5)
	assert(false,"No walkable authored spawn")
	return point
