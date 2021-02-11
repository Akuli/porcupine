import re
import pty
import subprocess


#pid, fd = pty.fork()
#if pid == 0:
#    # child
#    os.execv('/bin/bash', ['bash', '-c', 'sleep 1 && gcc'])
#else:
#    # parent
#    print(pid)
#    with open(fd, 'rb') as f:
#        while True:
#            try:
#                line = f.readline()
#            except OSError:
#                break
#            print(line)


master_fd, slave_fd = pty.openpty()#os.openpty()
subprocess.call(['gcc'], stdout=slave_fd, stderr=slave_fd)
with open(master_fd, 'rb') as f:
    while True:
        try:
            line = f.readline().decode('utf-8')
        except OSError:
            break

        line = re.sub(r'\x1b\[([0-9]+|K|K |)m', r'<\1>', line)
        print(repr(line))
