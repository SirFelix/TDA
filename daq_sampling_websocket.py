#!/usr/bin/env python3
"""
daq_sampling_websocket.py

Simplified event-driven DAQ sampling + one-shot WebSocket broadcaster.

This version includes:
- One-shot broadcast of DAQ device name and sample rate on WS connection.
- DAQ `period_points` variable tied to filtered pressure.
"""

import asyncio
import json
import time
import inspect
from typing import Any, Dict, Optional, Iterable, Tuple

import nidaqmx
import nidaqmx.system
from nidaqmx.constants import CurrentUnits, CurrentShuntResistorLocation, AcquisitionType, READ_ALL_AVAILABLE
import websockets
import websockets.exceptions

# ---------- Configuration ----------
PHYSICAL_CHAN = "cDAQ9181-2185DAEMod1/ai0"
DAQ_SAMPLE_RATE = 30  # Hz
TX_RATE = 10          # not used by one-shot but kept
PORT_NUMBER = 9813

clients = set()
VERBOSE = True

# ---------- Logging helper ----------
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BLUE = "\033[94m"
COLOR_ORANGE = "\033[38;5;172m"
COLOR_GRAY = "\033[90m"

def log(message: str, level: str = "info") -> None:
    if not VERBOSE:
        return
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

# ---------- Range mapping / conversion ----------
def map_range(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

raw_to_psi = lambda x: map_range(x, 0.004, 0.020, 0, 15000)

# ---------- Simple central DB ----------
_db: Dict[str, Dict[str, Any]] = {
    "DAQ": {"channel": PHYSICAL_CHAN, "port": PORT_NUMBER, "sample_rate": DAQ_SAMPLE_RATE, "tx_rate": TX_RATE},
    "RIG": {},
}
_db_lock = asyncio.Lock()

async def db_set(source: str, key: str, value: Any) -> None:
    async with _db_lock:
        src = _db.setdefault(source, {})
        src[key] = value

async def db_set_many(source: str, mapping: Dict[str, Any]) -> None:
    async with _db_lock:
        src = _db.setdefault(source, {})
        src.update(mapping)

def db_get(source: str, key: str, default: Any = None) -> Any:
    return _db.get(source, {}).get(key, default)

def db_get_all(source: str) -> Dict[str, Any]:
    return dict(_db.get(source, {}))

# ---------- Registry mapping JSON names -> DB keys/transforms ----------
REGISTRY: Dict[str, Dict[str, Any]] = {
    "DAQ": {
        "timestamp": "timestamp",
        "vars": {
            "raw_pressure":      {"key": "rawPressure",     "transform": float, "default": None},
            "filtered_pressure": {"key": "filteredPressure","transform": float, "default": -1.0},
            "tractor_speed":     {"key": "tractorSpeed",    "transform": float, "default": None},
            "period_points":     {"key": "periodPoints",    "transform": float, "default": None},
            "device_name":       {"key": "device_name",     "transform": str,   "default": None},
            "sample_rate":       {"key": "sample_rate",     "transform": float, "default": DAQ_SAMPLE_RATE},
        },
    },
    "RIG": {
        "timestamp": "timestamp",
        "vars": {
            "ctPressure":   {"key": "ctPressure",    "transform": float, "default": None},
            "whPressure":   {"key": "whPressure",    "transform": float, "default": None},
            "ctDepth":      {"key": "ctDepth",       "transform": float, "default": None},
            "ctWeight":     {"key": "ctWeight",      "transform": float, "default": None},
            "ctSpeed":      {"key": "ctSpeed",       "transform": float, "default": None},
            "ctFluidRate":  {"key": "ctFluidRate",   "transform": float, "default": None},
            "n2FluidRate":  {"key": "n2FluidRate",   "transform": float, "default": None},
        },
    },
}

_last_sent_ts: Dict[Tuple[str, str], Any] = {}

def get_device_name():
    system = nidaqmx.system.System.local()

    if not system.devices:
        raise RuntimeError("No NI devices found.")

    for device in system.devices:
        # If this is a module (not a chassis). 
        # DAQ field boxes only use modules
        if not device.product_type.startswith("cDAQ"):
            return f"{device.name}/ai0"

        # If it's a chassis, try to get its first module
        try:
            if device.modules:
                return f"{device.modules[0].name}/ai0"
        except AttributeError:
            pass

    raise RuntimeError("No module with channels found.")

# ---------- WebSocket send helper ----------
async def send_with_timeout(client, message: str, timeout: float = 1.0):
    try:
        await asyncio.wait_for(client.send(message), timeout=timeout)
    except asyncio.TimeoutError:
        log(f"[ TX ] Timeout sending to client {getattr(client, 'remote_address', client)}", "error")
        clients.discard(client)
    except websockets.exceptions.ConnectionClosed:
        log(f"[ TX ] Client {getattr(client, 'remote_address', client)} disconnected.", "error")
        clients.discard(client)
    except Exception as e:
        log(f"[ TX ] Error sending to client {getattr(client, 'remote_address', client)}: {e}", "error")
        clients.discard(client)

# ---------- One-shot broadcaster ----------
async def broadcast_data_one_shot(*, source: str, params: Iterable[str], msg_type: str = "data", per_call_defaults: Optional[Dict[str, Any]] = None, force: bool = False) -> None:
    
    spec = REGISTRY.get(source)
    if not spec:
        log(f"[ TX ] Unknown source '{source}'", "warn")
        return

    ts_key = spec["timestamp"]
    ts_val = db_get(source, ts_key)
    if ts_val is None:
        ts_val = time.time()

    if not force and _last_sent_ts.get((source, msg_type)) == ts_val:
        return

    params_map: Dict[str, Any] = {"timestamp": float(ts_val)}
    for name in params:
        var_spec = spec["vars"].get(name)
        if not var_spec:
            continue
        db_key = var_spec["key"]
        transform = var_spec.get("transform")
        default = (per_call_defaults or {}).get(name, var_spec.get("default"))
        raw_value = db_get(source, db_key, None)
        if raw_value is None:
            if default is not None:
                params_map[name] = default
            continue
        try:
            params_map[name] = transform(raw_value) if transform else raw_value
        except Exception:
            if default is not None:
                params_map[name] = default

    payload = {"source": source, "type": msg_type, "params": params_map}
    message = json.dumps(payload, separators=(",", ":"))

    send_tasks = [asyncio.create_task(send_with_timeout(c, message)) for c in list(clients)]
    if send_tasks:
        await asyncio.gather(*send_tasks)

    _last_sent_ts[(source, msg_type)] = ts_val
    log(f"[ TX ] {message}", "data")

# ---------- DAQ session helper ----------
class DAQSession:
    def __init__(self):
        self.sample_rate = DAQ_SAMPLE_RATE
        self.tx_rate = TX_RATE
        self.terminate = False
        self.active = False
    def stop(self): self.active = False
    def start(self): self.active = True
    def terminate_session(self): self.terminate = True
    def update_sample_rate(self, rate): self.sample_rate = rate
    def update_tx_rate(self, rate): self.tx_rate = rate

# ---------- DAQ sampling ----------
async def sample_daq(session: DAQSession):
    log(f"[ DAQ ] DAQ started.", "success")

    # Store device name and initial sample rate once
    device_name = get_device_name()
    await db_set("DAQ", "device_name", device_name)
    await db_set("DAQ", "sample_rate", session.sample_rate)
    await broadcast_data_one_shot(source="DAQ", params=["device_name", "sample_rate"], force=True)

    while not session.terminate:
        if not session.active:
            await asyncio.sleep(0.1)
            continue

        try:
            with nidaqmx.Task() as task:
                task.ai_channels.add_ai_current_chan(
                    physical_channel=PHYSICAL_CHAN,
                    min_val=0.004, max_val=0.020,
                    units=CurrentUnits.AMPS,
                    shunt_resistor_loc=CurrentShuntResistorLocation.INTERNAL
                )
                task.timing.cfg_samp_clk_timing(
                    rate=session.sample_rate,
                    sample_mode=AcquisitionType.CONTINUOUS,
                    samps_per_chan=1
                )
                task.start()
                log(f"Sampling at {session.sample_rate} Hz.", "success")

                while session.active:
                    value = task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)
                    timestamp = round(time.time(), 6)
                    sample = value[-1] if isinstance(value, (list, tuple)) else value

                    raw_current = float(sample)
                    raw_pressure = raw_to_psi(raw_current)

                    # Example: filtered pressure and period_points calculation
                    filtered_pressure = raw_pressure  # replace with actual filter logic
                    period_points = filtered_pressure / 1000  # placeholder example logic

                    await db_set_many("DAQ", {
                        "rawCurrent": raw_current,
                        "rawPressure": raw_pressure,
                        "filteredPressure": filtered_pressure,
                        "periodPoints": period_points,
                        "timestamp": timestamp,
                    })

                    await broadcast_data_one_shot(
                        source="DAQ",
                        params=["raw_pressure", "filtered_pressure", "tractor_speed", "period_points"]
                    )

                    await asyncio.sleep(1.0 / (session.sample_rate * 1.05))

        except asyncio.CancelledError:
            log("[CancelledError] Sampling task cancelled.", "info")
            break
        except Exception as e:
            log(f"[ DAQ ] Sampling loop exception: {e}", "error")
            await asyncio.sleep(0.5)

    log(f"[ DAQ ] Sampling task terminated.", "info")

