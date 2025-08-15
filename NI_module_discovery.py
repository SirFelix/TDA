import nidaqmx
import nidaqmx.system



module_name = None

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

if __name__ == "__main__":
    niDevice = get_device_name()
    print(f"Discovered device: {niDevice}")










# #---------------------------------------------------------------------------
# # Obtains the name of the module, displays and prints out first channel data
# import nidaqmx
# import nidaqmx.system
# system = nidaqmx.system.System.local()
# for device in system.devices:
#     if not device.product_type.startswith("cDAQ"):
#         # This is likely the module
#         module_name = device.name
#         print("was here")
#         break
#     else:
#         try:
#             # If chassis exposes modules directly
#             module_name = device.modules[0].name
#             break
#         except Exception:
#             pass

# if not module_name:
#     raise RuntimeError("No module found.")

# print(f"Connecting to {module_name}/ai0")

# with nidaqmx.Task() as task:
#     task.ai_channels.add_ai_voltage_chan(f"{module_name}/ai0")
#     print("Reading:", task.read())


# #-------------------------------------------------------------------
# # Looks through the device and gives a full description of NI device
# import nidaqmx.system

# system = nidaqmx.system.System.local()
# for device in system.devices:
#     print(f"Device name: {device.name}")
#     print(f"Product type: {device.product_type}")
    
#     # # Not all devices have serial_number, so check before accessing
#     # if hasattr(device, "serial_number"):
#     #     try:
#     #         print(f"Serial number: {device.serial_number}")
#     #     except Exception:
#     #         print("Serial number not available for this device.")
    
#     # If it's a chassis, check for modules
#     try:
#         if device.product_type.startswith("cDAQ"):
#             print("  Modules in chassis:")
#             for module in device.modules:
#                 print(f"    {module.name} - {module.product_type}")
#     except AttributeError:
#         pass

#     print("-" * 30)
