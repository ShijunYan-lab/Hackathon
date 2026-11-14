extends RefCounted
const Catalog=preload("res://maps/npc_catalog.gd")
static var font:SystemFont

static func descriptor(key:String)->Dictionary:
	var entries:Array=Catalog.entries()
	for entry in entries:
		if entry.appearance_key==key: return entry.duplicate(true)
	return entries[absi(key.hash())%entries.size()].duplicate(true)

static func texture_for(key:String,is_player:bool,female:bool=false)->Texture2D:
	return load("res://assets/characters/"+("player_female" if female else "player_male")+".png") if is_player else load("res://assets/characters/"+str(descriptor(key).appearance_key)+".png")

static func build(key:String,is_player:bool,female:bool=false)->SpriteFrames:
	var sheet:=texture_for(key,is_player,female)
	var frames:=SpriteFrames.new()
	frames.remove_animation("default")
	for row in range(4 if is_player else 1):
		for action in ["idle","run","sprint","attack","hurt","death","dodge"]:
			var anim:String=action+str(row) if is_player else action
			frames.add_animation(anim)
			frames.set_animation_loop(anim,action in ["idle","run","sprint"])
			frames.set_animation_speed(anim,12 if action=="sprint" else 8)
			var columns:Array=[0]
			if is_player:
				if action in ["run","sprint","dodge"]: columns=[1,2,3,4,5,6]
			else:
				if action=="idle": columns=[0,1,2]
				if action in ["run","sprint","dodge"]: columns=[3,4,5,6]
				if action=="attack": columns=[7,8,9,10,11]
			for column in columns:
				var atlas:=AtlasTexture.new()
				atlas.atlas=sheet
				atlas.region=Rect2(column*48,row*64,48,64)
				frames.add_frame(anim,atlas)
	# Base A controller's one-shot effects use these unsuffixed names.
	if is_player:
		for action in ["idle","run","sprint","attack","hurt","death","dodge"]:
			frames.add_animation(action)
			frames.set_animation_loop(action,action in ["idle","run","sprint"])
			for i in range(frames.get_frame_count(action+"0")):
				frames.add_frame(action,frames.get_frame_texture(action+"0",i))
	return frames

static func draw_actor(actor:Node2D,hp:int,max_hp:int,alive:bool,label:String)->void:
	if font==null:
		font=SystemFont.new()
		font.font_names=PackedStringArray(["Microsoft YaHei","sans-serif"])
	actor.draw_set_transform(Vector2.ZERO,0,Vector2(1,0.4))
	actor.draw_circle(Vector2.ZERO,13,Color(0.03,0.03,0.04,0.35))
	actor.draw_set_transform(Vector2.ZERO)
	if alive and hp<max_hp:
		actor.draw_rect(Rect2(-18,-67,36,4),Color("211c21"))
		actor.draw_rect(Rect2(-17,-66,34.0*hp/max_hp,2),Color("b68164"))
	# Names are learned through conversation; never draw a world-space identity label.