# ---------- WebSocket handler ----------
async def ws_handler(websocket, path, session: DAQSession):
    clients.add(websocket)
    log(f"[ WS ] {len(clients)} clients connected.", "header")
    try:
        await websocket.send(json.dumps({"type": "acknowledgement", "state": "NewConnection"}))
    except Exception:
        pass

    try:
        async for message in websocket:
            try:
                data = json.loads(message)
            except Exception:
                continue

            if data.get("type") == "command":
                params = data.get("params", {})
                action = params.get("action")
                sample_rate = params.get("sample_rate")
                tx_rate = params.get("tx_rate")

                if action == "DAQstop":
                    session.stop()
                    log("[ Command ] DAQ stopped.", "success")
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": "DAQstopped"}))
                elif action == "DAQstart":
                    session.start()
                    log("[ Command ] DAQ started.", "success")
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": "DAQstarted"}))
                elif action == "DAQdisconnect":
                    session.stop()
                    session.terminate = True
                    log("[ Command ] DAQ disconnected.", "success")
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": "DAQterminated"}))
                elif action == "DAQconnect":
                    session.terminate = False
                    log("[ Command ] DAQ reconnected.", "success")
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": "DAQreconnected"}))

                if sample_rate:
                    session.update_sample_rate(float(sample_rate))
                    await db_set("DAQ", "sample_rate", float(sample_rate))
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": f"sample_rate_set:{sample_rate}"}))
                if tx_rate:
                    session.update_tx_rate(float(tx_rate))
                    await db_set("DAQ", "tx_rate", float(tx_rate))
                    await websocket.send(json.dumps({"type": "acknowledgement", "state": f"tx_rate_set:{tx_rate}"}))

    except websockets.exceptions.ConnectionClosed:
        log("[ WS ] Client disconnected.", "warn")
    finally:
        clients.discard(websocket)
        log(f"[ WS ] client removed. {len(clients)} clients remain.", "debug")

# ---------- Main ----------
async def main():
    session = DAQSession()

    async def handler(ws, path):
        await ws_handler(ws, path, session)

    ws_server = await websockets.serve(handler, "0.0.0.0", PORT_NUMBER)
    log(f"[ WS ] Websocket server started on port {PORT_NUMBER}", "success")

    try:
        await asyncio.gather(
            sample_daq(session),
        )
    finally:
        ws_server.close()
        await ws_server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("[Exit] KeyboardInterrupt received. Exiting cleanly.", "success")
