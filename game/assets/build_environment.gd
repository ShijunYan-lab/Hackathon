extends SceneTree
## Technical sprite-atlas slicing and Godot-authored terrain/detail tiles.
const OUT:="res://assets/environment/"
var im:Image
var rng:=RandomNumberGenerator.new()

func _initialize()->void:
	DirAccess.make_dir_recursive_absolute(OUT)
	rng.seed=81136
	split_architecture()
	split_nature()
	terrain()
	for kind in ["barrel","bench","firewood","noticeboard","pot","scarecrow","ruin_wall","crystal","rubble","tuft","fern","mushrooms","pebbles","shrub"]: prop(kind)
	split_props()
	print("ENVIRONMENT: 9 architecture sprites, 12 nature/market sprites, 16 painted props, native details and 192 terrain tiles.")
	quit()

func split_architecture()->void:
	var source:=Image.load_from_file("res://assets/painted/architecture_source.png")
	var names:=["home","tavern","smith","cottage","warehouse","windmill","chapel","gatehouse","merchant"]
	var heights:=[0.0,0.31,0.64,1.0]
	for i in range(9):
		var x:=int(i%3*source.get_width()/3.0)
		var y:=int(heights[i/3]*source.get_height())
		var right:=int((i%3+1)*source.get_width()/3.0)
		var bottom:=int(heights[i/3+1]*source.get_height())
		var crop:=source.get_region(Rect2i(x,y,right-x,bottom-y))
		crop=crop.get_region(crop.get_used_rect())
		var width:=224
		if names[i] in ["tavern","warehouse","merchant","gatehouse"]: width=256
		var scale:=minf(float(width)/crop.get_width(),244.0/crop.get_height())
		crop.resize(roundi(crop.get_width()*scale),roundi(crop.get_height()*scale),Image.INTERPOLATE_NEAREST)
		crop.save_png(OUT+names[i]+".png")

func split_nature()->void:
	var source:=Image.load_from_file("res://assets/painted/nature_source.png")
	var names:=["tree_0","tree_1","tree_2","tree_3","stall","well","cart","tent","rock","log","grave","boat"]
	var sizes:=[Vector2(132,152),Vector2(120,168),Vector2(120,160),Vector2(118,148),Vector2(136,120),Vector2(94,100),Vector2(142,130),Vector2(138,122),Vector2(84,76),Vector2(116,64),Vector2(102,92),Vector2(104,58)]
	for i in range(12):
		var roi:=Rect2i(int(i%4*source.get_width()/4.0),int(i/4*source.get_height()/3.0),int(source.get_width()/4.0),int(source.get_height()/3.0))
		var crop:=source.get_region(roi)
		crop=crop.get_region(crop.get_used_rect())
		var scale:=minf(sizes[i].x/crop.get_width(),sizes[i].y/crop.get_height())
		crop.resize(roundi(crop.get_width()*scale),roundi(crop.get_height()*scale),Image.INTERPOLATE_NEAREST)
		crop.save_png(OUT+names[i]+".png")

func split_props()->void:
	var source:=Image.load_from_file("res://assets/painted/props_source.png")
	var names:=["barrel","crate","firewood","bench","pot","fence","ruin_wall","pillar","sign","noticeboard","crystal","rubble","flowers","fern","reeds","fire"]
	var sizes:=[Vector2(32,42),Vector2(49,49),Vector2(48,38),Vector2(54,32),Vector2(43,44),Vector2(64,42),Vector2(78,64),Vector2(49,83),Vector2(40,69),Vector2(63,64),Vector2(39,40),Vector2(68,44),Vector2(38,32),Vector2(40,37),Vector2(37,44),Vector2(42,48)]
	for i in range(16):
		var roi:=Rect2i(int(i%4*source.get_width()/4.0),int(i/4*source.get_height()/4.0),int(source.get_width()/4.0),int(source.get_height()/4.0))
		var crop:=source.get_region(roi)
		crop=crop.get_region(crop.get_used_rect())
		var scale:=minf(sizes[i].x/crop.get_width(),sizes[i].y/crop.get_height())
		crop.resize(roundi(crop.get_width()*scale),roundi(crop.get_height()*scale),Image.INTERPOLATE_NEAREST)
		crop.save_png(OUT+names[i]+".png")

