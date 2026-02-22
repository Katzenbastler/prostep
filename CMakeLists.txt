cmake_minimum_required(VERSION 3.21)
project(IdleHoursEngineStarter VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

set(BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(BUILD_GAMES OFF CACHE BOOL "" FORCE)
set(BUILD_SHARED_LIBS OFF CACHE BOOL "" FORCE)

FetchContent_Declare(
  raylib
  GIT_REPOSITORY https://github.com/raysan5/raylib.git
  GIT_TAG 5.5
)
FetchContent_MakeAvailable(raylib)

add_executable(idle_hours
  src/main.cpp
)

target_link_libraries(idle_hours PRIVATE raylib)

if(MSVC)
  target_compile_options(idle_hours PRIVATE /W4 /permissive-)
else()
  target_compile_options(idle_hours PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_custom_command(TARGET idle_hours POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_directory
  ${CMAKE_SOURCE_DIR}/assets $<TARGET_FILE_DIR:idle_hours>/assets
)
