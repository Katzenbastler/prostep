#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "raylib.h"
#include "raymath.h"

struct AABB {
    Vector3 min;
    Vector3 max;
};

static bool Intersects(const AABB& a, const AABB& b) {
    return (a.min.x <= b.max.x && a.max.x >= b.min.x) &&
           (a.min.y <= b.max.y && a.max.y >= b.min.y) &&
           (a.min.z <= b.max.z && a.max.z >= b.min.z);
}

struct Player {
    Vector3 bottomPos { 0.0f, 0.0f, 0.0f };
    Vector3 velocity { 0.0f, 0.0f, 0.0f };
    float yaw = 0.0f;
    float pitch = 0.0f;
    bool grounded = false;

    static constexpr Vector3 halfExtents { 0.35f, 0.90f, 0.35f };

    AABB Bounds() const {
        const Vector3 center {
            bottomPos.x,
            bottomPos.y + halfExtents.y,
            bottomPos.z
        };

        return {
            { center.x - halfExtents.x, center.y - halfExtents.y, center.z - halfExtents.z },
            { center.x + halfExtents.x, center.y + halfExtents.y, center.z + halfExtents.z }
        };
    }

    Vector3 EyePos() const {
        return { bottomPos.x, bottomPos.y + 1.65f, bottomPos.z };
    }
};

struct Monster {
    Vector3 bottomPos { 6.0f, 0.0f, 6.0f };
    float radius = 0.38f;
    float height = 3.6f;
    float speed = 2.2f;
};

static bool MonsterOverlapsJumpBox(const Vector3& pos, float radius, const AABB& jumpBox) {
    const float expandedMinX = jumpBox.min.x - radius;
    const float expandedMaxX = jumpBox.max.x + radius;
    const float expandedMinZ = jumpBox.min.z - radius;
    const float expandedMaxZ = jumpBox.max.z + radius;

    return (pos.x >= expandedMinX && pos.x <= expandedMaxX &&
            pos.z >= expandedMinZ && pos.z <= expandedMaxZ);
}

static void MoveMonsterAxis(Monster& monster, int axis, float delta, float roomHalf, float wallThickness, const AABB& jumpBox) {
    if (delta == 0.0f) return;

    Vector3 next = monster.bottomPos;
    if (axis == 0) next.x += delta;
    else next.z += delta;

    const float limit = roomHalf - wallThickness - monster.radius;
    next.x = std::clamp(next.x, -limit, limit);
    next.z = std::clamp(next.z, -limit, limit);

    if (!MonsterOverlapsJumpBox(next, monster.radius, jumpBox)) {
        monster.bottomPos = next;
    }
}

static float AxisOverlap(float aMin, float aMax, float bMin, float bMax) {
    return std::min(aMax, bMax) - std::max(aMin, bMin);
}

static bool CanCollideOnAxis(const AABB& playerBox, const AABB& collider, int axis) {
    constexpr float eps = 0.0001f;

    if (axis == 0) {
        return AxisOverlap(playerBox.min.y, playerBox.max.y, collider.min.y, collider.max.y) > eps &&
               AxisOverlap(playerBox.min.z, playerBox.max.z, collider.min.z, collider.max.z) > eps;
    }
    if (axis == 1) {
        return AxisOverlap(playerBox.min.x, playerBox.max.x, collider.min.x, collider.max.x) > eps &&
               AxisOverlap(playerBox.min.z, playerBox.max.z, collider.min.z, collider.max.z) > eps;
    }

    return AxisOverlap(playerBox.min.x, playerBox.max.x, collider.min.x, collider.max.x) > eps &&
           AxisOverlap(playerBox.min.y, playerBox.max.y, collider.min.y, collider.max.y) > eps;
}

