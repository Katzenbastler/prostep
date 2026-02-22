#version 330

in vec2 fragTexCoord;
in vec4 fragColor;
in vec3 fragLight;

out vec4 finalColor;

uniform sampler2D texture0;
uniform vec4 colDiffuse;

void main()
{
    vec4 albedo = texture(texture0, fragTexCoord) * colDiffuse * fragColor;
    finalColor = vec4(albedo.rgb * fragLight, albedo.a);
}
