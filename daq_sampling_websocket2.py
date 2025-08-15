import asyncio
import json
import time, datetime
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional

import websockets
import websockets.exceptions
# DAQ
import nidaqmx
import nidaqmx.system
from nidaqmx.constants import CurrentUnits, CurrentShuntResistorLocation, AcquisitionType, READ_ALL_AVAILABLE
# RIG (serial)
# pip install pyserial pyserial-asyncio
import serial
import serial_asyncio
import inspect # Used to get the line number

PORT_NUMBER = 8765
BROADCAST_HZ = 15             # how often to push data to clients
DAQ_READ_CHUNK = 100          # how many samples to read per loop iteration (tune)
WS_MAX_QUEUE = 3              # per-client outbound queue size (drop old frames)


# ------------- Utilities -------------

# Verbose output flag for debugging
VERBOSE = True

# --- Logging Colors ---
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BLUE = "\033[94m"
COLOR_ORANGE = "\033[38;5;172m"
COLOR_GRAY = "\033[90m"

def log(message, level="info"):

    if not VERBOSE:
        return
    
    # ts = datetime.datetime.now().strftime("%H:%M:%S")
    frame = inspect.currentframe().f_back
    color = {
        "info": COLOR_CYAN,
        "success": COLOR_GREEN,
        "warn": COLOR_YELLOW,
        "error": COLOR_RED,
        "debug": COLOR_GRAY,
        "header": COLOR_BLUE,
        "data": COLOR_ORANGE,
    }.get(level, COLOR_RESET)

    print(f"{color}[DSW #{frame.f_lineno}] {message}{COLOR_RESET}")

def safe_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=False)




# ------------- Ring buffers -------------

@dataclass
class RingBuffers:
    # Large rolling arrays
    raw_pressure: deque = field(default_factory=lambda: deque(maxlen=27000))
    raw_time: deque = field(default_factory=lambda: deque(maxlen=27000))

    # Smaller rolling arrays
    filt_pressure: deque = field(default_factory=lambda: deque(maxlen=500))
    speed: deque = field(default_factory=lambda: deque(maxlen=500))

    # Rig data (example)
    rig_time: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_ctPressure: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_whPressure: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_ctDepth: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_ctWeight: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_ctSpeed: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_ctFluidRate: deque = field(default_factory=lambda: deque(maxlen=1000))
    rig_n2FluidRate: deque = field(default_factory=lambda: deque(maxlen=1000))

    def snapshot_tail(self, n: int = 200) -> Dict[str, List[float]]:
        # Send only the recent tail to keep messages small
        def tail(dq: deque, k: int) -> List[float]:
            if k >= len(dq): return list(dq)
            # slicing deques is O(n); for small k this is fine
            return list(dq)[-k:]
        return {
            "rawPressure": tail(self.raw_pressure, n),
            "rawTime": tail(self.raw_time, n),
            "filterPressure": tail(self.filt_pressure, n),
            "tractorSpeed": tail(self.speed, n),
            "rigTime": tail(self.rig_time, n),
            "rigCh1": tail(self.rig_ctPressure, n),
            "rigCh1": tail(self.rig_whPressure, n),
            "rigCh1": tail(self.rig_ctDepth, n),
            "rigCh1": tail(self.rig_ctWeight, n),
            "rigCh1": tail(self.rig_ctSpeed, n),
            "rigCh1": tail(self.rig_ctFluidRate, n),
            "rigCh1": tail(self.rig_n2FluidRate, n),
        }





# ------------- DAQ Session -------------

@dataclass
class DAQConfig:
    device: Optional[str] = None         # None => auto-discover
    channels: List[str] = field(default_factory=lambda: ["ai0"])
    sample_rate_hz: float = 30000.0

