#!/bin/bash
# Compila e roda os testes da lógica do firmware no PC (Linux/WSL, g++ >= 9).
set -e
cd "$(dirname "$0")"
M=../../main
g++ -std=c++17 -O1 -Wall -Wextra -Wdouble-promotion -Werror \
    -I"$M/logic" -I"$M/generated" test_logic.cc "$M"/logic/*.cc -o /tmp/agrosense_host_tests
/tmp/agrosense_host_tests
