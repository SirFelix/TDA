#!/usr/bin/env python3
"""
Unified DAQ + RIG server with Recorder (SQLite), WebSocket control, and broadcaster.

Usage:
  python daq_rig_server_complete.py

WebSocket command examples (JSON):
  {"cmd":"configure_daq", "device": null, "channels":["ai0"], "sample_rate_hz":30000}
  {"cmd":"start_daq"}
  {"cmd":"stop_daq"}

  {"cmd":"configure_rig", "port": "COM3", "baudrate": 115200}
  {"cmd":"start_rig"}
  {"cmd":"stop_rig"}

  {"cmd":"configure_recording", "job_name":"Job1", "location":"./data"}
  {"cmd":"start_recording"}
  {"cmd":"pause_recording"}
  {"cmd":"stop_recording"}

  {"cmd":"shutdown"}

Notes:
- DAQSession.auto device detection attempts several heuristics to find module name.
- RIG lines can be: JSON object with named fields, JSON array of 7 vals, or CSV of 7 vals.
"""

from __future__ import annotations
import asyncio
import json
import os
import re
import sqlite3
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import websockets
# DAQ
import nidaqmx
from nidaqmx.constants import CurrentUnits, CurrentShuntResistorLocation, AcquisitionType, READ_ALL_AVAILABLE
import nidaqmx.system
# Serial
import serial_asyncio
import inspect

# ---------------- Config ----------------
PORT_NUMBER = 9813
BROADCAST_HZ = 15
DAQ_READ_CHUNK = 100
WS_MAX_QUEUE = 3


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

# ---------------- Utilities ----------------
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

def sanitize_name(s: str) -> str:
    s = str(s).strip()
    s = re.sub(r"[^A-Za-z0-9._\- ]+", "_", s)
    return s or "job"

# ---------------- RingBuffers ----------------
@dataclass
class RingBuffers:
    # DAQ buffers
    raw_pressure: deque = field(default_factory=lambda: deque(maxlen=27000))
    raw_time: deque = field(default_factory=lambda: deque(maxlen=27000))
    filt_pressure: deque = field(default_factory=lambda: deque(maxlen=500))
    speed: deque = field(default_factory=lambda: deque(maxlen=500))

    # Rig signals (named) and shared rig time
    ctPressure: deque = field(default_factory=lambda: deque(maxlen=500))
    whPressure: deque = field(default_factory=lambda: deque(maxlen=500))
    ctDepth: deque     = field(default_factory=lambda: deque(maxlen=500))
    ctWeight: deque    = field(default_factory=lambda: deque(maxlen=500))
    ctSpeed: deque     = field(default_factory=lambda: deque(maxlen=500))
    ctFluidRate: deque = field(default_factory=lambda: deque(maxlen=500))
    n2FluidRate: deque = field(default_factory=lambda: deque(maxlen=500))
    rig_time: deque    = field(default_factory=lambda: deque(maxlen=500))

    def snapshot_tail(self, n: int = 200) -> Dict[str, List[float]]:
        def tail(dq: deque, k: int) -> List[float]:
            if k >= len(dq):
                return list(dq)
            return list(dq)[-k:]
        return {
            "rawPressure": tail(self.raw_pressure, n),
            "rawTime": tail(self.raw_time, n),
            "filterPressure": tail(self.filt_pressure, n),
            "tractorSpeed": tail(self.speed, n),
            "ctPressure": tail(self.ctPressure, n),
            "whPressure": tail(self.whPressure, n),
            "ctDepth": tail(self.ctDepth, n),
            "ctWeight": tail(self.ctWeight, n),
            "ctSpeed": tail(self.ctSpeed, n),
            "ctFluidRate": tail(self.ctFluidRate, n),
            "n2FluidRate": tail(self.n2FluidRate, n),
            "rigTime": tail(self.rig_time, n),
        }