func canvas(w:int,h:int)->void:
	im=Image.create(w,h,false,Image.FORMAT_RGBA8)
	im.fill(Color.TRANSPARENT)

func rect(x:int,y:int,w:int,h:int,c:String)->void:
	var r:=Rect2i(x,y,w,h).intersection(Rect2i(Vector2i.ZERO,im.get_size()))
	if r.has_area(): im.fill_rect(r,Color(c))

func ellipse(cx:int,cy:int,rx:int,ry:int,c:String)->void:
	for y in range(-ry,ry+1):
		var half:=int(rx*sqrt(maxf(0,1-float(y*y)/float(ry*ry))))
		rect(cx-half,cy+y,half*2+1,1,c)

func line(a:Vector2i,b:Vector2i,c:String,t:int=1)->void:
	var count:=maxi(absi(b.x-a.x),absi(b.y-a.y))
	for i in range(count+1):
		var p:=Vector2(a).lerp(Vector2(b),float(i)/maxi(1,count))
		rect(roundi(p.x),roundi(p.y),t,t,c)

func terrain()->void:
	canvas(512,384)
	var palette:=[
		["68734a","707a50","616e46","7a8055"],["4b573d","526045","435139","5d6747"],
		["918064","9a886a","84755d","a29172"],["646657","777869","606554","858575"],
		["3c6466","467477","355a60","567e7a"],["67513b","846441","564733","ba9860"],
		["8d744c","a28656","62553b","b49965"],["505f49","5b6850","445843","6a7450"],
		["77764e","848155","696a47","96905e"],["a39571","b2a37e","918565","bcb18b"],
		["555e50","6d7666","515c4d","7d8474"],["6e7b4f","7a8757","617047","909568"]]
	for row in range(12):
		for col in range(16):
			var ox:=col*32
			var oy:=row*32
			var pal:Array=palette[row]
			rect(ox,oy,32,32,pal[0])
			for n in range(20):
				var x:=rng.randi_range(0,29)
				var y:=rng.randi_range(0,30)
				rect(ox+x,oy+y,rng.randi_range(1,3),1,pal[1+n%3])
			if row in [0,1,7,8,11]:
				for n in range(5):
					var x:=rng.randi_range(2,29)
					var y:=rng.randi_range(3,29)
					rect(ox+x,oy+y,1,2,pal[2])
					rect(ox+x-1,oy+y-1,1,2,pal[1])
			if row in [3,10]:
				var step:=8 if row==3 else 16
				for y in range(0,32,step):
					var x:=0
					while x<32:
						var width:=mini(rng.randi_range(step-2,step+5),32-x)
						var yy:=oy+y+rng.randi_range(0,1)
						var height:=step-rng.randi_range(1,3)
						rect(ox+x+1,yy+1,maxi(1,width-2),height,pal[1])
						rect(ox+x+2,yy,maxi(1,width-4),1,pal[3])
						for mark in range(3):
							rect(ox+x+rng.randi_range(1,maxi(1,width-2)),yy+rng.randi_range(1,height),1,1,pal[2 if mark==0 else 3])
						x+=width
			if row==4:
				for n in range(3): rect(ox+rng.randi_range(2,20),oy+rng.randi_range(2,29),rng.randi_range(4,9),1,pal[3])
			if row==5:
				for y in range(4,32,8):
					rect(ox,oy+y,32,2,pal[2])
					for x in range(4,32,7):
						rect(ox+x,oy+y-3,1,5,"ab9559")
						rect(ox+x-1,oy+y-4,3,2,"d2b575")
			if row==6:
				for x in range(0,32,8):
					rect(ox+x,oy,1,32,pal[2])
					rect(ox+x+2,oy,1,31,pal[3])
					rect(ox+x+4,oy+4,1,1,"4f4632")
	im.save_png(OUT+"terrain.png")

