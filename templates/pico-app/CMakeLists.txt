cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico CACHE STRING "Board type (pico, pico_w, ...)")

include(pico_sdk_import.cmake)

project({{APP_NAME}} C CXX ASM)

pico_sdk_init()

add_executable({{APP_NAME}} src/main.c)
target_link_libraries({{APP_NAME}} pico_stdlib)
pico_enable_stdio_usb({{APP_NAME}} 1)

pico_add_extra_outputs({{APP_NAME}})
