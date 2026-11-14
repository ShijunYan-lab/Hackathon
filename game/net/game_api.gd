extends Node
## One serialized HTTP boundary; retries preserve the exact request body and ID.
signal state_received(state:Dictionary,operation:String)
signal completed(operation:String,data:Dictionary)
signal failed(operation:String,message:String)
var base_url:="http://127.0.0.1:8765"
var world_id:=""
var version:=-1
var connected:=false
var queue:Array[Dictionary]=[]
var active:Dictionary={}
var http:HTTPRequest
var model_http:HTTPRequest
var model_queue:Array[Dictionary]=[]
var model_active:Dictionary={}
var serial:=0
var session:=str(Time.get_unix_time_from_system()).replace(".","")+"-"+str(randi())
var suspended:=false

func _ready()->void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--server="): base_url=arg.trim_prefix("--server=")
	http=HTTPRequest.new()
	http.timeout=25
	add_child(http)
	http.request_completed.connect(_response)
	model_http=HTTPRequest.new()
	model_http.timeout=75
	add_child(model_http)
	model_http.request_completed.connect(_model_response)

func idle()->bool: return active.is_empty() and queue.is_empty() and model_active.is_empty() and model_queue.is_empty() and not suspended

func call_api(operation:String,path:String,body:Dictionary={},versioned:bool=false,switch_world:bool=false)->void:
	serial+=1
	var payload:=body.duplicate(true)
	var method:=HTTPClient.METHOD_GET if body.is_empty() else HTTPClient.METHOD_POST
	if method==HTTPClient.METHOD_POST: payload.request_id=session+"-"+str(serial)
	var job:Dictionary={"op":operation,"path":path,"body":payload,"method":method,"versioned":versioned,"switch":switch_world,"world":world_id,"attempt":0}
	if operation=="dialogue":
		model_queue.append(job)
	else:
		queue.append(job)
	_dispatch()

func command(kind:String,payload:Dictionary)->void:
	if kind=="HIT":
		var same_attack: Callable = func(job): return job.op=="HIT" and job.body.payload.attacker_id==payload.attacker_id and job.body.payload.attack_id!=payload.attack_id
		if (not active.is_empty() and same_attack.call(active)) or queue.any(same_attack): return
	call_api(kind,"/v1/worlds/{world}/commands",{"kind":kind,"payload":payload},true)

func _dispatch()->void:
	if not active.is_empty() or suspended: return
	if queue.is_empty():
		_dispatch_model()
		return
	active=queue.pop_front()
	if active.op=="TASK_REPORT":
		var tasks: Array = get_parent().state.get("tasks",[])
		var task_id: String = str(active.body.payload.task_id)
		if not tasks.any(func(t):return str(t.id)==task_id and t.status in ["pending","running"]):
			active={}
			_dispatch()
			return
	if active.op=="HIT":
		var entities: Dictionary = get_parent().actors
		var payload: Dictionary = active.body.payload
		var attacker=entities.get(str(payload.attacker_id))
		var target=entities.get(str(payload.target_id))
		if attacker==null or target==null or not attacker.alive or not target.alive:
			active={}
			_dispatch()
			return
	active.path=str(active.path).replace("{world}",world_id)
	active.world=world_id
	if active.versioned: active.body.expected_world_version=maxi(0,version)
	active.serialized=JSON.stringify(active.body) if active.method==HTTPClient.METHOD_POST else ""
	_send()

# Conversation requests run independently from hit/checkpoint/other gameplay.
# We wait until earlier checkpoint writes have been sent before capturing the
# expected world version. A combat hit may invalidate a pending model reply;
# C rejects that stale proposal instead of applying it to the wrong world.
func _dispatch_model()->void:
	if suspended or not model_active.is_empty() or model_queue.is_empty(): return
	if not active.is_empty() or not queue.is_empty(): return
	model_active=model_queue.pop_front()
	model_active.path=str(model_active.path).replace("{world}",world_id)
	model_active.world=world_id
	if model_active.versioned: model_active.body.expected_world_version=maxi(0,version)
	var content:String=JSON.stringify(model_active.body) if model_active.method==HTTPClient.METHOD_POST else ""
	var err:int=model_http.request(base_url+str(model_active.path),
		["Content-Type: application/json"],model_active.method,content)
	if err!=OK:
		model_active={}
		failed.emit("dialogue","无法建立 NPC 模型请求；普通移动与战斗仍可继续。")

