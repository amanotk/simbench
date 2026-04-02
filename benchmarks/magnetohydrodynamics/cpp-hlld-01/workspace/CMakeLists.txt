cmake_minimum_required(VERSION 3.16)

project(cpp_hlld LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(FetchContent)

option(SIMBENCH_ENABLE_HIDDEN_TESTS "Build hidden Catch2 tests" OFF)
set(
  SIMBENCH_HIDDEN_TEST_SOURCE
  ""
  CACHE FILEPATH
  "Path to hidden Catch2 test source"
)

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

add_library(hlld_solver
  src/hlld.cpp
)

target_include_directories(hlld_solver PUBLIC
  src
)

add_executable(hlld_public_tests
  tests/cpp/test_public.cpp
)

target_link_libraries(hlld_public_tests PRIVATE
  hlld_solver
  Catch2::Catch2WithMain
)

set_target_properties(hlld_public_tests PROPERTIES
  RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/tests"
)

if(SIMBENCH_ENABLE_HIDDEN_TESTS)
  if(NOT EXISTS "${SIMBENCH_HIDDEN_TEST_SOURCE}")
    message(FATAL_ERROR "Hidden test source not found: ${SIMBENCH_HIDDEN_TEST_SOURCE}")
  endif()

  add_executable(hlld_hidden_tests
    "${SIMBENCH_HIDDEN_TEST_SOURCE}"
  )

  target_link_libraries(hlld_hidden_tests PRIVATE
    hlld_solver
    Catch2::Catch2WithMain
  )

  set_target_properties(hlld_hidden_tests PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/tests"
  )
endif()