# ---------------- Recorder (SQLite) ----------------
class Recorder:
    """
    Recorder that consumes queues and writes to SQLite.
    DAQ queue items: (time: float, value: float, channel: str)
    RIG queue items: (time: float, ctP, whP, ctD, ctW, ctS, ctFR, n2FR)
    """
    def __init__(self,
                 daq_queue: "asyncio.Queue[Tuple[float, float, str]]",
                 rig_queue: "asyncio.Queue[Tuple[float, float, float, float, float, float, float, float]]"):
        self.daq_q = daq_queue
        self.rig_q = rig_queue
        self._conn: Optional[sqlite3.Connection] = None
        self._task_daq: Optional[asyncio.Task] = None
        self._task_rig: Optional[asyncio.Task] = None
        self._recording = asyncio.Event()   # when set, writes are performed
        self.folder: Optional[Path] = None
        self.db_path: Optional[Path] = None
        self._stop_evt = asyncio.Event()

    def configured(self) -> bool:
        return self.db_path is not None

    def configure(self, location: str, job_name: str) -> Dict[str, str]:
        loc = Path(location).expanduser().resolve()
        job = sanitize_name(job_name)
        folder = loc / job
        folder.mkdir(parents=True, exist_ok=True)
        db_path = folder / "job.sqlite"
        self.folder, self.db_path = folder, db_path

        # create DB and schema now so client sees it right away
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA synchronous=NORMAL;")
            cur.execute("PRAGMA temp_store=MEMORY;")
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
                    ctPressure REAL,
                    whPressure REAL,
                    ctDepth REAL,
                    ctWeight REAL,
                    ctSpeed REAL,
                    ctFluidRate REAL,
                    n2FluidRate REAL
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_daq_time ON daq_samples(time);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rig_time ON rig_samples(time);")
            conn.commit()
        finally:
            conn.close()

        log(f"Recording configured: folder={folder}", "success")
        return {"folder": str(folder), "db": str(db_path), "job": job}

    async def start(self):
        if not self.configured():
            raise RuntimeError("Recorder not configured")
        if self._task_daq and not self._task_daq.done():
            # already running; just set recording flag
            self._recording.set()
            log("Recorder already running — resumed writing.", "info")
            return

        # open DB connection used by consumer tasks
        self._open_db()
        self._recording.set()
        self._stop_evt.clear()
        self._task_daq = asyncio.create_task(self._consume_daq())
        self._task_rig = asyncio.create_task(self._consume_rig())
        log("Recorder started.", "success")

    async def pause(self):
        self._recording.clear()
        log("Recorder paused.", "info")

    async def stop(self):
        self._recording.clear()
        self._stop_evt.set()
        tasks = [t for t in (self._task_daq, self._task_rig) if t]
        if tasks:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self._task_daq = self._task_rig = None
        self._close_db()
        log("Recorder stopped.", "success")

    def _open_db(self):
        if self._conn:
            return
        assert self.db_path is not None
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cur = self._conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA synchronous=NORMAL;")
        cur.execute("PRAGMA temp_store=MEMORY;")
        self._conn.commit()

    def _close_db(self):
        if self._conn:
            try:
                self._conn.commit()
            except Exception:
                pass
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def _consume_daq(self):
        assert self._conn is not None
        cur = self._conn.cursor()
        batch: List[Tuple[float, float, str]] = []
        last_flush = time.perf_counter()
        try:
            while not self._stop_evt.is_set():
                try:
                    item = await asyncio.wait_for(self.daq_q.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    item = None
                if item and self._recording.is_set():
                    # item: (t, value, channel)
                    batch.append(item)
                now = time.perf_counter()
                if batch and (now - last_flush > 0.5 or len(batch) >= 1000):
                    try:
                        cur.executemany("INSERT INTO daq_samples(time,value,channel) VALUES (?,?,?);", batch)
                        self._conn.commit()
                    except Exception as e:
                        log(f"Recorder DAQ write error: {e}", "error")
                    batch.clear()
                    last_flush = now
        finally:
            if batch:
                try:
                    cur.executemany("INSERT INTO daq_samples(time,value,channel) VALUES (?,?,?);", batch)
                    self._conn.commit()
                except Exception as e:
                    log(f"Recorder final DAQ write error: {e}", "error")

    async def _consume_rig(self):
        assert self._conn is not None
        cur = self._conn.cursor()
        batch: List[Tuple[float, float, float, float, float, float, float, float]] = []
        last_flush = time.perf_counter()
        try:
            while not self._stop_evt.is_set():
                try:
                    item = await asyncio.wait_for(self.rig_q.get(), timeout=0.25)
                except asyncio.TimeoutError:
                    item = None
                if item and self._recording.is_set():
                    # item is full 8-tuple
                    batch.append(item)
                now = time.perf_counter()
                if batch and (now - last_flush > 1.0 or len(batch) >= 500):
                    try:
                        cur.executemany(
                            "INSERT INTO rig_samples(time,ctPressure,whPressure,ctDepth,ctWeight,ctSpeed,ctFluidRate,n2FluidRate) VALUES (?,?,?,?,?,?,?,?);",
                            batch,
                        )
                        self._conn.commit()
                    except Exception as e:
                        log(f"Recorder RIG write error: {e}", "error")
                    batch.clear()
                    last_flush = now
        finally:
            if batch:
                try:
                    cur.executemany(
                        "INSERT INTO rig_samples(time,ctPressure,whPressure,ctDepth,ctWeight,ctSpeed,ctFluidRate,n2FluidRate) VALUES (?,?,?,?,?,?,?,?);",
                        batch,
                    )
                    self._conn.commit()
                except Exception as e:
                    log(f"Recorder final RIG write error: {e}", "error")

# ---------------- DAQ Session ----------------
@dataclass
class DAQConfig:
    device: Optional[str] = None         # None => auto-discover
    channels: List[str] = field(default_factory=lambda: ["ai0"])
    sample_rate_hz: float = 20.0

class DAQSession:
    def __init__(self, buffers: RingBuffers, out_queue: "asyncio.Queue[Tuple[float, float, str]]"):
        self.cfg = DAQConfig()
        self.buffers = buffers
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()
        self._daq_out_q = out_queue

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
            try:
                if not dev.product_type.startswith("cDAQ"):
                    return dev.name
            except Exception:
                continue
        # Fallback: try chassis.modules
        ch = system.devices[0]
        try:
            if hasattr(ch, "modules") and ch.modules:
                return ch.modules[0].name
        except Exception:
            pass
        return ch.name

    async def _run(self):
        device = self.cfg.device or self._auto_device()
        chan_list = [f"{device}/{ch}" for ch in self.cfg.channels]
        sr = self.cfg.sample_rate_hz

        try:
            with nidaqmx.Task() as task:
                for ch in chan_list:
                    task.ai_channels.add_ai_voltage_chan(ch)
                task.timing.cfg_samp_clk_timing(rate=sr, sample_mode=nidaqmx.constants.AcquisitionType.CONTINUOUS)

                # Warm-up
                try:
                    _ = task.read(number_of_samples_per_channel=DAQ_READ_CHUNK, timeout=10.0)
                except Exception:
                    pass

                t = 0.0
                dt = 1.0 / sr

                while self._running.is_set():
                    # Read a small chunk
                    try:
                        data = task.read(number_of_samples_per_channel=DAQ_READ_CHUNK, timeout=2.0)
                    except Exception as e:
                        # on read error, yield and continue or break depending on design
                        log(f"DAQ read error: {e}", "error")
                        await asyncio.sleep(0.1)
                        continue

                    # Normalize to channel 0 data
                    ch0 = None
                    if isinstance(data, list) and data and isinstance(data[0], list):
                        ch0 = data[0]
                    else:
                        ch0 = data

                    for v in ch0:
                        now = time.time()
                        self.buffers.raw_pressure.append(float(v))
                        self.buffers.raw_time.append(now)
                        # simple placeholder filter / derived
                        self.buffers.filt_pressure.append(float(v))
                        self.buffers.speed.append(0.0)

                        # enqueue to recorder (best-effort)
                        try:
                            # record with wall-clock timestamp and channel name (first channel)
                            chan_name = chan_list[0]
                            self._daq_out_q.put_nowait((now, float(v), chan_name))
                        except asyncio.QueueFull:
                            # drop if recorder queue is full
                            pass

                    # yield control
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            # graceful exit
            return
        except Exception as e:
            log(f"DAQ session error: {e}", "error")

# ---------------- RIG Session ----------------
@dataclass
class RigConfig:
    port: Optional[str] = None
    baudrate: int = 57600

class RigSession:
    def __init__(self, buffers: RingBuffers, out_queue: "asyncio.Queue[Tuple]"):
        self.cfg = RigConfig()
        self.buffers = buffers
        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()
        self._rig_out_q = out_queue

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
        # open serial connection
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=self.cfg.port, baudrate=self.cfg.baudrate
            )
        except Exception as e:
            log(f"RIG serial open error: {e}", "error")
            return

        try:
            while self._running.is_set():
                try:
                    line = await reader.readline()
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(0.01)
                    continue

                if not line:
                    await asyncio.sleep(0)
                    continue
                text = line.decode("utf-8", "ignore").strip()
                if not text:
                    continue

                parsed = None
                try:
                    parsed = json.loads(text)
                except Exception:
                    parsed = None

                values = None
                # JSON object with named fields
                if isinstance(parsed, dict):
                    try:
                        values = (
                            float(parsed.get("ctPressure", 0.0)),
                            float(parsed.get("whPressure", 0.0)),
                            float(parsed.get("ctDepth", 0.0)),
                            float(parsed.get("ctWeight", 0.0)),
                            float(parsed.get("ctSpeed", 0.0)),
                            float(parsed.get("ctFluidRate", 0.0)),
                            float(parsed.get("n2FluidRate", 0.0)),
                        )
                    except Exception:
                        values = None
                # JSON array
                elif isinstance(parsed, list) and len(parsed) >= 7:
                    try:
                        values = tuple(float(parsed[i]) for i in range(7))
                    except Exception:
                        values = None
                # CSV fallback
                if values is None:
                    parts = [p.strip() for p in text.split(",") if p.strip() != ""]
                    if len(parts) >= 7:
                        try:
                            values = tuple(float(parts[i]) for i in range(7))
                        except Exception:
                            values = None

                if values is None:
                    # couldn't parse => skip
                    continue

                now = time.time()
                ctP, whP, ctD, ctW, ctS, ctFR, n2FR = values

                # append to ring buffers
                self.buffers.ctPressure.append(ctP)
                self.buffers.whPressure.append(whP)
                self.buffers.ctDepth.append(ctD)
                self.buffers.ctWeight.append(ctW)
                self.buffers.ctSpeed.append(ctS)
                self.buffers.ctFluidRate.append(ctFR)
                self.buffers.n2FluidRate.append(n2FR)
                self.buffers.rig_time.append(now)

                # enqueue to recorder (non-blocking)
                try:
                    self._rig_out_q.put_nowait((now, ctP, whP, ctD, ctW, ctS, ctFR, n2FR))
                except asyncio.QueueFull:
                    pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

