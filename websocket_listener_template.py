import asyncio
import websockets
import json

PORT_NUMBER = 9813

clients = set()

async def ws_handler(ws, path, session):
    await clients.add(ws)
    async for message in ws:
        try:
            data = json.loads(message)
            print("======================")
            print(f"[WS RX] Raw JSON: {message}")   # raw string
            print(f"[WS RX] Parsed dict: {json.dumps(data, indent=2)}")  # pretty print parsed dict
            print("======================")

            # Example command dispatch
            cmd = data.get("cmd")
            if cmd:
                print(f"[WS CMD] Received command: {cmd}")
                # route commands here
                if cmd == "start_daq":
                    print("[ACTION] Starting DAQ...")
                elif cmd == "stop_daq":
                    print("[ACTION] Stopping DAQ...")
                elif cmd == "pause_recording":
                    print("[ACTION] Pausing recording...")
                elif cmd == "resume_recording":
                    print("[ACTION] Resuming recording...")

        except json.JSONDecodeError:
            print(f"[WS RX] Non-JSON message: {message}")

async def main():
    session = {}  # or your DAQSession()
    async with websockets.serve(
        lambda ws, path: ws_handler(ws, path, session),
        "localhost",
        PORT_NUMBER,
    ):
        print(f"[WS] Listening on ws://localhost:{PORT_NUMBER}")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Exit] KeyboardInterrupt received. Exiting cleanly.")
