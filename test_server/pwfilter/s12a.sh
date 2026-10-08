#!/bin/sh
PW_BASE=41964
wr() { prefman set 0 "$(printf 0x%05x $1)" l "$2" >/dev/null 2>&1; }
rd() { prefman get 0 "$(printf 0x%05x $1)" l 2>/dev/null | grep -o 'value = [-0-9]*' | sed 's/value = //'; }
so() { echo $(( PW_BASE + $1 * 52 + $2 * 4 )); }
# slot 9 = 强红
wr $(so 0 9) 200; wr $(so 1 9) 60; wr $(so 2 9) 60
# slot 10 = 强绿
wr $(so 0 10) 60; wr $(so 1 10) 200; wr $(so 2 10) 60
# slot 12 = 强蓝
wr $(so 0 12) 60; wr $(so 1 12) 60; wr $(so 2 12) 200
echo "9:$(rd $(so 0 9))/$(rd $(so 1 9))/$(rd $(so 2 9))"
echo "10:$(rd $(so 0 10))/$(rd $(so 1 10))/$(rd $(so 2 10))"
echo "12:$(rd $(so 0 12))/$(rd $(so 1 12))/$(rd $(so 2 12))"
echo A_DONE
