extends SceneTree
var stage:Node2D
var pose:=0
var players:=false
var sheet_group:=-1
var font:SystemFont
var entries:=preload("res://maps/npc_catalog.gd").entries()
var textures:Dictionary={}
func _initialize()->void: call_deferred("run")
func draw_gallery()->void:
	stage.draw_rect(Rect2(0,0,800,450),Color("65694d"))
	if sheet_group>=0:
		stage.draw_string(font,Vector2(177,17),"待机 · 3 帧                  行走 · 4 帧                          攻击 · 5 帧",HORIZONTAL_ALIGNMENT_LEFT,-1,12,Color("fff0ce"))
		for row in range(5):
			var actor:Dictionary=entries[sheet_group*5+row]
			var y:=28+row*82
			stage.draw_string(font,Vector2(20,y+37),actor.name,HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color("fff0ce"))
			stage.draw_texture_rect(textures[actor.appearance_key],Rect2(176,y,576,64),false)
	elif players:
		for gender in range(2):
			var texture:Texture2D=textures["player_female" if gender else "player_male"]
			for dir in range(4):
				var p:=Vector2(94+dir*180,30+gender*205)
				stage.draw_texture_rect_region(texture,Rect2(p,Vector2(96,128)),Rect2(pose*48,dir*64,48,64))
				stage.draw_string(font,p+Vector2(-12,153),("女" if gender else "男")+" · "+["正面","向左","向右","背面"][dir],HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color("fff0ce"))
	else:
		for i in range(entries.size()):
			var p:=Vector2(45+(i%5)*158,6+(i/5)*148)
			var texture:Texture2D=textures[entries[i].appearance_key]
			stage.draw_texture_rect_region(texture,Rect2(p,Vector2(90,120)),Rect2(pose*48,0,48,64))
			stage.draw_string(font,p+Vector2(3,138),entries[i].name,HORIZONTAL_ALIGNMENT_LEFT,-1,15,Color("fff0ce"))
func run()->void:
	for actor in entries:
		textures[actor.appearance_key]=load("res://assets/characters/"+actor.appearance_key+".png")
	for key in ["player_male","player_female"]: textures[key]=load("res://assets/characters/"+key+".png")
	font=SystemFont.new()
	font.font_names=PackedStringArray(["Microsoft YaHei"])
	stage=Node2D.new()
	stage.texture_filter=CanvasItem.TEXTURE_FILTER_NEAREST
	stage.draw.connect(draw_gallery)
	root.add_child(stage)
	for phase in [[0,"idle"],[4,"walk"],[9,"attack"]]:
		pose=phase[0]
		stage.queue_redraw()
		for i in range(3): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../release/previews/v2_npcs_"+phase[1]+".png")
	players=true
	pose=0
	stage.queue_redraw()
	for i in range(3): await process_frame
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png("res://../release/previews/v2_player_directions.png")
	for group in range(3):
		sheet_group=group
		stage.queue_redraw()
		for i in range(3): await process_frame
		await RenderingServer.frame_post_draw
		root.get_texture().get_image().save_png("res://../release/previews/v2_sheet_"+["village","forest","ruins"][group]+".png")
	quit()
