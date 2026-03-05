FC ?= gfortran
FFLAGS ?= -O2 -Wall -Wextra

BIN_DIR := bin
SRC_DIR := src
TARGET := $(BIN_DIR)/fd3d_cli

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC_DIR)/main.f90 $(SRC_DIR)/wave3d_solver.f90
	mkdir -p $(BIN_DIR)
	$(FC) $(FFLAGS) $(SRC_DIR)/wave3d_solver.f90 $(SRC_DIR)/main.f90 -o $(TARGET)

clean:
	rm -rf $(BIN_DIR)
