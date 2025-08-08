import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_libserialport/flutter_libserialport.dart';
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
  bool isDAQConnected = false;
  bool isDAQRunning = false;
  bool isDAQScanning = false;
  bool autoDAQScanEnabled = true;

  bool isRIGConnected = false;
  bool isRIGRunning = false;
  bool isRIGScanning = false;
  bool autoRIGScanEnabled = true;

  String? setEthernetIp;
  String? setSerialPort;
  int setSerialBaudRate = 57600;
  SerialPort? _port;

  List<TractorRawFiltered> tractorData = [];
  List<TractorSpeed> tractorSpeedData = [];
  Map<String, double> latestMetrics = {};
  List<EthDeviceInfo> connectedDevices = [];

  // Replaces manual 'availablePorts' list with dynamic port recognition
  List<String> get availablePorts => SerialPort.availablePorts;

  final List<int> availableBaudRates = [
    9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
  ];


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

  void connectDAQ() {
    sendCommand({'command': 'connect'});
    isDAQConnected = true;
    notifyListeners();
  }

  void disconnectDAQ() {
    sendCommand({'command': 'disconnect'});
    isDAQConnected = false;
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

  void toggleAutoDAQScan(bool enabled) {
    autoDAQScanEnabled = enabled;
    sendCommand({'command': 'setAutoScan', 'enabled': enabled});
    notifyListeners();
  }

  void scanDevicesDAQ() {
    isDAQScanning = true;
    sendCommand({'command': 'scan'});
    notifyListeners();
  }
  void setSelectedEthernetIp(String ip) {
    setEthernetIp = ip;
    notifyListeners();
  }

  void setSelectedSerialPort(String? port) {
    setSerialPort = port;
    notifyListeners();
  }
  
  void setSelectedBaudRate(int baudRate) {
    setSerialBaudRate = baudRate;
    notifyListeners();
  }
}


