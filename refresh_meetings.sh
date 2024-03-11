#! /bin/bash

if [ ! -d ./data ]; then
  mkdir -p data;
fi

# Example of how to setup USEPYTHON variable from virtualenv - comment out and set to your own path
export USEPYTHON='/home/nznaorg/virtualenv/repositories/meeting_picker/3.9/bin/python3'

declare -a arr_linux=("linux-gnu" "free-bsd" "darwin")
for item in "${arr_linux[@]}}"
do
    if [ "$OSTYPE" = "$item" ]; then
        $USEPYTHON refresh_meetings.py
    fi
echo "Completed meeting refresh on $(date)"
done

declare -a arr=("msys" "cygwin" "win32")
for item in "${arr[@]}"
do
    if [ "$OSTYPE" = "$item" ] 
        then $USEPYTHON refresh_meetings_win.py
    fi
echo "Completed meeting refresh on $(date)"
done
