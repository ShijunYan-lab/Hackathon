extends SceneTree
## Godot asset importer: source artwork remains unchanged in references/.
## Bounds, alpha masks and integer sampling turn the provided layouts into game frames.
const SOURCE := "res://assets/references/"
const OUT := "res://assets/characters/"
var manifest := {"frame_size":[48,64],"source_policy":"Original user artwork, cropped and nearest-neighbour fitted; no generative redraw.","actors":{}}

func _initialize() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	player()
	npcs("village",["holt","elena","bronn","marta","renard"],[116,315,512,707,903],[229,431,625,820,1019])
	npcs("forest",["glen","scott","leah","vick","orwen"],[132,328,518,701,891],[250,444,640,828,1020])
	npcs("ruins",["kyra","severin","morris","gareth","gravekeeper"],[138,317,497,673,852],[247,431,610,787,978])
	FileAccess.open(OUT+"source_manifest.json",FileAccess.WRITE).store_string(JSON.stringify(manifest,"  "))
	print("REFERENCE ACTORS: 2 player appearances + 15 NPCs; every cell exactly 48x64.")
	quit()

func cutout(source: Image,roi: Rect2i,transparent: bool=false) -> Image:
	var crop := source.get_region(roi)
	crop.convert(Image.FORMAT_RGBA8)
	if not transparent:
		var raw:=crop.duplicate() as Image
		# Flood only the dark paper connected to the edge, preserving enclosed dark detail.
		var width:=crop.get_width()
		var height:=crop.get_height()
		var seen:=PackedByteArray()
		seen.resize(width*height)
		var stack:Array[Vector2i]=[]
		for x in range(width):
			stack.append(Vector2i(x,0))
			stack.append(Vector2i(x,height-1))
		for y in range(height):
			stack.append(Vector2i(0,y))
			stack.append(Vector2i(width-1,y))
		while not stack.is_empty():
			var p:Vector2i=stack.pop_back()
			if p.x<0 or p.x>=width or p.y<0 or p.y>=height: continue
			var idx:=p.y*width+p.x
			if seen[idx]: continue
			seen[idx]=1
			var c:=crop.get_pixelv(p)
			if maxf(c.r,maxf(c.g,c.b))>0.22: continue
			crop.set_pixelv(p,Color.TRANSPARENT)
			for d in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]: stack.append(p+d)
		remove_sheet_fragments(crop)
		# Restore narrow dark seams/boots from the original pixels; they share the paper's
		# value but belong inside the character silhouette. No color is painted over them.
		for y in range(height):
			var previous:=-1
			for x in range(width):
				if crop.get_pixel(x,y).a>0:
					if previous>=0 and x-previous<=12:
						for fill_x in range(previous+1,x): crop.set_pixel(fill_x,y,raw.get_pixel(fill_x,y))
					previous=x
		for x in range(width):
			var previous:=-1
			for y in range(height):
				if crop.get_pixel(x,y).a>0:
					if previous>=0 and y-previous<=9:
						for fill_y in range(previous+1,y): crop.set_pixel(x,fill_y,raw.get_pixel(x,fill_y))
					previous=y
		# Retain one source pixel of the dark outline around the extracted silhouette.
		var mask:=crop.duplicate() as Image
		for y in range(1,height-1):
			for x in range(1,width-1):
				if mask.get_pixel(x,y).a>0: continue
				for d in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]:
					if mask.get_pixelv(Vector2i(x,y)+d).a>0:
						crop.set_pixel(x,y,raw.get_pixel(x,y))
						break
	var bounds:=crop.get_used_rect()
	if bounds.has_area(): return crop.get_region(bounds)
	return crop

func remove_sheet_fragments(crop:Image)->void:
	# A layout cell can touch an ornamental divider or a neighboring sprite.
	# Keep the main component, exclude edge-truncated neighbors and paper speckles.
	var width:=crop.get_width()
	var height:=crop.get_height()
	var seen:=PackedByteArray()
	seen.resize(width*height)
	var components:Array=[]
	var largest:=0
	for y in range(height):
		for x in range(width):
			if seen[y*width+x] or crop.get_pixel(x,y).a==0: continue
			var stack:Array[Vector2i]=[Vector2i(x,y)]
			var pixels:Array[Vector2i]=[]
			var edge:=false
			while not stack.is_empty():
				var p:Vector2i=stack.pop_back()
				if p.x<0 or p.y<0 or p.x>=width or p.y>=height: continue
				var index:=p.y*width+p.x
				if seen[index]: continue
				seen[index]=1
				if crop.get_pixelv(p).a==0: continue
				pixels.append(p)
				if p.x==0 or p.y==0 or p.x==width-1 or p.y==height-1: edge=true
				for d in [Vector2i.LEFT,Vector2i.RIGHT,Vector2i.UP,Vector2i.DOWN]: stack.append(p+d)
			largest=maxi(largest,pixels.size())
			var bounds:=Rect2i(Vector2i(x,y),Vector2i.ONE)
			for p in pixels: bounds=bounds.expand(p)
			components.append({"pixels":pixels,"edge":edge,"bounds":bounds})
	for part in components:
		var size:Vector2i=part.bounds.size
		var divider:bool=part.edge and (size.x>size.y*8 or size.y>size.x*8)
		var neighbor:bool=part.edge and part.pixels.size()<largest and (part.bounds.position.x>width*0.73 or part.bounds.end.x<width*0.23)
		if part.pixels.size()<10 or divider or neighbor or (part.edge and part.pixels.size()<70):
			for p in part.pixels: crop.set_pixelv(p,Color.TRANSPARENT)

