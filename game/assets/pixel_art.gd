extends SceneTree
## Reproducible source art, drawn on integer pixels by Godot itself.
## Run: godot --headless --path game --script res://assets/pixel_art.gd

var im: Image
var rng := RandomNumberGenerator.new()
const OUT := "res://assets/pixel/"

func _initialize() -> void:
	rng.seed = 67321
	DirAccess.make_dir_recursive_absolute(OUT)
	terrain()
	for variant in range(4): tree(variant)
	for kind in ["home", "tavern", "smith", "cottage", "warehouse"]: house(kind)
	for kind in ["stall", "well", "boat", "ruin", "pillar", "rock", "lamp", "crate", "fence", "flowers", "reeds", "sign", "fire"]: prop(kind)
	character(false)
	character(true)
	print("PIXEL ART: terrain, architecture, vegetation, props and 32x48 characters written.")
	quit()

func canvas(w: int, h: int) -> void:
	im = Image.create(w, h, false, Image.FORMAT_RGBA8)
	im.fill(Color.TRANSPARENT)

func rect(x: int, y: int, w: int, h: int, color: String) -> void:
	var clipped := Rect2i(x, y, w, h).intersection(Rect2i(0, 0, im.get_width(), im.get_height()))
	if clipped.has_area(): im.fill_rect(clipped, Color(color))

func dot(x: int, y: int, c: String) -> void: rect(x, y, 1, 1, c)

func ellipse(cx: int, cy: int, rx: int, ry: int, c: String) -> void:
	for y in range(-ry, ry + 1):
		var span := int(rx * sqrt(maxf(0.0, 1.0 - float(y * y) / float(ry * ry))))
		rect(cx - span, cy + y, span * 2 + 1, 1, c)

func line(a: Vector2i, b: Vector2i, c: String, thickness: int = 1) -> void:
	var steps := maxi(absi(b.x - a.x), absi(b.y - a.y))
	for i in range(steps + 1):
		var p := Vector2(a).lerp(Vector2(b), float(i) / maxi(1, steps))
		rect(roundi(p.x), roundi(p.y), thickness, thickness, c)

func save_art(file: String) -> void: im.save_png(OUT + file + ".png")

func terrain() -> void:
	canvas(512, 256)
	var palettes := [
		["64764b", "6b7d51", "5d7046", "748457"],
		["3d5545", "425b49", "394f41", "4b604a"],
		["a19069", "a69570", "978461", "b09c75"],
		["858675", "8e8d7b", "797d6e", "a0a08a"],
		["386c73", "40767b", "32636d", "4f8385"],
		["655441", "786048", "594b3c", "92724f"],
		["8b704b", "9a7d53", "765e41", "b29160"],
		["253e37", "2d463d", "233a32", "354d3e"]]
	for row in range(8):
		for col in range(4):
			var ox := col * 32
			var oy := row * 32
			var pal: Array = palettes[row]
			rect(ox, oy, 32, 32, pal[0])
			for n in range(55):
				var x := ox + rng.randi_range(0, 30)
				var y := oy + rng.randi_range(0, 30)
				rect(x, y, rng.randi_range(1, 3), 1, pal[rng.randi_range(1, 3)])
			if row == 3:
				for y in range(0, 32, 8):
					for x in range(-8, 32, 16):
						var xx := ox + x + (8 if y % 16 == 0 else 0)
						if xx >= ox: rect(xx, oy + y, mini(14, ox + 32 - xx), 1, "626e62")
						if xx >= ox: rect(xx, oy + y, 1, 7, "626e62")
			if row == 4:
				for n in range(5): rect(ox + rng.randi_range(2, 19), oy + rng.randi_range(2, 29), rng.randi_range(4, 10), 1, "649b98")
			if row == 5:
				for y in range(4, 32, 8):
					rect(ox, oy + y, 32, 2, "443e32")
					for x in range(4, 32, 8):
						rect(ox + x, oy + y - 3, 2, 5, "8b9a51")
						rect(ox + x - 2, oy + y - 2, 6, 1, "b7b368")
			if row == 6:
				for x in range(0, 32, 8):
					rect(ox + x, oy, 1, 32, "514b3c")
					rect(ox + x + 2, oy + 1, 1, 30, "b59a66")
					dot(ox + x + 3, oy + 3, "423e35")
	save_art("terrain")
	# Transparent edge tiles: dirt, shore and forest, each with 16 neighbour masks.
	canvas(512, 96)
	for style in range(3):
		for mask in range(16):
			for side in range(4):
				if not (mask & (1 << side)): continue
				for i in range(32):
					var depth := 2 + (i * 7 + i / 5) % 3
					for d in range(depth):
						var p := Vector2i(i, d)
						if side == 1: p = Vector2i(31 - d, i)
						if side == 2: p = Vector2i(i, 31 - d)
						if side == 3: p = Vector2i(d, i)
						var colors := [["64764b", "7b8656"], ["9a9b73", "b8b58b"], ["425b49", "52664b"]]
						dot(mask * 32 + p.x, style * 32 + p.y, colors[style][1 if d == depth - 1 else 0])
	save_art("edges")