func prop(kind:String)->void:
	canvas(64,64)
	match kind:
		"barrel":
			ellipse(32,56,17,5,"28302166")
			ellipse(32,37,15,20,"4c3e2e")
			ellipse(31,36,12,19,"8d6d43")
			for x in range(23,44,4): rect(x,22,1,31,"b3955e")
			for y in [25,45]: rect(19,y,26,3,"555951")
			ellipse(32,19,12,4,"b49b69")
			ellipse(32,19,9,2,"6f5639")
		"bench":
			for x in [10,46]: rect(x,43,5,14,"514733")
			rect(7,34,49,9,"826744")
			rect(8,34,47,2,"bea06a")
			rect(8,40,48,1,"4b4230")
		"firewood":
			for y in range(3):
				for x in range(5):
					rect(7+x*9,50-y*7,10,7,"544330")
					ellipse(11+x*9,53-y*7,4,3,"b29768")
					ellipse(11+x*9,53-y*7,2,1,"715237")
		"noticeboard":
			for x in [12,48]: rect(x,16,5,45,"5d4a36")
			rect(5,10,55,31,"594937")
			rect(8,12,49,26,"90754b")
			for i in range(5):
				var x:=11+i*9
				var y:=16+i%2*5
				rect(x,y,8,13,"d8c6a1")
				for k in range(3): rect(x+1,y+3+k*3,5,1,"99825b")
			rect(2,7,60,4,"b49b68")
		"pot":
			ellipse(31,49,9,10,"805c43")
			rect(22,39,19,4,"be8d65")
			for i in range(7):
				line(Vector2i(31,42),Vector2i(24+i*3,31+i%3*3),"667749")
				rect(23+i*3,30+i%3*3,3,3,"bfa2b5")
		"scarecrow":
			rect(30,21,3,40,"8a7049")
			line(Vector2i(11,31),Vector2i(51,27),"a18a5a",3)
			rect(22,24,19,23,"7e6650")
			ellipse(31,18,7,8,"bba577")
			rect(19,12,25,4,"5f5039")
			rect(24,5,15,9,"7f6b44")
		"ruin_wall":
			for y in range(4):
				for x in range(4):
					var xx:=x*15+(7 if y%2 else 0)
					rect(xx,53-y*9,14,8,"687263")
					rect(xx+1,53-y*9,12,2,"929881")
			for i in range(12): rect(rng.randi_range(3,58),rng.randi_range(26,59),4,2,"4d6842")
		"crystal":
			for i in range(3):
				var x:=23+i*7
				for y in range(19+i*5,56):
					var w:=mini(5,(y-19-i*5)/2)
					rect(x-w,y,w*2,1,"77648b")
					rect(x-w,y,maxi(1,w),1,"b8a5cb")
		"rubble","pebbles":
			for i in range(9):
				var x:=rng.randi_range(10,53)
				var y:=rng.randi_range(37,57)
				ellipse(x,y,3+i%3,2+i%2,"626b58")
				rect(x-2,y-1,4,1,"989a80")
		"tuft","fern","shrub":
			for i in range(12 if kind!="shrub" else 32):
				var x:=rng.randi_range(14,49)
				var y:=rng.randi_range(33,53)
				line(Vector2i(32,58),Vector2i(x,y),"56643d",1)
				rect(x-2,y,4,2,"84905a" if i%2 else "6b7d4b")
		"mushrooms":
			for i in range(5):
				var x:=18+i*7
				var y:=46+i%3*4
				rect(x,y,2,7,"bfad82")
				ellipse(x,y,4,2,"a2764c")
				rect(x-2,y-1,2,1,"dbbe81")
	im.save_png(OUT+kind+".png")
