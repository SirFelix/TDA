import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';

class DaqDropdown extends StatefulWidget {
  const DaqDropdown({super.key});

  @override
  State<DaqDropdown> createState() => _DaqDropdownState();
}

class _DaqDropdownState extends State<DaqDropdown> {
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
                SizedBox(width: 4),
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
              ],
            ),
             const SizedBox(height: 16),

            if (selectedValue == "Ethernet") ...[
              // Example Ethernet-specific dropdown
              DropdownButton<String>(
                value: appState.setEthernetIp ?? '192.168.1.1',
                items: ['192.168.1.1', '192.168.1.2'].map((ip) {
                  return DropdownMenuItem(value: ip, child: Text(ip));
                }).toList(),
                onChanged: (value) {
                  appState.setSelectedEthernetIp(value!);
                },
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
                dropdownMenuEntries: appState.availableBaudRates
                    .map<DropdownMenuEntry<int>>((int baudRate) {
                  return DropdownMenuEntry<int>(
                    value: baudRate,
                    label: baudRate.toString(),
                  );
                }).toList(),
              ),
            ],

            const SizedBox(height: 8),

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
                appState.isDAQConnected ? 'Disconnect' : 'Connect',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: appState.isDAQConnected
                  ? Colors.red
                  : Colors.green,
              ),
            ),

            Padding(padding: const EdgeInsets.only(bottom: 8)),
          ],
        );
      },
    );
  }
}