func tree(variant: int) -> void:
	canvas(80, 112)
	ellipse(42, 101, 29, 7, "263e3570")
	rect(35, 66, 12, 34, "352e2d")
	rect(38, 65, 6, 35, "665343")
	rect(39, 70, 2, 24, "8b7151")
	line(Vector2i(40, 83), Vector2i(23, 64), "554536", 4)
	line(Vector2i(42, 85), Vector2i(57, 68), "554536", 3)
	line(Vector2i(38, 97), Vector2i(29, 103), "514b37", 3)
	line(Vector2i(44, 96), Vector2i(52, 102), "514b37", 3)
	var pal: Array = ["243e36", "2f5040", "3e6448", "57774d", "738b57"]
	if variant == 1: pal = ["273e3e", "34534b", "436756", "5a7b5f", "799572"]
	if variant == 2: pal = ["343e35", "4c5540", "66704a", "839052", "a2a368"]
	if variant == 3: pal = ["213c35", "2b4d3e", "365d45", "4d714e", "67895e"]
	var lobes := [Vector3i(24, 56, 21), Vector3i(55, 55, 21), Vector3i(39, 34, 28), Vector3i(40, 17, 15), Vector3i(21, 37, 14), Vector3i(60, 38, 12)]
	for l in lobes: ellipse(l.x, l.y, l.z, int(l.z * 0.82), pal[0])
	for l in lobes:
		ellipse(l.x - 1, l.y - 3, l.z - 2, int(l.z * 0.70), pal[1])
		ellipse(l.x - 4, l.y - 8, l.z - 6, int(l.z * 0.48), pal[2])
	for n in range(190):
		var x := rng.randi_range(7, 70)
		var y := rng.randi_range(7, 71)
		if im.get_pixel(x, y).a > 0.9 and im.get_pixel(x, y) != Color(pal[0]):
			rect(x, y, rng.randi_range(2, 5), 2, pal[rng.randi_range(2, 4)] if y % 7 < 3 else pal[1])
	save_art("tree_" + str(variant))