class DAQSession:
    def __init__(self, buffers: RingBuffers):
        self.cfg = DAQConfig()
        self.buffers = buffers
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()

    def configure(self, **kwargs):
        if self._task and not self._task.done():
            raise RuntimeError("Stop DAQ before reconfiguring.")
        for k, v in kwargs.items():
            if hasattr(self.cfg, k):
                setattr(self.cfg, k, v)
        log(f"DAQ configured: {self.cfg}", "success")

    async def start(self):
        if self._task and not self._task.done():
            log("DAQ already running.", "warn")
            return
        self._running.set()
        self._task = asyncio.create_task(self._run())
        log("DAQ started.", "success")

    async def stop(self):
        self._running.clear()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            log("DAQ stopped.", "success")

    def _auto_device(self) -> str:
        system = nidaqmx.system.System.local()
        if not system.devices:
            raise RuntimeError("No NI devices found.")
        # Prefer a module device (not cDAQ chassis)
        for dev in system.devices:
            if not dev.product_type.startswith("cDAQ"):
                return dev.name
        # Fallback: first module of the first chassis if exposed
        ch = system.devices[0]
        try:
            if ch.modules:
                return ch.modules[0].name
        except AttributeError:
            pass
        # Last resort: first device name
        return ch.name

    async def _run(self):
        """
        Producer loop that reads NI DAQ and fills buffers.
        Uses a small sleep to yield to event loop; DAQmx read itself is blocking per call.
        """
        device = self.cfg.device or self._auto_device()
        chan_list = [f"{device}/{ch}" for ch in self.cfg.channels]
        sr = self.cfg.sample_rate_hz

        # Create task & configure
        with nidaqmx.Task() as task:
            for ch in chan_list:
                task.ai_channels.add_ai_voltage_chan(ch)
            task.timing.cfg_samp_clk_timing(rate=sr, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)

            # Warm-up read to start hardware
            _ = task.read(number_of_samples_per_channel=DAQ_READ_CHUNK, timeout=10.0)

            t = 0.0
            dt = 1.0 / sr

            while self._running.is_set():
                # Read a small chunk per loop to keep latency low
                data = task.read(number_of_samples_per_channel=DAQ_READ_CHUNK, timeout=2.0)

                # 'data' shape depends on number of channels; normalize to list-of-floats for first channel
                if isinstance(data[0], list):   # multi-chan
                    ch0 = data[0]
                else:                            # single-chan returns list
                    ch0 = data

                # Append to buffers
                for v in ch0:
                    self.buffers.raw_pressure.append(float(v))
                    self.buffers.raw_time.append(t)
                    t += dt

                # (Optional) compute/update filtered/speed here or in a separate consumer
                # Example placeholder:
                if ch0:
                    self.buffers.filt_pressure.append(ch0[-1])  # replace with your filter
                    self.buffers.speed.append(0.0)

                # Yield control
                await asyncio.sleep(0)




# ------------- RIG Session (serial) -------------

@dataclass
class RigConfig:
    port: Optional[str] = None
    baudrate: int = 115200

class RigSession:
    def __init__(self, buffers: RingBuffers):
        self.cfg = RigConfig()
        self.buffers = buffers
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()

    def configure(self, **kwargs):
        if self._task and not self._task.done():
            raise RuntimeError("Stop RIG before reconfiguring.")
        for k, v in kwargs.items():
            if hasattr(self.cfg, k):
                setattr(self.cfg, k, v)
        log(f"RIG configured: {self.cfg}", "success")

    async def start(self):
        if not self.cfg.port:
            raise RuntimeError("RIG port not set. Call configure_rig first.")
        if self._task and not self._task.done():
            log("RIG already running.", "warn")
            return
        self._running.set()
        self._task = asyncio.create_task(self._run())
        log("RIG started.", "success")

    async def stop(self):
        self._running.clear()
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            log("RIG stopped.", "success")

    async def _run(self):
        # asyncio serial reader
        reader, writer = await serial_asyncio.open_serial_connection(
            url=self.cfg.port, baudrate=self.cfg.baudrate
        )
        try:
            while self._running.is_set():
                line = await reader.readline()   # bytes until \n
                if not line:
                    await asyncio.sleep(0)
                    continue
                # Parse line -> value(s)
                try:
                    val = float(line.decode("utf-8", "ignore").strip())
                except Exception:
                    continue

                # Append to buffers
                self.buffers.rig_ctPressure.append(val)
                self.buffers.rig_whPressure.append(val)
                self.buffers.rig_ctDepth.append(val)
                self.buffers.rig_ctWeight.append(val)
                self.buffers.rig_ctSpeed.append(val)
                self.buffers.rig_ctFluidRate.append(val)
                self.buffers.rig_n2FluidRate.append(val)
                # You can use a local timebase or shared; simple local:
                self.buffers.rig_time.append(asyncio.get_event_loop().time())
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass




