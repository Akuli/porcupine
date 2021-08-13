#!/bin/bash
x86_64-w64-mingw32-windres resources.rc -O coff -o resources.res
x86_64-w64-mingw32-gcc -municode -mwindows -o Porcupine.exe main.c resources.res
