import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';

class RigDropdown extends StatefulWidget {
  const RigDropdown({super.key});

  @override
  State<RigDropdown> createState() => RigqDropdownState();
}

class RigqDropdownState extends State<RigDropdown> {
  String selectedValue = "Serial";

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, child) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Radio<String>(
                  value: "Serial",
                  groupValue: selectedValue,
                  onChanged: (value) {
                    setState(() {
                      selectedValue = value!;
                    });
                  },
                ),
                Container(
                  // color: Colors.white,
                  decoration: BoxDecoration(
                    color: Colors.transparent,
                  ),
                  child: Text("Serial"),
                ),
                SizedBox(width: 4),
                Radio<String>(
                  value: "Ethernet",
                  groupValue: selectedValue,
                  onChanged: (value) {
                    setState(() {
                      selectedValue = value!;
                    });
                  },
                ),
                Container(
                  // color: Colors.white,
                  decoration: BoxDecoration(
                    color: Colors.transparent,
                  ),
                  child: Text("Ethernet"),
                ),
              ],
            ),
             const SizedBox(height: 16),

            if (selectedValue == "Ethernet") ...[
              // Ethernet Dropdown
              DropdownMenu<String>(
                width: 250,
                initialSelection: appState.setEthernetIp ?? '192.168.4.140',
                hintText: 'Select/Enter IP',
                onSelected: (value) => setState(() => appState.setEthernetIp = value),
                dropdownMenuEntries: ['Auto', '192.168.4.140',].map((ip) {
                  return DropdownMenuEntry<String>(
                    value: ip,
                    label: ip,
                  );
                }).toList(),
              ),

              const SizedBox(height: 8),

              // Eth Port Dropdown
              DropdownMenu<int>(
                width: 250,
                initialSelection: appState.setEthernetPort ?? 2000,
                hintText: 'Select Port',
                onSelected: (int? value) {setState(() {appState.setSelectedEthernetPort(value!);});},
                dropdownMenuEntries: [2000, 5000].map((port) {
                  return DropdownMenuEntry<int>(
                    value: port,
                    label: port.toString(),
                  );
                }).toList(),
              ),

              const SizedBox(height: 8),

              // Serial Connect
              ElevatedButton.icon(
                onPressed: appState.setEthernetIp != null && appState.setEthernetPort != null
                    ? appState.connectDAQ
                    : null,
                icon: Icon(
                  appState.isDAQConnected
                    ? Icons.stop_circle_outlined
                    : Icons.play_circle_outlined,
                  size: 23,
                ),
                label: Text(
                  appState.isDAQConnected ? 'Disconnect Ethernet' : 'Connect Ethernet',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: appState.isDAQConnected
                    ? Colors.red
                    : Colors.green,
                ),
              ),
            ] else if (selectedValue == "Serial") ...[
              // Example Serial-specific dropdown
              DropdownMenu<String>(
                width: 250,
                initialSelection: appState.setSerialPort,
                hintText: 'Select Port',
                onSelected: (String? value) {
                  appState.setSelectedSerialPort(value);
                },
                dropdownMenuEntries: appState.availablePorts
                    .map<DropdownMenuEntry<String>>((String port) {
                  return DropdownMenuEntry<String>(
                    value: port,
                    label: port,
                  );
                }).toList(),
              ),
              const SizedBox(height: 8),
              DropdownMenu<int>(
                width: 250,
                initialSelection: appState.setSerialBaudRate,
                hintText: 'Select Baud Rate',
                onSelected: (int? value) {
                  appState.setSelectedBaudRate(value!);
                },
                dropdownMenuEntries: 
                appState.availableBaudRates.map<DropdownMenuEntry<int>>((int baudRate) {
                  return DropdownMenuEntry<int>(
                    value: baudRate,
                    label: baudRate.toString(),
                  );
                }).toList(),
              ),

              const SizedBox(height: 8),

              // Serial Connect
              ElevatedButton.icon(
                onPressed: appState.setSerialPort != null
                    ? appState.connectDAQ
                    : null,
                icon: Icon(
                  appState.isDAQConnected
                    ? Icons.stop_circle_outlined
                    : Icons.play_circle_outlined,
                  size: 23,
                ),
                label: Text(
                  appState.isDAQConnected ? 'Disconnect Serial' : 'Connect Serial',
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                ),
                style: ElevatedButton.styleFrom(
                  backgroundColor: appState.isDAQConnected
                    ? Colors.red
                    : Colors.green,
                ),
              ),
            ],


            Padding(padding: const EdgeInsets.only(bottom: 8)),
          ],
        );
      },
    );
  }
}
