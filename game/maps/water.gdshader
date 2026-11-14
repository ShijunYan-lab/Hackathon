shader_type canvas_item;
render_mode unshaded;

void fragment() {
	vec4 texel = texture(TEXTURE, UV);
	// The blue-green water palette is distinct from earth, grass and timber.
	float water = step(texel.r * 1.4, texel.b) * step(texel.g * 0.92, texel.b);
	float ripple = sin(UV.y * 1400.0 + TIME * 1.8 + sin(UV.x * 330.0));
	texel.rgb += water * step(0.94, ripple) * 0.035;
	COLOR = texel;
}
