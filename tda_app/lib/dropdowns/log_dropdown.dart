import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';

class LogDropdown extends StatefulWidget {
  const LogDropdown({super.key});

  @override
  State<LogDropdown> createState() => _LogDropdownState();
}

class _LogDropdownState extends State<LogDropdown> {
  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, child) {
        Color statusColor;
        String statusText;

        if (state.isLogging) {
          statusColor = Colors.green;
          statusText = 'Logging...';
        } else if (state.isCreatingLog) {
          statusColor = Colors.orange;
          statusText = 'Creating Log...';
        } else if (state.isNotLogging) {
          statusColor = Colors.red;
          statusText = 'Connection Lost';
        } else {
          statusColor = Colors.grey;
          statusText = 'Not Logging';
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
            
            // Log Dropdown
            TextField(
              controller: TextEditingController(text: state.fileName)
                ..selection = TextSelection.fromPosition(
                  TextPosition(offset: state.fileName.length),
                ),
              decoration: const InputDecoration(
                labelText: 'Job Name',
                hintText: "Enter Job Name",
                border: OutlineInputBorder(),
              ),
              // onSubmitted: (value) => state.setLogName(value),
              onChanged: (value) => state.setLogName(value),
            ),
            const SizedBox(height: 12),

            // File Location
            // Not written in yet. Will be added later

            Row(
              children: [
                ElevatedButton(
                  onPressed: state.isLogging
                    ? null
                    : () => state.startLogging(),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: state.isLogging
                      ? Colors.grey
                      : Colors.green
                  ),
                  child: const Text('Start Logging', style: TextStyle(color: Colors.white),),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  onPressed: state.isLogging
                    ? () => state.stopLogging()
                    : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: state.isLogging
                      ? Colors.red
                      : Colors.grey
                  ),
                  child: const Text('Stop Logging', style: TextStyle(color: Colors.white),),
                ),
              ],
            )
          ],
        );
      }
    );
  }
}