static void ResolveAxis(Player& player, const std::vector<AABB>& world, int axis, float delta) {
    if (delta == 0.0f) return;

    if (axis == 0) player.bottomPos.x += delta;
    if (axis == 1) player.bottomPos.y += delta;
    if (axis == 2) player.bottomPos.z += delta;

    AABB moved = player.Bounds();

    for (const AABB& collider : world) {
        if (!Intersects(moved, collider)) continue;
        if (!CanCollideOnAxis(moved, collider, axis)) continue;

        if (axis == 0) {
            if (delta > 0.0f) player.bottomPos.x -= (moved.max.x - collider.min.x);
            else player.bottomPos.x += (collider.max.x - moved.min.x);
            player.velocity.x = 0.0f;
        }

        if (axis == 1) {
            if (delta > 0.0f) player.bottomPos.y -= (moved.max.y - collider.min.y);
            else {
                player.bottomPos.y += (collider.max.y - moved.min.y);
                player.grounded = true;
            }
            player.velocity.y = 0.0f;
        }

        if (axis == 2) {
            if (delta > 0.0f) player.bottomPos.z -= (moved.max.z - collider.min.z);
            else player.bottomPos.z += (collider.max.z - moved.min.z);
            player.velocity.z = 0.0f;
        }

        moved = player.Bounds();
    }
}

static void DrawRoomChessboard(float roomHalfSize, float floorY) {
    constexpr float tileSize = 1.0f;
    const int tiles = static_cast<int>((roomHalfSize * 2.0f) / tileSize);
    const float start = -roomHalfSize;

    for (int z = 0; z < tiles; ++z) {
        for (int x = 0; x < tiles; ++x) {
            const bool odd = ((x + z) & 1) != 0;
            const Color color = odd ? Color{ 35, 35, 35, 255 } : Color{ 230, 230, 230, 255 };

            const Vector3 center {
                start + (static_cast<float>(x) + 0.5f) * tileSize,
                floorY - 0.01f,
                start + (static_cast<float>(z) + 0.5f) * tileSize
            };
            DrawCube(center, tileSize, 0.02f, tileSize, color);
        }
    }
}

static void DrawPlayerBody(const Player& player, float animTime, float moveSpeedFactor) {
    const float bodyHeight = player.halfExtents.y * 2.0f;
    const float bodyRadius = 0.32f;

    const Vector3 bodyCenter {
        player.bottomPos.x,
        player.bottomPos.y + bodyHeight * 0.5f,
        player.bottomPos.z
    };
    DrawCylinder(bodyCenter, bodyRadius, bodyRadius, bodyHeight, 18, RED);

    const float yawRad = player.yaw * DEG2RAD;
    const Vector3 forward { std::sin(yawRad), 0.0f, -std::cos(yawRad) };
    const Vector3 right { std::cos(yawRad), 0.0f, std::sin(yawRad) };

    const float shoulderY = player.bottomPos.y + bodyHeight * 0.70f;
    const float armLength = 0.75f;
    const float swing = std::sin(animTime * 10.0f) * 0.25f * moveSpeedFactor;

    const Vector3 leftStart = Vector3Add(
        Vector3{ player.bottomPos.x, shoulderY, player.bottomPos.z },
        Vector3Scale(right, -(bodyRadius + 0.04f))
    );
    const Vector3 leftEnd = Vector3Add(
        Vector3Add(leftStart, Vector3{ 0.0f, -armLength, 0.0f }),
        Vector3Scale(forward, swing)
    );

    const Vector3 rightStart = Vector3Add(
        Vector3{ player.bottomPos.x, shoulderY, player.bottomPos.z },
        Vector3Scale(right, bodyRadius + 0.04f)
    );
    const Vector3 rightEnd = Vector3Add(
        Vector3Add(rightStart, Vector3{ 0.0f, -armLength, 0.0f }),
        Vector3Scale(forward, -swing)
    );

    DrawCylinderEx(leftStart, leftEnd, 0.085f, 0.065f, 12, MAROON);
    DrawCylinderEx(rightStart, rightEnd, 0.085f, 0.065f, 12, MAROON);
}

static void DrawMonster(const Monster& monster) {
    const Color bodyColor { 35, 35, 35, 255 };
    const Vector3 start { monster.bottomPos.x, monster.bottomPos.y, monster.bottomPos.z };
    const Vector3 end { monster.bottomPos.x, monster.bottomPos.y + monster.height, monster.bottomPos.z };
    DrawCylinderEx(start, end, monster.radius, monster.radius, 18, bodyColor);
}

