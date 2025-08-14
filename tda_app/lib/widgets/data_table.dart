import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/app_state.dart';
import 'package:intl/intl.dart';

class LoggingTable extends StatefulWidget {
  /// Optional fixed height for the scrolling list section.
  final double listHeight;
  final double listWidth;

  const LoggingTable({super.key, this.listHeight = 260, this.listWidth = 1200});

  @override
  State<LoggingTable> createState() => _LoggingTableState();
}

class _LoggingTableState extends State<LoggingTable> {
  // Controllers for the input row
  final _ctPressureCtrl = TextEditingController();
  final _whPressureCtrl = TextEditingController();
  final _ctDepthCtrl = TextEditingController();
  final _ctWeightCtrl = TextEditingController();
  final _ctSpeedCtrl = TextEditingController();
  final _ctFlRateCtrl = TextEditingController();
  final _commentsCtrl = TextEditingController();

  final _numberFormatter = NumberFormat("#,##0.###");
  final _timeFormatter = DateFormat('HH:mm:ss');

  // Fixed column widths so header/input/saved rows align
  static const double wTime = 120;
  static const double wNum = 120;
  static const double wComments = 240;


  @override
  void dispose() {
    _ctPressureCtrl.dispose();
    _whPressureCtrl.dispose();
    _ctDepthCtrl.dispose();
    _ctWeightCtrl.dispose();
    _ctSpeedCtrl.dispose();
    _ctFlRateCtrl.dispose();
    _commentsCtrl.dispose();
    super.dispose();
  }

  double? _parseDouble(String s) {
    final v = s.trim();
    if (v.isEmpty) return null;
    return double.tryParse(v);
  }

  void _handleSubmit(AppState appState) {

  // OLD CODE. Plan to be removed. Used to check for valid input on all fields
    // final ctPressure = _parseDouble(_ctPressureCtrl.text);
    // final whPressure = _parseDouble(_whPressureCtrl.text);
    // final ctDepth = _parseDouble(_ctDepthCtrl.text);
    // final ctWeight = _parseDouble(_ctWeightCtrl.text);
    // final ctSpeed = _parseDouble(_ctSpeedCtrl.text);
    // final ctFlRate = _parseDouble(_ctFlRateCtrl.text);

    // // Simple validation
    // if ([ctPressure, whPressure, ctDepth, ctWeight, ctSpeed, ctFlRate]
    //     .any((v) => v == null)) {
    //   ScaffoldMessenger.of(context).showSnackBar(
    //     const SnackBar(content: Text('Please enter valid numeric values.')),
    //   );
    //   return;
    // }

    // appState.addLogEntry(
    //   LogEntry(
    //     logtime: DateTime.now(),
    //     logctPressure: ctPressure!,
    //     logwhPressure: whPressure!,
    //     logctDepth: ctDepth!,
    //     logctWeight: ctWeight!,
    //     logctSpeed: ctSpeed!,
    //     logctFluidRate: ctFlRate!,
    //     logcomments: _commentsCtrl.text.trim(),
    //   ),
    // );
  // ------------------------------------

    final entry = LogEntry(
      logtime: DateTime.now(), 
      logctPressure: _ctPressureCtrl.text.isNotEmpty ? double.parse(_ctPressureCtrl.text) : null, 
      logwhPressure: _whPressureCtrl.text.isNotEmpty ? double.parse(_whPressureCtrl.text) : null, 
      logctDepth: _ctDepthCtrl.text.isNotEmpty ? double.parse(_ctDepthCtrl.text) : null,
      logctWeight: _ctWeightCtrl.text.isNotEmpty ? double.parse(_ctWeightCtrl.text) : null, 
      logctSpeed: _ctSpeedCtrl.text.isNotEmpty ? double.parse(_ctSpeedCtrl.text) : null, 
      logctFluidRate: _ctFlRateCtrl.text.isNotEmpty ? double.parse(_ctFlRateCtrl.text) : null, 
      logcomments: _commentsCtrl.text.isNotEmpty ? _commentsCtrl.text : null,
      );

    appState.addLogEntry(entry);

    // Clear input row
    _ctPressureCtrl.clear();
    _whPressureCtrl.clear();
    _ctDepthCtrl.clear();
    _ctWeightCtrl.clear();
    _ctSpeedCtrl.clear();
    _ctFlRateCtrl.clear();
    _commentsCtrl.clear();
  }

  Widget _headerCell(String label, double width) {
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
      alignment: Alignment.centerLeft,
      color: Colors.grey.shade300,
      child: Text(
        label,
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
    );
  }

