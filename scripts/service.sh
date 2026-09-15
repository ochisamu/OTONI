#!/usr/bin/env bash
set -euo pipefail
YUE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "${1:-start}" in
  start)
    if systemctl --user is-active --quiet yue2-studio.service; then
      echo 'OTONI is running: http://localhost:7860'
    else
      python3 "$YUE_ROOT/scripts/install_service.py" --output "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/yue2-studio.service"
      systemctl --user daemon-reload
      systemctl --user enable --now yue2-studio.service
      echo 'Opening address: http://localhost:7860'
    fi
    ;;
  stop) systemctl --user stop yue2-studio.service ;;
  restart) "$0" stop; "$0" start ;;
  status) systemctl --user status yue2-studio.service --no-pager ;;
  logs) journalctl --user -u yue2-studio.service -f ;;
  *) echo 'Usage: scripts/service.sh {start|stop|restart|status|logs}'; exit 2 ;;
esac