func fit_frame(source:Image,w:int=48,h:int=64) -> Image:
	var result:=Image.create(w,h,false,Image.FORMAT_RGBA8)
	var factor:=minf(float(w-2)/source.get_width(),float(h-2)/source.get_height())
	var resized:=source.duplicate() as Image
	resized.resize(maxi(1,roundi(source.get_width()*factor)),maxi(1,roundi(source.get_height()*factor)),Image.INTERPOLATE_NEAREST)
	result.blit_rect(resized,Rect2i(Vector2i.ZERO,resized.get_size()),Vector2i((w-resized.get_width())/2,h-resized.get_height()-1))
	return result

func player() -> void:
	var original:=Image.load_from_file(SOURCE+"player_original.png")
	# Original image five: front/profile/back/profile, kept in the supplied design.
	var rois := [
		[Rect2i(275,96,195,282),Rect2i(555,96,184,282),Rect2i(278,480,188,290),Rect2i(555,480,184,290)],
		[Rect2i(1027,111,202,267),Rect2i(1320,113,201,265),Rect2i(1027,506,202,264),Rect2i(1324,506,197,264)]]
	for gender in range(2):
		var sheet:=Image.create(48*8,64*4,false,Image.FORMAT_RGBA8)
		var directions: Array=[rois[gender][0],rois[gender][3],rois[gender][1],rois[gender][2]]
		for direction in range(4):
			var base:=fit_frame(cutout(original,directions[direction],true))
			if gender==1 and direction==2: base.flip_x()
			for frame in range(8):
				var pose:=base.duplicate() as Image
				if frame>0:
					# Animate the actual reference pixels; keep face, hair and clothing identity.
					pose.fill(Color.TRANSPARENT)
					var phase:=sin(float(frame-1)/6.0*TAU)
					for y in range(64):
						for x in range(48):
							var shift:=0
							if y>45: shift=roundi(phase*(1 if x<24 else -1))
							var bob:=1 if frame in [2,3,5,6] and y<54 else 0
							var dest:=Vector2i(clampi(x+shift,0,47),clampi(y-bob,0,63))
							pose.set_pixelv(dest,base.get_pixel(x,y))
				sheet.blit_rect(pose,Rect2i(0,0,48,64),Vector2i(frame*48,direction*64))
		var key:="player_female" if gender else "player_male"
		sheet.save_png(OUT+key+".png")
		manifest.actors[key]={"source":"player_original.png","directions":["down","left","right","up"],"columns":8,"rows":4,"animation":"Reference-pixel deformation for walking; source has static directional views."}

func npcs(group:String,ids:Array,tops:Array,bottoms:Array) -> void:
	var original:=Image.load_from_file(SOURCE+"npc_"+group+".png")
	# Source sheets already contain the requested idle, walking and attack poses.
	var columns: Array = [Vector2i(430,509),Vector2i(510,584),Vector2i(585,660),Vector2i(674,747),Vector2i(748,820),Vector2i(821,893),Vector2i(894,967),Vector2i(979,1069),Vector2i(1070,1158),Vector2i(1159,1247),Vector2i(1248,1336),Vector2i(1337,1427)]
	if group=="village": columns=[Vector2i(452,532),Vector2i(533,606),Vector2i(607,687),Vector2i(703,773),Vector2i(775,837),Vector2i(838,901),Vector2i(902,962),Vector2i(984,1070),Vector2i(1071,1156),Vector2i(1157,1242),Vector2i(1243,1335),Vector2i(1336,1427)]
	if group=="ruins": columns=[Vector2i(473,540),Vector2i(541,608),Vector2i(609,674),Vector2i(692,761),Vector2i(762,830),Vector2i(831,896),Vector2i(897,963),Vector2i(980,1064),Vector2i(1065,1145),Vector2i(1146,1227),Vector2i(1228,1321),Vector2i(1322,1421)]
	for row in range(5):
		var sheet:=Image.create(48*12,64,false,Image.FORMAT_RGBA8)
		for col in range(12):
			var bounds:Vector2i=columns[col]
			var roi:=Rect2i(bounds.x,tops[row],bounds.y-bounds.x,bottoms[row]-tops[row])
			var actor:=fit_frame(cutout(original,roi))
			sheet.blit_rect(actor,Rect2i(0,0,48,64),Vector2i(col*48,0))
		var key:String=ids[row]
		sheet.save_png(OUT+key+".png")
		manifest.actors[key]={"source":"npc_"+group+".png","source_row":row,"columns":12,"rows":1,"animations":{"idle":[0,1,2],"walk":[3,4,5,6],"attack":[7,8,9,10,11]}}
