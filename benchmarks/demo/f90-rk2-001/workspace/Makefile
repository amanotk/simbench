FC ?= gfortran
FFLAGS ?= -O2 -Wall -Wextra
CPPFLAGS ?= -I/usr/local/include/FLAP -I/usr/local/include/FACE -I/usr/local/include/PENF
LDLIBS ?= -lFLAP -lFACE -lPENF

BIN_DIR := bin
SRC_DIR := src
TARGET := $(BIN_DIR)/rk2_cli

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC_DIR)/main.f90 $(SRC_DIR)/rk2_solver.f90
	mkdir -p $(BIN_DIR)
	$(FC) $(FFLAGS) $(CPPFLAGS) $(SRC_DIR)/rk2_solver.f90 $(SRC_DIR)/main.f90 -o $(TARGET) $(LDLIBS)

clean:
	rm -rf $(BIN_DIR)
