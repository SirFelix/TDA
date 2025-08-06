import 'package:flutter/foundation.dart';
import 'dart:convert';
// import 'dart:async';


class DaqProvider with ChangeNotifier {
  final List<String> _log = [];
  final List<DaqDataPoint> _chartData = [];
  bool _isConnected = false;
  bool _isStreaming = false;

  List<String> get log => _log;
  List<DaqDataPoint> get chartData => _chartData;
  bool get isConnected => _isConnected;
  bool get isStreaming => _isStreaming;

  
  DateTime _lastUpdate = DateTime.now();

  void connect() {
    // print('[DaqProvider] connect() called');  // For Debugging 
    _isConnected = true;
    notifyListeners();
  }

  void disconnect() {
    // print('[DaqProvider] disconnect() called');  // For Debugging 
    _isConnected = false;
    _isStreaming = false;
    notifyListeners();
  }

  void clearLog() {
    _log.clear();
    _chartData.clear();
    notifyListeners();
  }

  void startStreaming() {
    _isStreaming = true;
    notifyListeners();
  }


  void handleIncomingMessage(String message) {
    _log.add(message);

    try {
      final decoded = json.decode(message);
      if (decoded['type'] == 'data') {
        final ts = DateTime.fromMillisecondsSinceEpoch((decoded['timestamp'] * 1000).toInt());
        final value = (decoded['value'] as num).toDouble();
        _chartData.add(DaqDataPoint(timestamp: ts, value: value));

        // Keep only the last N points
        // if (_chartData.length > 300) {
        //   _chartData.removeRange(0, _chartData.length - 300);
        // }
        if (value == 0){
          _addChartPoint(value);
        }
      }
      else if (decoded['type'] == 'acknowledgement'){
        print("Python received and acknowledged message");
      }
    } catch (e) {
      print('[DAQ Error] Invalid message: $e');
    }

    notifyListeners();
  }
  void _addChartPoint(double value) {
  final now = DateTime.now();
  if (now.difference(_lastUpdate).inMilliseconds < 33) return;
  _lastUpdate = now;

  _chartData.add(DaqDataPoint(timestamp: now, value: value));
  if (_chartData.length > 50) _chartData.removeAt(0);

  notifyListeners();
}


  void stopStreaming() {
    _isStreaming = false;
    notifyListeners();
  }

}
class DaqDataPoint {
  final DateTime timestamp;
  final double value;

  DaqDataPoint({required this.timestamp, required this.value});
}