import argparse
import json
from pathlib import Path
import sys
import time
import numpy as np
from .profile import bundled_profile, parse_profile
from .storage import Store
from .protocol import Parser, encode_frame
from .transport import ports, synthetic_signal


def seed_demo(store, sessions=3, repetitions=4):
    """Bounded synthetic fixtures, with honest provenance. Never a speech dataset."""
    profile = bundled_profile()
    ids = []
    for visit in range(sessions):
        session = store.create_session(f"Synthetic visit {visit+1}", "synthetic-fixture", "simulator", profile,
                                       "Generated labelled waveform; software verification only")
        ids.append(session["id"])
        for label in ("add a note", "new paragraph", "rest"):
            for rep in range(repetitions):
                stamps = np.arange(60, dtype=np.int64) * 50_000_000 + 1
                signals, packets = [], []
                for i in range(len(stamps)):
                    raw = encode_frame(i, synthetic_signal(label, i*.05 + .02*rep, seed=visit*10000+rep*100+i))
                    frame = Parser().feed(raw)[0]
                    signals.append(frame.complex_heatmap(profile.range_bins))
                    packets.append(raw)
                store.save_trial(session["id"], label, stamps, signals, np.arange(len(stamps)), packets,
                                 {"synthetic": True, "source": "simulator", "articulation": "silent"})
    return ids


def main():
    parser = argparse.ArgumentParser(description="Gasp · local radar research")
    parser.add_argument("--data", default="data", help="Local dataset directory")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Open local recording and training UI")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--research", action="store_true", help="Enable experimental classifier evaluation; not transcription")
    sub.add_parser("doctor", help="Inspect Mac ports and prerequisites without opening hardware")
    inspect = sub.add_parser("profile", help="Inspect and budget a bundled or custom profile")
    inspect.add_argument("name", nargs="?", default="usb-phase-20hz")
    demo = sub.add_parser("seed-demo", help="Generate explicitly synthetic pipeline-test sessions")
    demo.add_argument("--sessions", type=int, default=3)
    demo.add_argument("--repetitions", type=int, default=4)
    training = sub.add_parser("train", help="Train the CPU baseline with a whole-session holdout")
    training.add_argument("--sessions", nargs="+", required=True)
    training.add_argument("--test", nargs="+", required=True)
    training.add_argument("--articulation", choices=("silent", "voiced", "whisper"), help="Select one mode when visits contain paired takes")
    replay = sub.add_parser("replay", help="Validate a saved SDK UART binary through the streaming parser")
    replay.add_argument("path")
    replay.add_argument("--range-bins", type=int, default=64)
    dca = sub.add_parser("dca-record", help="Native DCA1000 UDP capture, with CLI-configured radar")
    dca.add_argument("--output", required=True)
    dca.add_argument("--cli-port", required=True)
    dca.add_argument("--host-ip", default="192.168.33.30")
    dca.add_argument("--board-ip", default="192.168.33.180")
    dca.add_argument("--seconds", type=float, default=5)
    dca.add_argument("--profile", default="dca-raw")
    imp = sub.add_parser("dca-import", help="Convert a short headerless two-lane capture into a labelled trial")
    imp.add_argument("capture_dir")
    imp.add_argument("--label", required=True)
    imp.add_argument("--subject", default="Boyd")
    imp.add_argument("--session-id", help="Append another capture to an existing DCA session")
    imp.add_argument("--confirm-layout", action="store_true", help="Confirm two-lane complex16 I0/I1/Q0/Q1, RX noninterleaved, TDM, no headers")
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            from .server import create_app
            print(f"Gasp: http://127.0.0.1:{args.port}")
            uvicorn.run(create_app(args.data, research_enabled=args.research), host="127.0.0.1", port=args.port, log_level="info", access_log=False)
            return
        if args.command == "doctor":
            print(json.dumps({"python": sys.version, "platform": sys.platform, "serial_ports": ports(),
                              "hardware_validation": "pending", "uart": "115200 CLI / 921600 data",
                              "profile": bundled_profile().summary(),
                              "driver": "https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers",
                              "reminder": "SDK 3.x OOB AOP firmware required; no firmware is flashed by this app"}, indent=2))
            return
        if args.command == "profile":
            p = parse_profile(Path(args.name).read_text()) if Path(args.name).is_file() else bundled_profile(args.name)
            print(json.dumps(p.summary(), indent=2))
            return
        store = Store(args.data)
        if args.command == "seed-demo":
            if not 2 <= args.sessions <= 10 or not 2 <= args.repetitions <= 20:
                raise ValueError("Use 2–10 sessions and 2–20 repetitions for a bounded fixture")
            print(json.dumps({"synthetic": True, "session_ids": seed_demo(store,args.sessions,args.repetitions)}, indent=2))
        elif args.command == "train":
            from .training import train
            print(json.dumps(train(store, args.sessions, args.test, articulation=args.articulation), indent=2))
        elif args.command == "replay":
            p, count, complex_count = Parser(), 0, 0
            with Path(args.path).open("rb") as f:
                while chunk := f.read(137):
                    for frame in p.feed(chunk):
                        count += 1
                        complex_count += frame.complex_heatmap(args.range_bins) is not None
            print(json.dumps({"frames": count, "complex_frames": complex_count, "bad_packets": p.bad_packets,
                              "discarded_bytes": p.discarded_bytes, "trailing_bytes": len(p.buffer)}, indent=2))
            if not count or p.bad_packets or len(p.buffer):
                raise ValueError("UART replay is empty, malformed or incomplete")
        elif args.command == "dca-record":
            from .dca import capture
            p = parse_profile(Path(args.profile).read_text()) if Path(args.profile).is_file() else bundled_profile(args.profile)
            print(json.dumps(capture(p,args.output,args.cli_port,args.host_ip,args.board_ip,args.seconds), indent=2))
        elif args.command == "dca-import":
            from .dca import import_capture
            if not args.confirm_layout:
                raise ValueError("Verify the documented ADC layout, then pass --confirm-layout; this is not auto-detected")
            folder = Path(args.capture_dir)
            manifest = json.loads((folder/"manifest.json").read_text())
            if manifest["status"] != "complete":
                raise ValueError("Capture was not completed successfully")
            p = parse_profile(manifest["profile"]["text"])
            if args.session_id:
                s = store.session(args.session_id)
                if s["source"] != "dca1000" or s["profile"]["sha256"] != p.sha256 or s["subject"] != args.subject:
                    raise ValueError("Existing DCA session source/profile/subject mismatch")
            else:
                s = store.create_session("DCA visit "+time.strftime("%Y-%m-%d"),args.subject,"dca1000",p)
            result = import_capture(store, folder, s, args.label)
            print(json.dumps({"session_id":s["id"],"trial":result},indent=2))
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