int main() {
    SetConfigFlags(FLAG_MSAA_4X_HINT | FLAG_WINDOW_RESIZABLE | FLAG_VSYNC_HINT);
    InitWindow(1600, 900, "Idle Hours - Custom Engine Starter");
    SetTargetFPS(0);
    DisableCursor();
    ChangeDirectory(GetApplicationDirectory());

    InitAudioDevice();
    Sound step1 = LoadSound("assets/audio/step1.wav");
    Sound step2 = LoadSound("assets/audio/step2.wav");
    bool soundsReady = IsSoundValid(step1) && IsSoundValid(step2);
    if (!soundsReady) {
        const std::string fallback1 = std::string("../assets/audio/step1.wav");
        const std::string fallback2 = std::string("../assets/audio/step2.wav");
        if (IsSoundValid(step1)) UnloadSound(step1);
        if (IsSoundValid(step2)) UnloadSound(step2);
        step1 = LoadSound(fallback1.c_str());
        step2 = LoadSound(fallback2.c_str());
        soundsReady = IsSoundValid(step1) && IsSoundValid(step2);
    }
    if (soundsReady) {
        SetSoundVolume(step1, 0.75f);
        SetSoundVolume(step2, 0.75f);
    } else {
        TraceLog(LOG_WARNING, "Footstep sounds not loaded.");
    }

    Shader lighting = LoadShader("assets/shaders/glsl330/lighting.vs", "assets/shaders/glsl330/lighting.fs");
    int lightDirLoc = GetShaderLocation(lighting, "lightDir");
    int lightColorLoc = GetShaderLocation(lighting, "lightColor");
    int ambientLoc = GetShaderLocation(lighting, "ambientColor");

    const float lightDir[3] = { -0.35f, -1.0f, -0.25f };
    const float lightColor[3] = { 1.0f, 1.0f, 1.0f };
    const float ambientColor[3] = { 0.30f, 0.30f, 0.34f };

    SetShaderValue(lighting, lightDirLoc, lightDir, SHADER_UNIFORM_VEC3);
    SetShaderValue(lighting, lightColorLoc, lightColor, SHADER_UNIFORM_VEC3);
    SetShaderValue(lighting, ambientLoc, ambientColor, SHADER_UNIFORM_VEC3);

    Camera3D camera {};
    camera.projection = CAMERA_PERSPECTIVE;
    camera.fovy = 75.0f;

    constexpr float roomHalf = 10.0f;
    constexpr float wallThickness = 0.5f;
    constexpr float roomHeight = 4.0f;

    const AABB groundCollider { { -roomHalf, -2.0f, -roomHalf }, { roomHalf, 0.0f, roomHalf } };
    const AABB leftWall { { -roomHalf, 0.0f, -roomHalf }, { -roomHalf + wallThickness, roomHeight, roomHalf } };
    const AABB rightWall { { roomHalf - wallThickness, 0.0f, -roomHalf }, { roomHalf, roomHeight, roomHalf } };
    const AABB backWall { { -roomHalf, 0.0f, -roomHalf }, { roomHalf, roomHeight, -roomHalf + wallThickness } };
    const AABB frontWall { { -roomHalf, 0.0f, roomHalf - wallThickness }, { roomHalf, roomHeight, roomHalf } };
    const AABB ceiling { { -roomHalf, roomHeight, -roomHalf }, { roomHalf, roomHeight + 0.4f, roomHalf } };

    const AABB jumpBox { { -1.2f, 0.0f, 1.6f }, { 1.2f, 0.75f, 3.8f } };

    std::vector<AABB> wallColliders { leftWall, rightWall, backWall, frontWall, jumpBox };
    std::vector<AABB> verticalColliders { groundCollider, ceiling, jumpBox };

    Player player;
    Monster monster;

    const float physicsDt = 1.0f / 120.0f;
    float accumulator = 0.0f;
    float animTime = 0.0f;
    float stepTimer = 0.0f;
    float jumpBufferTimer = 0.0f;
    float coyoteTimer = 0.0f;

    while (!WindowShouldClose()) {
        const float frameDt = std::min(GetFrameTime(), 0.05f);
        accumulator += frameDt;
        animTime += frameDt;
        if (IsKeyPressed(KEY_SPACE)) jumpBufferTimer = 0.12f;
        else jumpBufferTimer = std::max(0.0f, jumpBufferTimer - frameDt);

        const Vector2 mouseDelta = GetMouseDelta();
        player.yaw += mouseDelta.x * 0.08f;
        player.pitch = std::clamp(player.pitch - mouseDelta.y * 0.08f, -89.0f, 89.0f);

        while (accumulator >= physicsDt) {
            accumulator -= physicsDt;
            const bool wasGrounded = player.grounded;
            player.grounded = false;
            coyoteTimer = wasGrounded ? 0.10f : std::max(0.0f, coyoteTimer - physicsDt);

            const float yawRad = player.yaw * DEG2RAD;
            const Vector3 forward { std::sin(yawRad), 0.0f, -std::cos(yawRad) };
            const Vector3 right { std::cos(yawRad), 0.0f, std::sin(yawRad) };

            Vector3 moveInput { 0.0f, 0.0f, 0.0f };
            if (IsKeyDown(KEY_W)) moveInput = Vector3Add(moveInput, forward);
            if (IsKeyDown(KEY_S)) moveInput = Vector3Subtract(moveInput, forward);
            if (IsKeyDown(KEY_D)) moveInput = Vector3Add(moveInput, right);
            if (IsKeyDown(KEY_A)) moveInput = Vector3Subtract(moveInput, right);

            const float inputLenSq = Vector3LengthSqr(moveInput);
            if (inputLenSq > 0.0001f) moveInput = Vector3Scale(moveInput, 1.0f / std::sqrt(inputLenSq));

            const bool sneaking = IsKeyDown(KEY_LEFT_CONTROL) || IsKeyDown(KEY_RIGHT_CONTROL);
            const float speed = sneaking ? 1.8f : (IsKeyDown(KEY_LEFT_SHIFT) ? 6.0f : 3.8f);
            player.velocity.x = moveInput.x * speed;
            player.velocity.z = moveInput.z * speed;

            if (jumpBufferTimer > 0.0f && coyoteTimer > 0.0f) {
                player.velocity.y = 5.2f;
                jumpBufferTimer = 0.0f;
                coyoteTimer = 0.0f;
            } else if (wasGrounded && player.velocity.y < 0.0f) {
                player.velocity.y = 0.0f;
            }

            if (!wasGrounded || player.velocity.y > 0.0f) player.velocity.y -= 14.0f * physicsDt;

            ResolveAxis(player, wallColliders, 0, player.velocity.x * physicsDt);
            ResolveAxis(player, verticalColliders, 1, player.velocity.y * physicsDt);
            ResolveAxis(player, wallColliders, 2, player.velocity.z * physicsDt);

            if (player.grounded && player.bottomPos.y < 0.002f) {
                player.bottomPos.y = 0.0f;
                player.velocity.y = 0.0f;
            }

            const float horizontalSpeed = std::sqrt(player.velocity.x * player.velocity.x + player.velocity.z * player.velocity.z);
            if (player.grounded && horizontalSpeed > 0.2f) {
                stepTimer -= physicsDt;
                if (stepTimer <= 0.0f) {
                    if (soundsReady) {
                        if (GetRandomValue(0, 1) == 0) PlaySound(step1);
                        else PlaySound(step2);
                    }
                    stepTimer = 0.75f;
                }
            } else {
                stepTimer = 0.0f;
            }

            const Vector3 toPlayer {
                player.bottomPos.x - monster.bottomPos.x,
                0.0f,
                player.bottomPos.z - monster.bottomPos.z
            };
            const float distSq = toPlayer.x * toPlayer.x + toPlayer.z * toPlayer.z;
            const float reachDistance = player.halfExtents.x + monster.radius;
            if (distSq > reachDistance * reachDistance) {
                const float dist = std::sqrt(distSq);
                const float step = std::min(monster.speed * physicsDt, dist - reachDistance);
                if (step > 0.0f) {
                    const float nx = toPlayer.x / dist;
                    const float nz = toPlayer.z / dist;
                    MoveMonsterAxis(monster, 0, nx * step, roomHalf, wallThickness, jumpBox);
                    MoveMonsterAxis(monster, 2, nz * step, roomHalf, wallThickness, jumpBox);
                }
            }
            monster.bottomPos.y = 0.0f;
        }

        const float yawRad = player.yaw * DEG2RAD;
        const float pitchRad = player.pitch * DEG2RAD;
        const Vector3 viewDir {
            std::sin(yawRad) * std::cos(pitchRad),
            std::sin(pitchRad),
            -std::cos(yawRad) * std::cos(pitchRad)
        };

        camera.position = player.EyePos();
        camera.target = Vector3Add(camera.position, viewDir);
        camera.up = { 0.0f, 1.0f, 0.0f };

        BeginDrawing();
        ClearBackground({ 45, 96, 184, 255 });

        BeginMode3D(camera);
        BeginShaderMode(lighting);

        DrawRoomChessboard(roomHalf - wallThickness, 0.0f);

        DrawCube({ 0.0f, roomHeight + 0.2f, 0.0f }, roomHalf * 2.0f, 0.4f, roomHalf * 2.0f, Color{ 180, 180, 190, 255 });
        DrawCube({ -roomHalf + wallThickness * 0.5f, roomHeight * 0.5f, 0.0f }, wallThickness, roomHeight, roomHalf * 2.0f, Color{ 150, 150, 160, 255 });
        DrawCube({ roomHalf - wallThickness * 0.5f, roomHeight * 0.5f, 0.0f }, wallThickness, roomHeight, roomHalf * 2.0f, Color{ 150, 150, 160, 255 });
        DrawCube({ 0.0f, roomHeight * 0.5f, -roomHalf + wallThickness * 0.5f }, roomHalf * 2.0f, roomHeight, wallThickness, Color{ 150, 150, 160, 255 });
        DrawCube({ 0.0f, roomHeight * 0.5f, roomHalf - wallThickness * 0.5f }, roomHalf * 2.0f, roomHeight, wallThickness, Color{ 150, 150, 160, 255 });

        const Vector3 jumpSize { jumpBox.max.x - jumpBox.min.x, jumpBox.max.y - jumpBox.min.y, jumpBox.max.z - jumpBox.min.z };
        const Vector3 jumpCenter { jumpBox.min.x + jumpSize.x * 0.5f, jumpBox.min.y + jumpSize.y * 0.5f, jumpBox.min.z + jumpSize.z * 0.5f };
        DrawCube(jumpCenter, jumpSize.x, jumpSize.y, jumpSize.z, Color{ 190, 130, 90, 255 });

        const float horizontalSpeed = std::sqrt(player.velocity.x * player.velocity.x + player.velocity.z * player.velocity.z);
        const float moveFactor = std::clamp(horizontalSpeed / 6.0f, 0.0f, 1.0f);
        DrawPlayerBody(player, animTime, moveFactor);
        DrawMonster(monster);

        EndShaderMode();
        EndMode3D();

        DrawRectangle(15, 15, 600, 110, Fade(BLACK, 0.4f));
        DrawText("WASD move | SPACE jump | SHIFT sprint | CTRL sneak | ESC cursor", 25, 25, 20, RAYWHITE);
        DrawText(TextFormat("Pos: %.2f %.2f %.2f", player.bottomPos.x, player.bottomPos.y, player.bottomPos.z), 25, 55, 20, RAYWHITE);
        DrawText(TextFormat("FPS: %d | MonsterDist: %.2f | Sound: %s", GetFPS(), Vector3Distance(monster.bottomPos, player.bottomPos), soundsReady ? "OK" : "MISSING"), 25, 85, 20, RAYWHITE);

        if (IsKeyPressed(KEY_ESCAPE)) {
            if (IsCursorHidden()) EnableCursor();
            else DisableCursor();
        }

        EndDrawing();
    }

    if (IsSoundValid(step1)) UnloadSound(step1);
    if (IsSoundValid(step2)) UnloadSound(step2);
    CloseAudioDevice();
    UnloadShader(lighting);
    CloseWindow();
    return 0;
}
