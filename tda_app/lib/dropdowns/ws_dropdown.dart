import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';

class WSDropdown extends StatefulWidget {
  const WSDropdown({super.key});

  @override
  State<WSDropdown> createState() => RigqDropdownState();
}

class RigqDropdownState extends State<WSDropdown> {
  String selectedValue = "Serial";

  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, child) {
        Color statusColor;
        String statusText;

        if (state.wsConnecting) {
          statusColor = Colors.orange;
          statusText = 'Connecting...';
        } else if (state.wsConnected) {
          statusColor = Colors.green;
          statusText = 'Connected';
        } else if (state.wsConnectionLost) {
          statusColor = Colors.red;
          statusText = 'Connection Lost';
        } else {
          statusColor = Colors.grey;
          statusText = 'Disconnected';
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Status indicator
            Row(
              children: [
                Container(
                  width: 14,
                  height: 14,
                  decoration: BoxDecoration(
                    color: statusColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(statusText),
              ],
            ),
            const SizedBox(height: 12),

            // Address input
            TextField(
              controller: TextEditingController(text: state.wsAddress)
                ..selection = TextSelection.fromPosition(
                  TextPosition(offset: state.wsAddress.length),
                ),
              decoration: const InputDecoration(
                labelText: 'WebSocket Address',
                hintText: 'e.g., 192.168.1.100',
                border: OutlineInputBorder(),
              ),
              onSubmitted: state.setWsAddress,
            ),
            const SizedBox(height: 8),

            // Port input
            TextField(
              controller: TextEditingController(text: state.wsPort.toString())
                ..selection = TextSelection.fromPosition(
                  TextPosition(offset: state.wsPort.toString().length),
                ),
              decoration: const InputDecoration(
                labelText: 'Port',
                border: OutlineInputBorder(),
              ),
              keyboardType: TextInputType.number,
              onSubmitted: (val) {
                final port = int.tryParse(val);
                if (port != null) state.setWsPort(port);
              },
            ),
            const SizedBox(height: 12),

            // Buttons
            Wrap(
              children: [
                ElevatedButton(
                  onPressed: state.wsConnected
                      ? null
                      : () => state.connectWebSocket(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                  ),
                  child: const Text('Connect', style: TextStyle(color:  Colors.white),),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: state.wsConnected
                      ? () => state.disconnectWebSocket()
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.red,
                  ),
                  child: const Text('Disconnect', style: TextStyle(color:  Colors.white),),
                ),
                const SizedBox(width: 8),
                // ElevatedButton(
                //   onPressed: () => state.reconnectWebSocket(),
                //   style: ElevatedButton.styleFrom(
                //     backgroundColor: Colors.orange,
                //   ),
                //   child: const Text('Reconnect'),
                // ),
              ],
            ),
          ],
        );
      },
    );
  }
}