# ------------- Websocket server & control -------------

class Hub:
    """Tracks connected clients and handles broadcasting."""
    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()

    async def register(self, ws):
        self.clients.add(ws)

    async def unregister(self, ws):
        self.clients.discard(ws)

    async def broadcast(self, msg: Dict[str, Any]):
        if not self.clients:
            return
        payload = safe_json(msg)
        # Send concurrently; drop slow clients
        send_tasks = []
        for ws in list(self.clients):
            try:
                send_tasks.append(asyncio.create_task(ws.send(payload)))
            except Exception:
                await self.unregister(ws)
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)


async def ws_handler(ws, path, daq: DAQSession, rig: RigSession, hub: Hub, shutdown_evt: asyncio.Event):
    await hub.register(ws)
    log("Client connected.", "success")
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            cmd = msg.get("cmd")
            if cmd == "configure_daq":
                daq.configure(**{k: v for k, v in msg.items() if k != "cmd"})
                await ws.send(safe_json({"ok": True}))
            elif cmd == "start_daq":
                await daq.start()
                await ws.send(safe_json({"ok": True}))
            elif cmd == "stop_daq":
                await daq.stop()
                await ws.send(safe_json({"ok": True}))

            elif cmd == "configure_rig":
                rig.configure(**{k: v for k, v in msg.items() if k != "cmd"})
                await ws.send(safe_json({"ok": True}))
            elif cmd == "start_rig":
                await rig.start()
                await ws.send(safe_json({"ok": True}))
            elif cmd == "stop_rig":
                await rig.stop()
                await ws.send(safe_json({"ok": True}))

            elif cmd == "shutdown":
                await ws.send(safe_json({"ok": True}))
                shutdown_evt.set()
            else:
                await ws.send(safe_json({"ok": False, "error": "unknown_command"}))
    finally:
        await hub.unregister(ws)
        log("Client disconnected.", "warn")


async def broadcaster(hub: Hub, buffers: RingBuffers):
    period = 1.0 / BROADCAST_HZ
    while True:
        await asyncio.sleep(period)
        tail = buffers.snapshot_tail(n=200)
        await hub.broadcast({"type": "stream", "data": tail})




# ------------- Main -------------

async def main():
    buffers = RingBuffers()
    daq = DAQSession(buffers)
    rig = RigSession(buffers)
    hub = Hub()
    shutdown_evt = asyncio.Event()

    async def handler(ws, path):
        return await ws_handler(ws, path, daq, rig, hub, shutdown_evt)

    ws_server = await websockets.serve(handler, "0.0.0.0", PORT_NUMBER)
    log(f"[ WS ] WebSocket server listening on :{PORT_NUMBER}", "success")

    # Run broadcaster forever; DAQ and RIG tasks are started via websocket commands
    tasks = [
        asyncio.create_task(broadcaster(hub, buffers)),
    ]

    try:
        # Run until a client sends {"cmd":"shutdown"}
        await shutdown_evt.wait()
    finally:
        log("Shutting down…", "warn")
        ws_server.close()
        await ws_server.wait_closed()
        await daq.stop()
        await rig.stop()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log("Shutdown complete.", "success")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("KeyboardInterrupt — exiting.", "warn")