  Widget _inputCell({
    required TextEditingController controller,
    required double width,
    String? hint,
    bool isNumber = true,
  }) {
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      color: Colors.grey.shade50,
      child: TextField(
        controller: controller,
        decoration: InputDecoration(
          isDense: true,
          hintText: hint,
          border: const OutlineInputBorder(),
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        ),
        keyboardType: isNumber
            ? const TextInputType.numberWithOptions(decimal: true, signed: false)
            : TextInputType.text,
      ),
    );
  }

  Widget _dataCell(String text, double width) {
    return Container(
      width: width,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      alignment: Alignment.centerLeft,
      child: Text(text),
    );
  }

  @override
  Widget build(BuildContext context) {
    final appState = context.watch<AppState>();

    return Card(
      elevation: 2,
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(12),

        child: SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: ConstrainedBox(
            // Make sure the table gets at least full width of the viewport
            constraints: BoxConstraints(minWidth: MediaQuery.of(context).size.width - 48),
            // constraints: BoxConstraints(maxWidth: ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header row
                Row(
                  children: [
                    _headerCell('Time', wTime),
                    _headerCell('Circ Pressure', wNum),
                    _headerCell('WH Pressure', wNum),
                    _headerCell('CT Depth', wNum),
                    _headerCell('CT Weight', wNum),
                    _headerCell('CT Speed', wNum),
                    _headerCell('CT FL Rate', wNum),
                    _headerCell('Comments', wComments),
                    _headerCell('', wTime),
                  ],
                ),

                const SizedBox(height: 8),

                // // Submit button
                // Align(
                //   alignment: Alignment.centerLeft,
                //   child: ElevatedButton.icon(
                //     icon: const Icon(Icons.save),
                //     label: const Text('Submit'),
                //     onPressed: () => _handleSubmit(appState),
                //   ),
                // ),

                // const SizedBox(height: 8),

                // Input row
                Row(
                  children: [
                    // Time is auto-filled on submit; show "Now"
                    StreamBuilder<DateTime>(
                      stream: Stream.periodic(const Duration(seconds: 1), (_) => DateTime.now()),
                      builder: (context, snapshot) {
                        final now = snapshot.data ?? DateTime.now();
                        final timeStr = "${now.hour.toString().padLeft(2, '0')}:"
                                        "${now.minute.toString().padLeft(2, '0')}"
                                        ":${now.second.toString().padLeft(2, '0')}";
                        return Container(
                          width: wTime,
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                          color: Colors.grey.shade100,
                          child: Text('Now ($timeStr)'),
                        );
                      },
                    ),
                    // Container(
                    //   width: wTime,
                    //   padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
                    //   color: Colors.grey.shade100,
                    //   child: Text('Now (${_timeFormatter.format(DateTime.now())})'),
                    // ),
                    _inputCell(controller: _ctPressureCtrl,width: wNum,hint: 'psi',isNumber: true,),
                    _inputCell(controller: _whPressureCtrl,width: wNum,hint: 'psi',isNumber: true,),
                    _inputCell(controller: _ctDepthCtrl,width: wNum,hint: 'ft',isNumber: true,),
                    _inputCell(controller: _ctWeightCtrl,width: wNum,hint: 'klbf',isNumber: true,),
                    _inputCell(controller: _ctSpeedCtrl,width: wNum,hint: 'ft/min',isNumber: true,),
                    _inputCell(controller: _ctFlRateCtrl,width: wNum,hint: 'bbl/min',isNumber: true,),
                    _inputCell(controller: _commentsCtrl,width: wComments,hint: 'Comments',isNumber: false,),

                    const SizedBox(width: 8,),

                    // Submit button
                    ElevatedButton.icon(
                      icon: const Icon(Icons.save),
                      label: const Text('Submit'),
                      onPressed: () => _handleSubmit(appState),
                    ),

                  ],
                ),

                const SizedBox(height: 12),

                // Saved rows (scrollable vertically)
                SizedBox(
                  // width: double.infinity,
                  width: widget.listWidth,
                  height: widget.listHeight,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: Container(
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.grey.shade300),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: ListView.builder(
                        itemCount: appState.logEntries.length,
                        itemBuilder: (context, index) {
                          final e = appState.logEntries[index];
                          final bg = index.isEven
                              ? Colors.grey.shade200
                              : Colors.grey.shade100;
                          return Container(
                            color: bg,
                            child: Row(
                              children: [
                                _dataCell(_timeFormatter.format(e.logtime), wTime),
                                _dataCell(e.logctPressure != null ? _numberFormatter.format(e.logctPressure) : '', wNum),
                                _dataCell(e.logwhPressure != null ? _numberFormatter.format(e.logwhPressure) : '', wNum),
                                _dataCell(e.logctDepth != null ? _numberFormatter.format(e.logctDepth) : '', wNum),
                                _dataCell(e.logctWeight != null ? _numberFormatter.format(e.logctWeight): '', wNum),
                                _dataCell(e.logctSpeed != null ? _numberFormatter.format(e.logctSpeed) : '', wNum),
                                _dataCell(e.logctFluidRate != null ? _numberFormatter.format(e.logctFluidRate) : '', wNum),
                                _dataCell(e.logcomments ?? '', wComments),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