func house(kind: String) -> void:
	canvas(176, 160)
	var roof := "88594b"
	var roof_light := "ae7860"
	if kind == "home":
		roof = "555b70"
		roof_light = "7b8191"
	if kind == "tavern":
		roof = "71516a"
		roof_light = "986d82"
	if kind == "smith":
		roof = "4e6265"
		roof_light = "758484"
	ellipse(90, 147, 78, 9, "2b3b3260")
	rect(19, 70, 138, 77, "363d36")
	rect(24, 72, 128, 66, "b9ab85")
	rect(26, 75, 124, 10, "96896e")
	rect(23, 135, 132, 9, "797e6c")
	for y in range(137, 145, 4):
		for x in range(25, 153, 11): rect(x + (5 if y % 8 else 0), y, 1, 3, "505c52")
	for x in [27, 59, 111, 147]:
		rect(x, 80, 5, 55, "554738")
		rect(x + 1, 82, 1, 50, "897454")
	rect(25, 105, 126, 4, "62503d")
	line(Vector2i(32, 110), Vector2i(52, 132), "6b5741", 3)
	line(Vector2i(139, 110), Vector2i(118, 132), "6b5741", 3)
	for x in [38, 121]:
		rect(x - 3, 89, 21, 29, "6c5842")
		rect(x, 90, 15, 23, "353e3e")
		rect(x + 2, 92, 11, 18, "d3af72")
		rect(x + 3, 93, 4, 7, "efd39b")
		rect(x + 7, 91, 2, 22, "6f5a42")
		rect(x, 101, 15, 2, "6f5a42")
		rect(x - 4, 115, 23, 3, "493f32")
		rect(x - 2, 118, 20, 5, "648052")
		for f in range(5): rect(x + f * 4, 117 - f % 2, 2, 2, "cfac86")
	rect(73, 106, 27, 34, "4d4336")
	rect(76, 108, 21, 30, "806443")
	for x in range(78, 98, 5): rect(x, 109, 1, 28, "574936")
	rect(77, 111, 19, 2, "ad8c58")
	rect(77, 130, 19, 2, "504c3c")
	rect(92, 123, 2, 2, "e4c684")
	rect(69, 140, 35, 4, "b1ad8e")
	rect(65, 144, 43, 4, "898c76")
	# Stepped, shingled roof, asymmetric weathering and ridge.
	for y in range(25, 80):
		var inset := int((79 - y) * 0.42)
		rect(7 + inset, y, 162 - inset * 2, 1, "343c39")
		rect(10 + inset, y, 156 - inset * 2, 1, roof)
		if y % 7 == 0: rect(10 + inset, y, 156 - inset * 2, 1, roof_light)
		for x in range(12 + inset, 163 - inset, 13):
			if y % 7 > 0: dot(x + (6 if y % 14 < 7 else 0), y, "453f42")
	rect(30, 23, 116, 4, "454147")
	rect(30, 23, 116, 1, roof_light)
	rect(7, 80, 162, 4, "473d35")
	rect(10, 80, 156, 1, "c2a07b")
	# Dormer.
	for y in range(44, 66):
		var w := mini(18, y - 43)
		rect(87 - w, y, w * 2, 1, "373e3b")
		rect(89 - w, y + 2, maxi(1, w * 2 - 4), 1, "c6b48b")
	rect(78, 57, 18, 16, "5c4d3c")
	rect(81, 58, 12, 12, "d4bd81")
	rect(86, 58, 2, 13, "64553f")
	rect(80, 63, 14, 2, "64553f")
	rect(126, 12, 15, 27, "646c63")
	for y in range(14, 36, 5): rect(127, y, 13, 1, "9c9d86")
	rect(123, 10, 21, 5, "424e48")
	rect(125, 10, 17, 1, "aaa48d")
	if kind == "tavern":
		rect(146, 91, 23, 3, "4b4037")
		rect(162, 94, 2, 7, "8c8061")
		rect(152, 100, 21, 18, "4e4238")
		rect(154, 102, 17, 14, "ac8c58")
		rect(159, 104, 5, 8, "ece0b0")
		rect(164, 105, 3, 5, "ece0b0")
	if kind == "smith":
		rect(114, 108, 35, 28, "454b47")
		rect(119, 113, 25, 21, "2d3031")
		ellipse(131, 128, 10, 5, "b45e3c")
		ellipse(131, 128, 7, 3, "f5bd62")
		rect(123, 137, 28, 3, "9a9a80")
	save_art(kind)

