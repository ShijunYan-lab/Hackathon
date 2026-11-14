extends CharacterBody2D
var data:Dictionary
var sprite:Sprite2D
var home:=Vector2.ZERO
var elapsed:=0.0
var talking:=false
var preview_attack:=false
var facing_left:=false
var movement_enabled:=true

func _ready()->void:
	collision_layer=4
	collision_mask=1
	motion_mode=MOTION_MODE_FLOATING
	var collision:=CollisionShape2D.new()
	var shape:=CapsuleShape2D.new()
	shape.radius=7
	shape.height=18
	collision.shape=shape
	collision.rotation=PI/2
	collision.position=Vector2(0,-5)
	add_child(collision)
	sprite=Sprite2D.new()
	sprite.texture=load("res://assets/characters/"+data.appearance_key+".png")
	sprite.hframes=12
	sprite.position=Vector2(0,-30)
	add_child(sprite)
	home=position
	elapsed=float(abs(hash(data.id))%47)
	add_to_group("preview_npcs")
	queue_redraw()

func _draw()->void:
	draw_set_transform(Vector2(0,-1),0,Vector2(1,0.35))
	draw_circle(Vector2.ZERO,13,Color(0.08,0.09,0.07,0.4))
	draw_set_transform(Vector2.ZERO)

func _physics_process(delta:float)->void:
	elapsed+=delta
	velocity=Vector2.ZERO
	if preview_attack:
		sprite.frame=7+int(elapsed*7)%5
	elif not talking and movement_enabled and fmod(elapsed,18)>13:
		var target:=home+Vector2(26 if fmod(elapsed,36)>18 else -26,0)
		velocity=(target-position).normalized()*23 if position.distance_to(target)>3 else Vector2.ZERO
		if velocity!=Vector2.ZERO:
			facing_left=velocity.x<0
			sprite.frame=3+int(elapsed*6)%4
		else: sprite.frame=int(elapsed*3)%3
	else: sprite.frame=int(elapsed*2.5)%3
	sprite.flip_h=facing_left
	move_and_slide()

func set_controls_locked(value:bool)->void:
	talking=value
	velocity=Vector2.ZERO

func reply_to(message:String)->String:
	if message.contains("消息") or message.contains("传闻") or message.contains("遗迹") or message.contains("路") or message.contains("森林"):
		return data.rumor
	if message.contains("工作") or message.contains("手艺") or message.contains("做") or message.contains("卖") or message.contains("买"):
		return data.work
	if message.contains("哪里") or message.contains("地方") or message.contains("这里"):
		return "这里是"+str(data.place)+"。"+str(data.rumor)
	if message.contains("你好") or message.contains("您好") or message.contains("名字") or message.contains("谁"):
		return "我叫"+str(data.name)+"。"+str(data.greeting)
	return "关于“"+message.left(28)+"”，我知道的有限。"+str(data.rumor)
