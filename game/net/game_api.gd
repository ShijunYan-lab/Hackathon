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

func idle()->bool: return active.is_empty() and queue.is_empty() and not suspended

func call_api(operation:String,path:String,body:Dictionary={},versioned:bool=false,switch_world:bool=false)->void:
	serial+=1
	var payload:=body.duplicate(true)
	var method:=HTTPClient.METHOD_GET if body.is_empty() else HTTPClient.METHOD_POST
	if method==HTTPClient.METHOD_POST: payload.request_id=session+"-"+str(serial)
	queue.append({"op":operation,"path":path,"body":payload,"method":method,"versioned":versioned,"switch":switch_world,"world":world_id,"attempt":0})
	_dispatch()

func command(kind:String,payload:Dictionary)->void:
	call_api(kind,"/v1/worlds/{world}/commands",{"kind":kind,"payload":payload},true)

func _dispatch()->void:
	if not active.is_empty() or queue.is_empty() or suspended: return
	active=queue.pop_front()
	active.path=str(active.path).replace("{world}",world_id)
	active.world=world_id
	if active.versioned: active.body.expected_world_version=maxi(0,version)
	active.serialized=JSON.stringify(active.body) if active.method==HTTPClient.METHOD_POST else ""
	_send()

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