func prop(kind: String) -> void:
	canvas(64, 64)
	match kind:
		"stall":
			canvas(96, 80)
			rect(11, 31, 4, 44, "584a37")
			rect(81, 31, 4, 44, "584a37")
			rect(9, 57, 78, 18, "76573b")
			rect(9, 56, 78, 4, "b39661")
			for x in range(12, 85, 9): rect(x, 63, 1, 10, "473e31")
			for y in range(12, 43):
				var inset := int((42 - y) * 0.2)
				for x in range(5 + inset, 91 - inset):
					dot(x, y, ("bd8668" if y < 35 else "995e51") if x / 10 % 2 == 0 else ("ded0a2" if y < 35 else "c0b38a"))
			rect(5, 43, 86, 2, "54473a")
			for n in range(16):
				var x := 15 + n % 8 * 9
				var y := 51 + n / 8 * 4
				ellipse(x, y, 3, 3, ["849451", "b56e50", "d2aa60"][n % 3])
		"well":
			ellipse(32, 55, 25, 6, "2b3c3270")
			ellipse(32, 44, 22, 13, "555f56")
			rect(10, 32, 44, 14, "808b7c")
			ellipse(32, 32, 22, 10, "b0b29a")
			ellipse(32, 32, 15, 6, "2a4348")
			for x in [12, 49]: rect(x, 11, 4, 30, "65523b")
			rect(10, 11, 45, 5, "a68b57")
			rect(31, 13, 1, 24, "c9bb8b")
			for y in range(4, 14): rect(6 + (13-y), y, 52 - (13-y)*2, 1, "68576b")
		"boat":
			canvas(64, 112)
			ellipse(32, 62, 27, 44, "224c5780")
			for y in range(17, 103):
				var w := int(22 * sin(PI * (y - 17) / 86.0))
				rect(32 - w, y, w * 2 + 1, 1, "413f34")
				if w > 3: rect(35 - w, y, w * 2 - 5, 1, "a08250" if y % 8 < 2 else "796041")
			for y in [39, 70, 86]: rect(14, y, 35, 5, "b59861")
			line(Vector2i(7, 84), Vector2i(53, 27), "493f34", 3)
			line(Vector2i(8, 83), Vector2i(54, 26), "b8a177", 1)
		"ruin":
			canvas(192, 160)
			for y in range(105, 155, 12):
				for x in range(15, 177, 19): rect(x, y, 17, 10, "69796c" if (x+y)%3 else "819182")
			for x in [32, 130]:
				rect(x - 5, 58, 36, 78, "3d514b")
				rect(x, 57, 25, 74, "869184")
				rect(x + 3, 61, 4, 66, "a8ad97")
				for y in range(62, 132, 13): rect(x, y, 25, 2, "536b60")
				rect(x - 6, 125, 38, 11, "9a9f88")
			for y in range(22, 72):
				var outer := int(sqrt(maxf(0, 64*64 - (y-80)*(y-80))))
				var inner := int(sqrt(maxf(0, 43*43 - (y-80)*(y-80))))
				for x in range(96 - outer, 97 + outer):
					if absi(x-96) >= inner: dot(x, y, "8d9989" if (x+y) % 17 > 2 else "5c7166")
			line(Vector2i(93, 23), Vector2i(87, 42), "374c47", 2)
			for n in range(80): rect(rng.randi_range(22, 163), rng.randi_range(116, 149), 4, 2, "4c7053")
			rect(84, 109, 24, 23, "445a56")
			line(Vector2i(96, 112), Vector2i(103, 120), "9ccfbd", 2)
			line(Vector2i(103, 120), Vector2i(96, 128), "9ccfbd", 2)
			line(Vector2i(96, 128), Vector2i(89, 120), "9ccfbd", 2)
			line(Vector2i(89, 120), Vector2i(96, 112), "9ccfbd", 2)
		"pillar":
			rect(19, 18, 25, 38, "697e73")
			rect(22, 16, 6, 39, "a3aa91")
			for y in range(24, 56, 9): rect(19, y, 25, 1, "40594f")
			rect(14, 54, 36, 8, "8d9a84")
			rect(17, 14, 18, 6, "9da68d")
		"rock":
			ellipse(32, 50, 23, 8, "2a3f3460")
			ellipse(31, 40, 23, 14, "536657")
			ellipse(28, 36, 20, 13, "7c8971")
			ellipse(23, 31, 12, 6, "9c9f84")
			rect(22, 45, 21, 2, "697655")
		"lamp":
			rect(30, 21, 3, 39, "4c4435")
			rect(28, 58, 7, 3, "a29a70")
			rect(22, 13, 20, 3, "574d3d")
			rect(24, 16, 15, 16, "443f34")
			rect(26, 18, 11, 11, "e3bb70")
			rect(29, 19, 5, 8, "ffe3a1")
			rect(30, 12, 3, 20, "6e6144")
		"crate":
			rect(18, 30, 29, 26, "4f4736")
			rect(20, 31, 25, 22, "9a7c50")
			for x in range(22, 45, 6): rect(x, 33, 1, 19, "67543b")
			line(Vector2i(21, 33), Vector2i(42, 51), "c0a06a", 3)
			rect(20, 33, 25, 2, "bda06a")
		"fence":
			for y in [30, 42]: rect(0, y, 64, 5, "9b8659")
			for x in [4, 52]:
				rect(x, 24, 6, 33, "574e38")
				rect(x, 24, 4, 30, "baa16d")
		"flowers":
			for n in range(14):
				var x := rng.randi_range(13, 50)
				var y := rng.randi_range(32, 55)
				rect(x, y, 1, 5, "405e3d")
				rect(x - 1, y - 1, 3, 2, ["d8c595", "b7a1bf", "dbb476"][n%3])
		"reeds":
			for n in range(11):
				var x := rng.randi_range(17, 47)
				var y := rng.randi_range(20, 40)
				line(Vector2i(32, 58), Vector2i(x,y), "8a9b69")
				rect(x - 1, y - 4, 3, 7, "9d8b5d")
		"sign":
			rect(30, 31, 4, 29, "65513a")
			rect(13, 24, 39, 13, "b09863")
			rect(16, 27, 31, 2, "79613d")
			rect(18, 32, 20, 1, "79613d")
		"fire":
			ellipse(32, 52, 18, 6, "626b59")
			line(Vector2i(21, 53), Vector2i(42, 46), "6f5139", 4)
			ellipse(32, 42, 9, 12, "c17643")
			ellipse(31, 43, 5, 9, "e9ad54")
			ellipse(30, 46, 3, 6, "f7db88")
	save_art(kind)

