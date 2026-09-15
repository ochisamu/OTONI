"""Generate a user service for the current checkout, without machine-specific paths."""
import argparse
from pathlib import Path


def service_text(root):
    def quote(value):
        return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('%','%%').replace('$','$$')+'"'
    return f'''[Unit]
Description=OTONI local music studio
After=network.target

[Service]
Type=simple
WorkingDirectory={str(root).replace('%','%%')}
ExecStart={quote(root/'scripts/start.sh')}
Restart=on-failure
RestartSec=3
TimeoutStopSec=30
KillMode=control-group

[Install]
WantedBy=default.target
'''

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    # Replace an earlier linked unit without editing the link target.
    if args.output.is_symlink():args.output.unlink()
    args.output.write_text(service_text(Path(__file__).resolve().parents[1]))
