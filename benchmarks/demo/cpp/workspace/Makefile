CXX ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -pedantic

BIN_DIR := bin
SRC_DIR := src
TARGET := $(BIN_DIR)/rk2_cli

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC_DIR)/main.cpp $(SRC_DIR)/rk2.cpp $(SRC_DIR)/rk2.hpp
	mkdir -p $(BIN_DIR)
	$(CXX) $(CXXFLAGS) $(SRC_DIR)/main.cpp $(SRC_DIR)/rk2.cpp -o $(TARGET)

clean:
	rm -rf $(BIN_DIR)
