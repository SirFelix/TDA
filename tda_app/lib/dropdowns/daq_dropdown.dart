import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';

class DaqDropdown extends StatelessWidget {
  const DaqDropdown({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, appState, _) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [

            const SizedBox(height: 16),
            // Mode selector using SegmentedButton
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: "Serial", label: Text("USB")),
                ButtonSegment(value: "Ethernet", label: Text("Ethernet")),
              ],
              selected: {appState.daqMode},
              onSelectionChanged: (newSelection) {
                if (newSelection.isNotEmpty) {
                  appState.setDaqMode(newSelection.first);
                }
              },
            ),

            const SizedBox(height: 16),

            // Mode-specific controls
            if (appState.daqMode == "Ethernet") ...[
              DropdownMenu<String>(
                width: 290,
                initialSelection: appState.NIModule,
                hintText: 'Select Channel Address',
                onSelected: (value) {
                  if (value != null) appState.setSelectedNIModuleChannel(value);
                },
                dropdownMenuEntries: [
                  'cDAQ9181-2185DAEMod1/ai0',
                  'cDAQ9181-2185DAEMod1/ai1',
                ].map((ch) => DropdownMenuEntry<String>(
                      value: ch,
                      label: ch,
                    ))
                  .toList(),
              ),
              const SizedBox(height: 8),
              DropdownMenu<int>(
                width: 290,
                initialSelection: appState.setNIModuleSPS,
                hintText: 'Frame Rate',
                onSelected: (value) {
                  if (value != null) appState.setNIModuleSPS = value;
                },
                dropdownMenuEntries: [1, 2, 5, 10, 20, 30]
                    .map((fps) => DropdownMenuEntry<int>(
                          value: fps,
                          label: '$fps',
                        ))
                    .toList(),
              ),
            ] else if (appState.daqMode == "Serial") ...[
              DropdownMenu<String>(
                width: 290,
                initialSelection: appState.setSerialPort,
                hintText: 'Select Port',
                onSelected: (value) {
                  if (value != null) appState.setSelectedSerialPort(value);
                },
                dropdownMenuEntries: appState.availablePorts
                    .map((port) => DropdownMenuEntry<String>(
                          value: port,
                          label: port,
                        ))
                    .toList(),
              ),
              const SizedBox(height: 8),
              DropdownMenu<int>(
                width: 290,
                initialSelection: appState.setSerialBaudRate,
                hintText: 'Select Baud Rate',
                onSelected: (value) {
                  if (value != null) appState.setSelectedBaudRate(value);
                },
                dropdownMenuEntries: appState.availableBaudRates
                    .map((baud) => DropdownMenuEntry<int>(
                          value: baud,
                          label: baud.toString(),
                        ))
                    .toList(),
              ),
              const SizedBox(height: 8),
              DropdownMenu<int>(
                width: 290,
                initialSelection: appState.setSerialFPS,
                hintText: 'Frame Rate',
                onSelected: (value) {
                  if (value != null) appState.setSerialFPS = value;
                },
                dropdownMenuEntries: [1, 2, 5, 10, 20, 30]
                    .map((fps) => DropdownMenuEntry<int>(
                          value: fps,
                          label: '$fps',
                        ))
                    .toList(),
              ),
            ],

            const SizedBox(height: 8),

            Divider(
              thickness: 2,),

            const SizedBox(height: 8),

            // Start / Stop DAQ button
            ElevatedButton.icon(
              onPressed: () {
                if (appState.isDAQRunning) {
                  appState.stopDAQ();
                } else {
                  appState.startDAQ();
                }
              },
              icon: Icon(
                appState.isDAQRunning
                    ? Icons.stop_circle_outlined
                    : Icons.play_circle_outlined,
                size: 23,
                color: Colors.white,
              ),
              label: Text(
                appState.isDAQRunning ? 'Stop DAQ' : 'Start DAQ',
                style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w600, color: Colors.white),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor:
                    appState.isDAQRunning ? Colors.red : Colors.green,
              ),
            ),
          ],
        );
      },
    );
  }
}