func _model_response(result:int,code:int,_headers:PackedStringArray,bytes:PackedByteArray)->void:
	if model_active.is_empty(): return
	var job:Dictionary=model_active
	model_active={}
	var parser:=JSON.new()
	var parsed:Variant=null
	if not bytes.is_empty() and parser.parse(bytes.get_string_from_utf8())==OK: parsed=parser.data
	if result!=HTTPRequest.RESULT_SUCCESS or not parsed is Dictionary or code>=500:
		failed.emit(str(job.op),"NPC 对话服务超时或连接失败；战斗仍可进行。")
		_dispatch()
		return
	if not parsed.get("ok",false):
		var error:Dictionary=parsed.get("error",{}) if parsed.get("error") is Dictionary else {}
		failed.emit(str(job.op),str(error.get("message","NPC 对话未被接受"))+" ["+str(error.get("code",code))+"]")
		if code==409: call_api("refresh","/v1/worlds/{world}/state")
		_dispatch()
		return
	var data:Dictionary=parsed.get("data",{})
	if data.get("state") is Dictionary:
		var next_state:Dictionary=data.state
		if str(next_state.get("world_id",""))==world_id and int(next_state.get("world_version",-1))>=version:
			version=int(next_state.world_version)
			state_received.emit(next_state,str(job.op))
	completed.emit(str(job.op),data)
	_dispatch()

func _send()->void:
	active.attempt+=1
	http.timeout=2 if active.op=="health" else (75 if active.op in ["dialogue","advance"] else 25)
	var error:=http.request(base_url+str(active.path),["Content-Type: application/json"],active.method,active.serialized)
	if error!=OK: _response(HTTPRequest.RESULT_CANT_CONNECT,0,[],PackedByteArray())

func _response(result:int,code:int,_headers:PackedStringArray,bytes:PackedByteArray)->void:
	if active.is_empty(): return
	var parser:=JSON.new()
	var parsed:Variant=null
	if not bytes.is_empty() and parser.parse(bytes.get_string_from_utf8())==OK: parsed=parser.data
	if result!=HTTPRequest.RESULT_SUCCESS or code>=500 or not parsed is Dictionary:
		connected=false
		# The first local health probe is only a discovery check. Repeating it
		# several times before bootstrapping makes the title screen look frozen.
		if str(active.get("op", "")) == "health":
			active = {}
			suspended = false
			failed.emit("health", "本地世界服务尚未就绪，尝试启动后端。")
			_dispatch()
			return
		if int(active.attempt)<3:
			await get_tree().create_timer(float(active.attempt)).timeout
			_send()
			return
		# Keep the unresolved operation for F9: a lost response may already be committed.
		suspended=true
		failed.emit(str(active.op),"连接中断；操作尚未确认。F9 以相同请求编号重连。")
		return
	connected=true
	var job:=active
	active={}
	if not parsed.get("ok",false):
		var detail:Dictionary=parsed.get("error",{}) if parsed.get("error") is Dictionary else {}
		if job.op=="HIT" and detail.get("code","") in ["ATTACK_EXPIRED","ATTACK_COOLDOWN","NPC_DEAD"]:
			# Predicted collision became obsolete while in transit; no damage is applied.
			# This is a rejected prediction, not a successful hit or a retryable transaction.
			_dispatch()
			return
		failed.emit(str(job.op),str(detail.get("message","请求未被接受"))+" ["+str(detail.get("code",code))+"]")
		if code==409:
			# Drop actions based on stale state; do not silently replay attacks or trades.
			queue.clear()
			call_api("refresh","/v1/worlds/{world}/state")
		_dispatch()
		return
	var data:Dictionary=parsed.get("data",{})
	if data.get("evaluation_active",false) and str(job.op) in ["resume","refresh"]:
		# A legacy session may point at an evaluation. Recover before applying its actors.
		completed.emit(str(job.op),data)
		_dispatch()
		return
	if data.get("state") is Dictionary:
		var state:Dictionary=data.state
		var incoming:=str(state.world_id)
		if bool(job.switch) or world_id.is_empty():
			world_id=incoming
			version=-1
			queue.clear()
		if incoming==world_id and int(state.world_version)>=version:
			version=int(state.world_version)
			state_received.emit(state,str(job.op))
	completed.emit(str(job.op),data)
	_dispatch()

func retry()->void:
	if suspended:
		suspended=false
		active.attempt=0
		_send()
	elif idle(): call_api("health","/health")
