"""Start the local business profile editor from any working directory."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from peerproof.profile.server import create_server


def main():
    parser = argparse.ArgumentParser(description="PeerProof 사업 프로필 입력·저장·수정")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "processed" / "business_profiles")
    args = parser.parse_args()
    server = create_server(args.data_dir, args.port)
    print(f"PeerProof: http://127.0.0.1:{server.server_port}", flush=True)
    print(f"프로필 저장 경로: {args.data_dir}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
