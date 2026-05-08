cmake_minimum_required(VERSION 3.13)

# Default RP2040 Pico; Pico W: -DPICO_BOARD=pico_w (lab/docker Makefile PICO_BOARD=pico_w).
set(PICO_BOARD pico CACHE STRING "Board type")

if(NOT DEFINED ENV{PICO_SDK_PATH})
    message(FATAL_ERROR "PICO_SDK_PATH is not set (set by pico-dev container)")
endif()

include($ENV{PICO_SDK_PATH}/pico_sdk_init.cmake)

project(hello_lab C CXX ASM)

pico_sdk_init()

add_executable(hello_lab src/main.c)
target_link_libraries(hello_lab pico_stdlib)
pico_enable_stdio_usb(hello_lab 1)

pico_add_extra_outputs(hello_lab)
