#version 330

in vec3 vertexPosition;
in vec2 vertexTexCoord;
in vec3 vertexNormal;
in vec4 vertexColor;

out vec2 fragTexCoord;
out vec4 fragColor;
out vec3 fragLight;

uniform mat4 mvp;
uniform mat4 matModel;

uniform vec3 lightDir;
uniform vec3 lightColor;
uniform vec3 ambientColor;

void main()
{
    vec3 worldNormal = normalize(mat3(matModel) * vertexNormal);
    float diffuse = max(dot(worldNormal, -normalize(lightDir)), 0.0);

    fragLight = ambientColor + (lightColor * diffuse);
    fragTexCoord = vertexTexCoord;
    fragColor = vertexColor;

    gl_Position = mvp * vec4(vertexPosition, 1.0);
}
