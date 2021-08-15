# Can't use -m or -c in main.c, would import from current working directory (user's home)
from porcupine.__main__ import main

main()
