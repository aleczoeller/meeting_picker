#! /bin/bash

if [ ! -d ./data ]; then
  mkdir -p data;
fi

# Example of how to setup USEPYTHON variable from virtualenv - comment out and set to your own path
export USEPYTHON='/home/nznaorg/virtualenv/repositories/meeting_picker/3.9/bin/python3'
$USEPYTHON refresh_meetings.py

