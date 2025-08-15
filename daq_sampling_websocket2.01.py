import asyncio
import json
# import time, datetime
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
import numpy as np

# Utilities for logging/file writiing
import os, re, sqlite3, time, datetime
from pathlib import Path

PORT_NUMBER = 8765
BROADCAST_HZ = 15             # how often to push data to clients
DAQ_READ_CHUNK = 100          # how many samples to read per loop iteration (tune)
WS_MAX_QUEUE = 3              # per-client outbound queue size (drop old frames)


# ------------- Utilities -------------

# Verbose output flag for debugging
VERBOSE = True

# ----------- Logging Colors -----------
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


# ------------- Logging to file with SQLite -------------

async def broadcaster(hub: Hub, buffers: RingBuffers):
    period = 1.0 / BROADCAST_HZ
    while True:
        await asyncio.sleep(period)
        tail = buffers.snapshot_tail(n=200)
        await hub.broadcast({"type": "stream", "data": tail})


def sanitize_name(s: str) -> str:
    # keep it simple & safe for folders/files
    s = s.strip()
    s = re.sub(r"[^A-Za-z0-9._\- ]+", "_", s)
    return s or "job"

# --- NEW: Recorder ---
class Recorder:
    """
    Consumes DAQ/RIG queues; writes to SQLite with start/pause/stop control.
    Tables:
      daq_samples(time REAL, value REAL, channel TEXT)
      rig_samples(time REAL, value REAL)
    """
    def __init__(self, daq_queue: "asyncio.Queue[tuple[float,float,str]]",
                       rig_queue: "asyncio.Queue[tuple[float,float]]"):
        self.daq_q = daq_queue
        self.rig_q = rig_queue
        self._conn: sqlite3.Connection | None = None
        self._task_daq: asyncio.Task | None = None
        self._task_rig: asyncio.Task | None = None
        self._recording = asyncio.Event()   # on/off gate for writing
        self.folder: Path | None = None
        self.db_path: Path | None = None
        self._stop_evt = asyncio.Event()

    def configured(self) -> bool:
        return self.db_path is not None

    def configure(self, location: str, job_name: str):
        loc = Path(location).expanduser().resolve()
        job = sanitize_name(job_name)
        folder = loc / job
        folder.mkdir(parents=True, exist_ok=True)
        db_path = folder / "job.sqlite"
        self.folder, self.db_path = folder, db_path
        # create db & schema
        self._open_db()
        self._init_schema()
        self._close_db()
        return {"folder": str(folder), "db": str(db_path), "job": job}

    async def start(self):
        if not self.configured():
            raise RuntimeError("Recorder not configured. Call configure_recording first.")
        if self._task_daq and not self._task_daq.done():
            # already running: just ensure recording is ON
            self._recording.set()
            return
        # open connection (exclusive to writer tasks)
        self._open_db()
        self._recording.set()
        self._stop_evt.clear()
        self._task_daq = asyncio.create_task(self._consume_daq())
        self._task_rig = asyncio.create_task(self._consume_rig())

    async def pause(self):
        self._recording.clear()

    async def stop(self):
        self._recording.clear()
        self._stop_evt.set()
        tasks = [t for t in (self._task_daq, self._task_rig) if t]
        if tasks:
            for t in tasks: t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._task_daq = self._task_rig = None
        self._close_db()

    # ---- internal helpers ----
    def _open_db(self):
        if self._conn: return
        assert self.db_path is not None
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA temp_store=MEMORY;")

    def _close_db(self):
        if self._conn:
            self._conn.commit()
            self._conn.close()
            self._conn = None

    def _init_schema(self):
        assert self._conn
        cur = self._conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS daq_samples(
                time REAL NOT NULL,
                value REAL NOT NULL,
                channel TEXT NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS rig_samples(
                time REAL NOT NULL,
                value REAL NOT NULL
            );
        """)
        # Optional indices for faster time range queries
        cur.execute("CREATE INDEX IF NOT EXISTS idx_daq_time ON daq_samples(time);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_rig_time ON rig_samples(time);")
        self._conn.commit()

    async def _consume_daq(self):
        assert self._conn
        cur = self._conn.cursor()
        batch: list[tuple[float,float,str]] = []
        last_flush = time.perf_counter()
        try:
            while not self._stop_evt.is_set():
                try:
                    item = await asyncio.wait_for(self.daq_q.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    item = None
                if item:
                    # item: (t, value, channel_name)
                    if self._recording.is_set():
                        batch.append(item)
                # flush periodically or when batch is big
                now = time.perf_counter()
                if batch and (now - last_flush > 0.5 or len(batch) >= 1000):
                    cur.executemany("INSERT INTO daq_samples(time,value,channel) VALUES (?,?,?);", batch)
                    self._conn.commit()
                    batch.clear()
                    last_flush = now
        finally:
            if batch:
                cur.executemany("INSERT INTO daq_samples(time,value,channel) VALUES (?,?,?);", batch)
                self._conn.commit()

    async def _consume_rig(self):
        assert self._conn
        cur = self._conn.cursor()
        batch: list[tuple[float,float]] = []
        last_flush = time.perf_counter()
        try:
            while not self._stop_evt.is_set():
                try:
                    item = await asyncio.wait_for(self.rig_q.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    item = None
                if item and self._recording.is_set():
                    batch.append(item)
                now = time.perf_counter()
                if batch and (now - last_flush > 1.0 or len(batch) >= 500):
                    cur.executemany("INSERT INTO rig_samples(time,value) VALUES (?,?);", batch)
                    self._conn.commit()
                    batch.clear()
                    last_flush = now
        finally:
            if batch:
                cur.executemany("INSERT INTO rig_samples(time,value) VALUES (?,?);", batch)
                self._conn.commit()



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