# ---------------- Hub & Broadcaster ----------------
class Hub:
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
        send_tasks = []
        for ws in list(self.clients):
            try:
                send_tasks.append(asyncio.create_task(ws.send(payload)))
            except Exception:
                await self.unregister(ws)
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)

async def broadcaster(hub: Hub, buffers: RingBuffers):
    period = 1.0 / BROADCAST_HZ
    SNAP_TAIL = 50
    while True:
        await asyncio.sleep(period)
        if not hub.clients:
            continue
        tail = buffers.snapshot_tail(n=SNAP_TAIL)
        log(f"stream: {tail}", "data")
        await hub.broadcast({"type": "stream", "data": tail})

def verbose_log(data):
    log("======================", "info")
    log(f"[WS RX] Raw JSON: {data}", "data")   # raw string
    log(f"[WS RX] Parsed dict: {json.dumps(data, indent=2)}", "log")  # pretty print parsed dict
    log("======================", "info")


# ---------------- Websocket Handler ----------------
async def ws_handler(ws, path, daq: DAQSession, rig: RigSession, hub: Hub, recorder: Recorder, shutdown_evt: asyncio.Event):
    await hub.register(ws)
    log("Client connected.", "success")
    try:        
        async for raw in ws:
            try:
                msg = json.loads(raw)
                if VERBOSE:
                    verbose_log(msg)
            except Exception:
                await ws.send(safe_json({"ok": False, "error": "invalid_json"}))
                continue

            cmd = msg.get("cmd")
            try:
                # DAQ control
                if cmd == "configure_daq":
                    kwargs = {k: v for k, v in msg.items() if k != "cmd"}
                    daq.configure(**kwargs)
                    await ws.send(safe_json({"ok": True, "configured": True}))
                elif cmd == "start_daq":
                    await daq.start()
                    await ws.send(safe_json({"ok": True, "daq_running": True}))
                elif cmd == "stop_daq":
                    await daq.stop()
                    await ws.send(safe_json({"ok": True, "daq_running": False}))

                # RIG control
                elif cmd == "configure_rig":
                    kwargs = {k: v for k, v in msg.items() if k != "cmd"}
                    rig.configure(**kwargs)
                    await ws.send(safe_json({"ok": True, "configured": True}))
                elif cmd == "start_rig":
                    await rig.start()
                    await ws.send(safe_json({"ok": True, "rig_running": True}))
                elif cmd == "stop_rig":
                    await rig.stop()
                    await ws.send(safe_json({"ok": True, "rig_running": False}))

                # Recorder control
                elif cmd == "configure_recording":
                    job_name = msg.get("job_name")
                    location = msg.get("location")
                    if not job_name or not location:
                        await ws.send(safe_json({"ok": False, "error": "missing job_name/location"}))
                    else:
                        info = recorder.configure(location=location, job_name=job_name)
                        await ws.send(safe_json({"ok": True, "recording_config": info, "recording": False}))
                elif cmd == "start_recording":
                    await recorder.start()
                    await ws.send(safe_json({"ok": True, "recording": True, "folder": str(recorder.folder), "db": str(recorder.db_path)}))
                elif cmd == "pause_recording":
                    await recorder.pause()
                    await ws.send(safe_json({"ok": True, "recording": False}))
                elif cmd == "stop_recording":
                    await recorder.stop()
                    await ws.send(safe_json({"ok": True, "recording": False}))

                # Shutdown
                elif cmd == "shutdown":
                    await ws.send(safe_json({"ok": True}))
                    shutdown_evt.set()
                else:
                    await ws.send(safe_json({"ok": False, "error": "unknown_command"}))
            except Exception as e:
                log(f"Command {cmd} error: {e}", "error")
                await ws.send(safe_json({"ok": False, "error": str(e)}))
    finally:
        await hub.unregister(ws)
        log("Client disconnected.", "warn")

