import 'dart:convert';
import 'package:flutter/foundation.dart';
// import 'package:tda_app/tabs/dashboard.dart';
import 'package:web_socket_channel/web_socket_channel.dart';






// Created to add some data
class EthDeviceInfo {
  final String name;
  final String ip;

  EthDeviceInfo({required this.name, required this.ip});
}

class TractorRawFiltered {

  final DateTime timestamp;
  final double raw;
  final double filtered;

  TractorRawFiltered({required this.timestamp, required this.raw, required this.filtered});
}
class TractorSpeed {

  final DateTime timestamp;
  final double speed;

  TractorSpeed({required this.timestamp, required this.speed});
}




class AppState extends ChangeNotifier {
  static final AppState _instance = AppState._internal();
  factory AppState() => _instance;
  AppState._internal();

  final WebSocketChannel channel = WebSocketChannel.connect(
    Uri.parse('ws://localhost:8765'), // Replace with your socket address
  );

  // Realtime data
  bool isConnected = false;
  bool isDAQRunning = false;
  bool isScanning = false;
  bool autoScanEnabled = true;


  List<TractorRawFiltered> tractorData = [];
  List<TractorSpeed> tractorSpeedData = [];
  Map<String, double> latestMetrics = {};
  List<EthDeviceInfo> connectedDevices = [];


  void init() {
    channel.stream.listen((message) {
      final data = jsonDecode(message);
      _handleMessage(data);
    });
  }

  void _handleMessage(dynamic data) {
    // Example logic
    if (data['type'] == 'sensor') {
      final point = TractorRawFiltered(
        timestamp: DateTime.parse(data['timestamp']),
        raw: data['raw'],
        filtered: data['filtered'],
      );
      tractorData.add(point);
      if (tractorData.length > 100) tractorData.removeAt(0);
    }

    if (data['type'] == 'tractor') {
      final speed = TractorSpeed(
        timestamp: DateTime.parse(data['timestamp']),
        speed: data['speed'],
      );
      tractorSpeedData.add(speed);
      if (tractorSpeedData.length > 100) tractorSpeedData.removeAt(0);
    }

    // Example metric cards update
    if (data['type'] == 'metric_update') {
      latestMetrics[data['name']] = data['value'];
    }

    notifyListeners(); // tell all widgets to rebuild
  }

  // Sending commands
  void sendCommand(Map<String, dynamic> message) {
    // final msg = {'command': command, 'payload': payload ?? {}};
    channel.sink.add(jsonEncode(message));
  }

  void connect() {
    sendCommand({'command': 'connect'});
    isConnected = true;
    notifyListeners();
  }

  void disconnect() {
    sendCommand({'command': 'disconnect'});
    isConnected = false;
    notifyListeners();
  }

  void startDAQ() {
    sendCommand({'command': 'start'});
    isDAQRunning = true;
    notifyListeners();
  }

  void stopDAQ() {
    sendCommand({'command': 'stop'});
    isDAQRunning = false;
    notifyListeners();
  }

  void toggleAutoScan(bool enabled) {
    autoScanEnabled = enabled;
    sendCommand({'command': 'setAutoScan', 'enabled': enabled});
    notifyListeners();
  }

  void scanDevices() {
    isScanning = true;
    sendCommand({'command': 'scan'});
    notifyListeners();
  }
}


