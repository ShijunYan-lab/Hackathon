extends SceneTree
func _initialize() -> void:
	var file:=FileAccess.open("res://../release/GODOT_LICENSE.txt",FileAccess.WRITE)
	file.store_string(Engine.get_license_text())
	file.store_string("\n\nThird-party components:\n"+JSON.stringify(Engine.get_copyright_info(),"  "))
	file.close()
	quit()
