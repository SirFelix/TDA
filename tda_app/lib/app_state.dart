import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:tda_app/tabs/dashboard.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

class AppState extends ChangeNotifier {
  static final AppState _instance = AppState._internal();
  factory AppState() => _instance;
  AppState._internal();

  final WebSocketChannel channel = WebSocketChannel.connect(
    Uri.parse('ws://localhost:8765'), // Replace with your socket address
  );

  // Realtime data
  List<MySensorPoint> sensorData = [];
  List<TractorData> tractorSpeedData = [];
  Map<String, double> latestMetrics = {};
  List<DeviceInfo> connectedDevices = [];

  void init() {
    channel.stream.listen((message) {
      final data = jsonDecode(message);
      _handleMessage(data);
    });
  }

  void _handleMessage(dynamic data) {
    // Example logic
    if (data['type'] == 'sensor') {
      final point = MySensorPoint(
        DateTime.parse(data['timestamp']),
        data['raw'],
        data['filtered'],
      );
      sensorData.add(point);
      if (sensorData.length > 100) sensorData.removeAt(0);
    }

    if (data['type'] == 'tractor') {
      final speed = TractorData(
        DateTime.parse(data['timestamp']),
        data['speed'],
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
  void sendCommand(String command, [Map<String, dynamic>? payload]) {
    final msg = {'command': command, 'payload': payload ?? {}};
    channel.sink.add(jsonEncode(msg));
  }
}


// Created to add some data
class DeviceInfo {
}

class TractorData {
  TractorData(DateTime parse, data);
}
