### daq_sampling_websocket.py
# This is to replace the serial_output_web_socket.py program. It's update is limited
# and this program is made to fix that.

import asyncio, json, time, datetime
from typing import Any, Callable, Dict, Optional, Iterable, Tuple, List
import nidaqmx
from nidaqmx.constants import CurrentUnits, CurrentShuntResistorLocation, AcquisitionType, READ_ALL_AVAILABLE
import websockets
import websockets.exceptions
import inspect # Used to get the line number

## Not used
# import signal
# import numpy as np


#--------------- Configuration ----------------
PHYSICAL_CHAN = "cDAQ9181-2185DAEMod1/ai0"
DAQ_SAMPLE_RATE = 4  #Hz
TX_RATE = 4        #Hz
port_number = 9813

clients = set()

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

shared_data = {
    "daq_timestamp": None,
    "daq_rawCurrent": None,
    "daq_rawPressure": None,
    "daq_filteredPressure": None,
    "daq_tractorSpeed": None,
    "daq_channel": PHYSICAL_CHAN,
    "daq_port": port_number,
    "sample_rate": DAQ_SAMPLE_RATE,
    "tx_rate": TX_RATE
}


varSpec = Dict[str, Any]
SourceSpec = Dict[str, Any]

REGISTRY: Dict[str, SourceSpec] = {
    "DAQ": {
        "timestamp": "daq_timestamp",
        "vars": {
            "raw_pressure":         {"key": "daq_rawPressure",      "transform": float, "default": None},
            "filtered_pressure":    {"key": "daq_filteredPressure", "transform": float, "default": None},
            "tractor_speed":        {"key": "daq_tractorSpeed",     "transform": float, "default": None},
        },
    },
    "RIG": {
        "timestamp": "rig_timestamp",
        "vars": {
            "ctPressure":   {"key": "rig_ctPressure",   "transform": float, "default": None},
            "whPressure":   {"key": "rig_whPressure",   "transform": float, "default": None},
            "ctDepth":      {"key": "rig_ctDepth",      "transform": float, "default": None},
            "ctWeight":     {"key": "rig_ctWeight",     "transform": float, "default": None},
            "ctSpeed":      {"key": "rig_ctSpeed",      "transform": float, "default": None},
            "ctFluidRate":  {"key": "rig_ctFluidRate",  "transform": float, "default": None},
            "n2FluidRate":  {"key": "rig_n2FluidRate",  "transform": float, "default": None},
        },
    },
}

class DAQSession:
    def __init__(self):
        self.sample_rate = DAQ_SAMPLE_RATE
        self.tx_rate = TX_RATE
        self.terminate = False
        self.active = False

    def stop(self):
        self.active = False

    def start(self):
        self.active = True

    def terminate(self):
        self.terminate = True

    def update_sample_rate(self, rate):
        self.sample_rate = rate

    def update_tx_rate(self, rate):
        self.tx_rate = rate




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