# ---------------- Main ----------------
async def main():
    buffers = RingBuffers()

    # recorder queues (bounded)
    daq_queue: asyncio.Queue = asyncio.Queue(maxsize=50_000)      # larger for DAQ high rate
    rig_queue: asyncio.Queue = asyncio.Queue(maxsize=10_000)

    daq = DAQSession(buffers, daq_queue)
    rig = RigSession(buffers, rig_queue)
    recorder = Recorder(daq_queue, rig_queue)
    hub = Hub()
    shutdown_evt = asyncio.Event()

    async def handler(ws, path):
        return await ws_handler(ws, path, daq, rig, hub, recorder, shutdown_evt)

    ws_server = await websockets.serve(handler, "localhost", PORT_NUMBER)
    log(f"[ WS ] WebSocket server listening on :{PORT_NUMBER}", "success")

    tasks = [
        asyncio.create_task(broadcaster(hub, buffers)),
    ]

    try:
        # stay alive until shutdown command arrives
        await shutdown_evt.wait()
    finally:
        log("Shutting down…", "warn")
        ws_server.close()
        await ws_server.wait_closed()

        # stop subsystems
        await daq.stop()
        await rig.stop()
        await recorder.stop()

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        log("Shutdown complete.", "success")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("KeyboardInterrupt — exiting.", "warn")