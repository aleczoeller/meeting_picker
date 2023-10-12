#! /bin/bash

if [ ! -d ./data ]; then
  mkdir -p data;
fi

declare -a arr_linux=("linux-gnu" "free-bsd" "darwin")
for item in "${arr_linux[@]}}"
do
    if [ "$OSTYPE" = "$item" ]; then
        $PYTHONDIS refresh_meetings.py
    fi
done

declare -a arr=("msys" "cygwin" "win32")
for item in "${arr[@]}"
do
    if [ "$OSTYPE" = "$item" ] 
        then $PYTHONDIS refresh_meetings_win.py
    fi
done