def map_range(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min

raw_to_psi = lambda x: map_range(x, 0.004, 0.020, 0, 15000)





async def sample_daq(session: DAQSession, shared_data: dict): # Added async to turn sample_daq function into an async function
    log(f"[ DAQ ] DAQ started.", "success")
    while not session.terminate: # Check if the DAQ session was terminated
        if session.active:       # Check if the DAQ session is active (DAQstart was called)
            with nidaqmx.Task() as task:

                #Channel configuration of DAQ
                task.ai_channels.add_ai_current_chan(
                    physical_channel=PHYSICAL_CHAN,
                    min_val=0.004, max_val=0.020,
                    units=CurrentUnits.AMPS,
                    shunt_resistor_loc=CurrentShuntResistorLocation.INTERNAL
                )

                
                #Sampling configuration
                task.timing.cfg_samp_clk_timing(
                    rate=session.sample_rate,
                    sample_mode=AcquisitionType.CONTINUOUS,
                    samps_per_chan=1
                )


                log(f"Sampling at {session.sample_rate} Hz. Press Ctrl+C to stop.", "success")

                task.start() # Start the DAQ task explicity Before first read (required when using READ_ALL_AVAILABLE)

                # session.start()

                try:
                    while session.active:
                        # # Takes all the samples stored in value and retrieves only the latest sample to log
                        # # Note: that this tops out at ~64Hz before the DAQ buffer starts growing
                        # # Alternative: value = task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE)[-1]
                        value = task.read(number_of_samples_per_channel=READ_ALL_AVAILABLE) # This grabs everything currently in the buffer and optionally discards the rest. Stops buffer overflow condition
                        timestamp = round(time.time(), 6)

                        if value:   # Checks if the buffer is empty
                            for i, sample in enumerate(value):
                                continue
                                log(f"{timestamp + i / session.sample_rate:.3f}: {sample:.9f} A", "data")

                            if len(value) > 1:

                                  # For sending multiple samples at once
                                  #-----------------------------------------
                                # # Back calculates even time intervals of the samples in the buffer
                                # base_time = timestamp - (len(value) - 1) / session.sample_rate
                                # timestamps = [base_time + i / session.sample_rate for i in range(len(value))]

                                # log(f"{len(value)} samples in buffer. making an array of samples.", "warn")
                                # shared_data["daq_rawCurrent"] = value
                                # shared_data["daq_timestamp"] = timestamps
                                  #-----------------------------------------


                                # For sending only the latest sample
                                shared_data["daq_rawCurrent"] = value[-1]
                                shared_data["daq_rawPressure"] = raw_to_psi(value[-1])
                            else:
                                # log("One sample in buffer.", "info")
                                shared_data["daq_rawCurrent"] = value
                                shared_data["daq_rawPressure"] = raw_to_psi(value[-1])

                                # log(f"{timestamp}: {shared_data['daq_rawPressure']:.2f} PSI", "data")
                            
                            shared_data["daq_timestamp"] = timestamp
                        else:
                            continue
                            

                        await asyncio.sleep(1.0 / (session.sample_rate * 1.1)) # Not needed the sample rate is defined

                except asyncio.CancelledError:
                    log("[CancelledError] Sampling task was cancelled.", "info")
                except KeyboardInterrupt:
                    log("\n[KeyboardInterrupt] Sampling stopped.", "info")
                finally:
                    session.stop()

        # Checks if the session is active every 0.1 seconds
        else:
            # log(f"[ DS ] Sampling task is inactive.", "info")
            await asyncio.sleep(0.1)
    log(f"[ DS ] Sampling task was terminated.", "info")
    await asyncio.sleep(0.1)



### OLD CODE Broadcast DAQ data to clients indiscriminately and independently of the sampling task
# async def broadcast_data(session: DAQSession, shared_data):
#     last_sent_timestamp = None
#     try:
#         while True:
#             current_timestamp = shared_data["daq_timestamp"]
#             if shared_data["daq_rawCurrent"] is not None and current_timestamp != last_sent_timestamp:

#                 payload = {
#                     "source": "DAQ",
#                     "type": "data",
#                     "params": {
#                         # "timestamp": shared_data["daq_timestamp"][-1] if shared_data["daq_timestamp"] else None,
#                         "timestamp": shared_data["daq_timestamp"] if shared_data["daq_timestamp"] else None,
#                         "raw_pressure": shared_data["daq_rawPressure"] if shared_data["daq_rawPressure"] else None,
#                         "filtered_pressure": 4,
#                         "tractor_speed": 15.2,
#                     }
#                 }

#                 message = json.dumps(payload)
#                 log(f"[ TX ] {message}", "data")

#                 # Build a list of tasks
#                 send_tasks = []
#                 for client in list(clients):
#                     send_tasks.append(
#                         asyncio.create_task(send_with_timeout(client, message))
#                     )

#                 await asyncio.gather(*send_tasks)
#                 # log(f"[ TX ] Client removed. {len(clients)} clients remain.", "warn")


#                 # log(f"[ TX ] Sent {len(shared_data['daq_rawCurrent'])} samples.", "success")
#                 last_sent_timestamp = current_timestamp

#             await asyncio.sleep(1.0 / (shared_data["tx_rate"] * 1.15))

#     except Exception as e:
#         log(f"[ TX ] Exception: {e}", "error")


#### NEW CODE Receives input from multiple sources and sends data to clients
async def broadcast_data(session: DAQSession, shared_data):
    last_sent_timestamp = None
    try:
        while True:
            current_timestamp = shared_data["daq_timestamp"]
            if shared_data["daq_rawCurrent"] is not None and current_timestamp != last_sent_timestamp:

                payload = {
                    "source": "DAQ",
                    "type": "data",
                    "params": {
                        # "timestamp": shared_data["daq_timestamp"][-1] if shared_data["daq_timestamp"] else None,
                        "timestamp": shared_data["daq_timestamp"] if shared_data["daq_timestamp"] else None,
                        "raw_pressure": shared_data["daq_rawPressure"] if shared_data["daq_rawPressure"] else None,
                        "filtered_pressure": 4,
                        "tractor_speed": 15.2,
                    }
                }

                message = json.dumps(payload)
                # log(f"[ TX ] {message}", "data")

                # Build a list of tasks
                send_tasks = []
                for client in list(clients):
                    send_tasks.append(
                        asyncio.create_task(send_with_timeout(client, message))
                    )

                await asyncio.gather(*send_tasks)
                # log(f"[ TX ] Client removed. {len(clients)} clients remain.", "warn")


                # log(f"[ TX ] Sent {len(shared_data['daq_rawCurrent'])} samples.", "success")
                last_sent_timestamp = current_timestamp

            await asyncio.sleep(1.0 / (shared_data["tx_rate"] * 1.15))

    except Exception as e:
        log(f"[ TX ] Exception: {e}", "error")


# --- Helper function to protect each send call ---
async def send_with_timeout(client, message, timeout=1.0):
    try:
        await asyncio.wait_for(client.send(message), timeout=timeout)
    except asyncio.TimeoutError:
        log(f"[ TX ] Timeout sending to client {client.remote_address}", "error")
        clients.discard(client)
    except websockets.exceptions.ConnectionClosed:
        log(f"[ TX ] Client {client.remote_address} disconnected.", "error")
        clients.discard(client)
    except Exception as e:
        log(f"[ TX ] Error sending to client {client.remote_address}: {e}", "error")
        clients.discard(client)





async def ws_handler(websocket, session: DAQSession, shared_data: dict):
    clients.add(websocket)
    log(f"[ WS ] {len(clients)} clients connected. Connected to {websocket.remote_address}", "header")
    await websocket.send( json.dumps({"type": "acknowledgement","state": "NewConnection",}))
    session.terminate = False

    try:
        async for message in websocket:
            log(f"[ WS ] Received: {message}", "data")
            data = json.loads(message)
            
            if data.get("type") == "command":
                params = data.get("params", {})
                action = params.get("action")
                sample_rate = params.get("sample_rate")
                tx_rate = params.get("tx_rate")

                if action == "DAQstop":
                    session.stop()
                    log("[ Command ] DAQ stopped.", "success")
                    await websocket.send( json.dumps({"type": "acknowledgement","state": "DAQstopped",}))

                elif action == "DAQstart":
                    session.start()
                    log("[ Command ] DAQ started.", "success")
                    await websocket.send( json.dumps({"type": "acknowledgement","state": "DAQstarted",}))
                
                elif action == "WSdisconnect":
                    session.stop()
                    session.terminate = True
                    log("[ Command ] WS disconnected.", "success")
                    await websocket.send( json.dumps({"type": "acknowledgement","state": "WSterminated",}))

                elif action == "DAQconnect":
                    # session.start()
                    session.terminate = False
                    log("[ Command ] DAQ reconnected.", "success")
                    await websocket.send( json.dumps({"type": "acknowledgement","state": "DAQreconnected",}))

                if sample_rate:
                    session.update_sample_rate(sample_rate)
                    shared_data["sample_rate"] = sample_rate

                if tx_rate:
                    session.update_tx_rate(tx_rate)
                    shared_data["tx_rate"] = tx_rate
    
    except websockets.exceptions.ConnectionClosed:
        log("Client disconnected.", "error")
    finally:
        clients.remove(websocket)



#Need to add this function for the asynchronous sleep call
async def main():
    session = DAQSession()
    # await sample_daq(session)

    shared_data = {
        "daq_rawCurrent": None,
        "daq_timestamp": None,
        "tx_rate": session.tx_rate
    }

    ws_server = await websockets.serve(
        lambda ws,
        path: ws_handler(ws, session, shared_data),
        "localhost",
        port_number
    )      #start the websocket server

    log(f"[ WS ] Websocket server started on port {port_number}", "success")
    await asyncio.gather(

        sample_daq(session, shared_data),       #run DAQ reading function
        broadcast_data(session, shared_data),            #send data to clients
    )
    
#----------




if __name__ == "__main__":
    try:
        asyncio.run(main()) # Wrap the regular main() with asyncio.run() to create a co-routine 
    except KeyboardInterrupt:
        log("[Exit] KeyboardInterrupt received. Exiting cleanly.", "success")