func character(female: bool) -> void:
	canvas(32 * 8, 48 * 4)
	for direction in range(4):
		for frame in range(8):
			var ox := frame * 32
			var oy := direction * 48
			var bob := 1 if frame in [2, 3, 6, 7] else 0
			var step := (1 if frame < 4 else -1) if frame > 0 else 0
			var hair := "a69ac4" if female else "3b304f"
			var light := "d3c6e0" if female else "65517e"
			var mid := "81729f" if female else "4e3d68"
			var outline := "292638"
			# Boots and alternating legs stay anchored to the 32x48 cell.
			rect(ox+9, oy+36, 6, 9+step, outline)
			rect(ox+18, oy+36, 6, 9-step, outline)
			rect(ox+10, oy+39+step, 4, 4, "69536b")
			rect(ox+19, oy+39-step, 4, 4, "69536b")
			rect(ox+9, oy+44+step, 6, 1, "a38b80")
			rect(ox+18, oy+44-step, 6, 1, "a38b80")
			# Cape, cream piping, tunic and belt.
			for y in range(23, 40):
				var half := 8 + int((y-23)/5)
				rect(ox+16-half, oy+y+bob, half*2, 1, outline)
				rect(ox+18-half, oy+y+bob, half*2-4, 1, "57476f")
				rect(ox+17-half, oy+y+bob, 1, 1, "b6a2b7")
				rect(ox+14+half, oy+y+bob, 1, 1, "8e7c9f")
			rect(ox+10, oy+38+bob, 13, 2, "c5b5bb")
			if direction != 3:
				rect(ox+12, oy+24+bob, 9, 13, "bdb0b9")
				rect(ox+14, oy+25+bob, 5, 14, "3a354b")
				rect(ox+10, oy+33+bob, 13, 2, "c4a57c")
				rect(ox+15, oy+32+bob, 3, 4, "e3cb98")
				line(Vector2i(ox+12,oy+24+bob),Vector2i(ox+21,oy+29+bob),"ddc9b0",2)
			else:
				rect(ox+16, oy+29+bob, 2, 8, "d4c1b1")
				rect(ox+13, oy+32+bob, 8, 2, "d4c1b1")
			for side in [-1, 1]:
				var arm_x: int = ox+16+side*10
				var arm_y: int = oy+27+bob+side*step
				rect(arm_x-2, arm_y, 5, 9, outline)
				rect(arm_x-1, arm_y+1, 3, 5, "796486")
				rect(arm_x-1, arm_y+6, 3, 3, "e4c4b2")
			# Chibi head: hand-placed pixels, dark silhouette, distinct profile/back.
			for y in range(5, 24):
				var half := 12 if y in range(10,20) else (10 if y in range(7,22) else 7)
				rect(ox+16-half, oy+y+bob, half*2, 1, outline)
				rect(ox+17-half, oy+y+bob, half*2-2, 1, hair)
			rect(ox+13, oy+2+bob, 5, 4, outline)
			rect(ox+12, oy+4+bob, 9, 3, hair)
			rect(ox+10, oy+8+bob, 7, 2, mid)
			rect(ox+18, oy+6+bob, 3, 2, light)
			rect(ox+6, oy+12+bob, 3, 6, mid)
			rect(ox+20, oy+10+bob, 5, 3, mid)
			if direction != 3:
				var face_x := ox+10 + (-3 if direction == 1 else (3 if direction == 2 else 0))
				rect(face_x, oy+17+bob, 13, 7, "edcbbb")
				rect(face_x+1, oy+23+bob, 11, 2, "c89e98")
				rect(face_x+3, oy+21+bob, 8, 3, "f5dcc5")
				for eye in ([2,9] if direction == 0 else ([2] if direction == 1 else [9])):
					rect(face_x+eye, oy+18+bob, 3, 4, "3b304f")
					dot(face_x+eye, oy+18+bob, "eee8eb")
				for x in [8,12,17,22]:
					rect(ox+x, oy+12+bob, 3, 7 if x in [8,17] else 5, hair)
					rect(ox+x, oy+12+bob, 1, 3, mid)
			else:
				for x in [8,13,19,24]: rect(ox+x, oy+13+bob, 2, 8, mid)
			if female:
				for x in ([5,24] if direction != 3 else [6,11,17,23]):
					rect(ox+x, oy+17+bob, 4, 15, mid)
					rect(ox+x, oy+17+bob, 2, 13, hair)
					rect(ox+x, oy+20+bob, 1, 6, light)
				rect(ox+23, oy+11+bob, 6, 3, "ded0e2")
				rect(ox+25, oy+9+bob, 2, 7, "f0dcce")
				dot(ox+25, oy+12+bob, "d6b174")
			# Collar and the reference's small gold/lilac brooch.
			rect(ox+10, oy+24+bob, 13, 3, "413951")
			rect(ox+15, oy+25+bob, 3, 3, "ccb18a")
			dot(ox+16, oy+26+bob, "b294cf")
	save_art("traveler_female" if female else "traveler_male")
