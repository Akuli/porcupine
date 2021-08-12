# Based on a file that pynsis generated
import sys, os
import site
scriptdir, script = os.path.split(os.path.abspath(__file__))
installdir = scriptdir  # for compatibility with commands
pkgdir = os.path.join(scriptdir, 'pkgs')
sys.path.insert(0, pkgdir)
# Ensure .pth files in pkgdir are handled properly
site.addsitedir(pkgdir)
os.environ['PYTHONPATH'] = pkgdir + os.pathsep + os.environ.get('PYTHONPATH', '')


if __name__ == '__main__':
    from porcupine.__main__ import main
    main()
