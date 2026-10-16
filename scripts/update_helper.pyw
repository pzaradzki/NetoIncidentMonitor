"""Entry point compiled as an independent, windowless updater executable."""
import sys
from neto_incident_monitor.update_installer import main

if __name__ == '__main__':
    main(sys.argv[1])
