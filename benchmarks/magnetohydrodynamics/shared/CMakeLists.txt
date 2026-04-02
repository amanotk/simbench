cmake_minimum_required(VERSION 3.16)

project(magnetohydrodynamics_shared_reference LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(mhd1d_reference_lib
  src/mhd1d.cpp
  src/hlld.cpp
)

target_include_directories(mhd1d_reference_lib PUBLIC
  src
  ../../common/include
)

add_executable(mhd1d_reference
  src/main.cpp
)

target_link_libraries(mhd1d_reference PRIVATE
  mhd1d_reference_lib
)

set_target_properties(mhd1d_reference PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)
