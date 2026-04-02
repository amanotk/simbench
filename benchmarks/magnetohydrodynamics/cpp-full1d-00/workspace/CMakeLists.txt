cmake_minimum_required(VERSION 3.16)

project(cpp_full_solver1d LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

find_package(Catch2 3 QUIET)

if(NOT Catch2_FOUND)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.13.0
    GIT_SHALLOW TRUE
  )
  FetchContent_MakeAvailable(Catch2)
endif()

add_library(mhd1d_solver
  src/mhd1d.cpp
  src/hlld.cpp
)

target_include_directories(mhd1d_solver PUBLIC
  src
  ../../../common/include
)

add_executable(cpp_full_solver1d
  src/main.cpp
)

target_link_libraries(cpp_full_solver1d PRIVATE
  mhd1d_solver
)

set_target_properties(cpp_full_solver1d PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

add_executable(cpp_full_solver1d_public_tests
  tests/cpp/test_public.cpp
)

target_link_libraries(cpp_full_solver1d_public_tests PRIVATE
  mhd1d_solver
  Catch2::Catch2WithMain
)

target_include_directories(cpp_full_solver1d_public_tests PRIVATE
  src
  ../../../common/include
)

set_target_properties(cpp_full_solver1d_public_tests PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/tests"
)
