cmake_minimum_required(VERSION 3.16)
project(UE4ESPDetectionTester)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_FLAGS_RELEASE "-O3")
set(CMAKE_CXX_FLAGS_DEBUG "-g -O0")

# Platform check
if(NOT WIN32)
    message(FATAL_ERROR "This project requires Windows platform for memory reading")
endif()

# Main executable
add_executable(UE4ESPDetectionTester
    UE4ESPDetectionTester.cpp
)

# Link Windows libraries
target_link_libraries(UE4ESPDetectionTester
    kernel32
    psapi
    ntdll
)

# Include directories
target_include_directories(UE4ESPDetectionTester PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# Compiler flags for MSVC
if(MSVC)
    target_compile_options(UE4ESPDetectionTester PRIVATE
        /W4
        /WX
        /EHsc
    )
else()
    target_compile_options(UE4ESPDetectionTester PRIVATE
        -Wall
        -Wextra
        -Werror
    )
endif()

# Output directory
set_target_properties(UE4ESPDetectionTester PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# Installation
install(TARGETS UE4ESPDetectionTester
    RUNTIME DESTINATION bin
)

install(FILES
    config.json
    SETUP_GUIDE.md
    README_ESP_TESTER.md
    ue4_esp_tester.py
    find_offsets.py
    DESTINATION share/UE4ESPDetectionTester
)

# Print build info
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ Standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "Compiler: ${CMAKE_CXX_COMPILER}")
