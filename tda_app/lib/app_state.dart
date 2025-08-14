import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
// import 'package:flutter/painting.dart';
import 'package:flutter_libserialport/flutter_libserialport.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

class EthDeviceInfo {
  final String name;
  final String ip;
  EthDeviceInfo({required this.name, required this.ip});
}

class TractorPressure {
  final DateTime timestamp;
  final double rawPressure;
  final double filteredPressure;
  TractorPressure({required this.timestamp, required this.rawPressure, required this.filteredPressure});
}

class TractorSpeed {
  final DateTime timestamp;
  final double tractorSpeed;
  TractorSpeed({required this.timestamp, required this.tractorSpeed});
}

class RigData {
  final DateTime timestamp;
  final double ctPressure;
  final double whPressure;
  final double ctDepth;
  final double ctWeight;
  final double ctSpeed;
  final double ctFluidRate;
  final double n2FluidRate;

  RigData({required this.timestamp, 
  required this.ctPressure, 
  required this.whPressure, 
  required this.ctDepth, 
  required this.ctWeight, 
  required this.ctSpeed, 
  required this.ctFluidRate, 
  required this.n2FluidRate});
  
}

class LogEntry {
  final DateTime logtime;
  final double? logctPressure;
  final double? logwhPressure;
  final double? logctDepth;
  final double? logctWeight;
  final double? logctSpeed;
  final double? logctFluidRate;
  // final double? logn2FluidRate;
  final String? logcomments;

  LogEntry({required this.logtime, 
  required this.logctPressure, 
  required this.logwhPressure, 
  required this.logctDepth, 
  required this.logctWeight, 
  required this.logctSpeed, 
  required this.logctFluidRate, 
  // required this.logn2FluidRate, 
  required this.logcomments});
}



class AppState extends ChangeNotifier {
  static final AppState _instance = AppState._internal();
  factory AppState() {
  return _instance;
  }
  AppState._internal(){
    _seedMockLogs(); 
  }

  WebSocketChannel? _channel;
  StreamSubscription? _channelSubscription;

  // WebSocket config & status
  String wsAddress = 'localhost';
  int wsPort = 9813;
  bool wsConnected = false;
  bool wsConnecting = false;
  bool wsConnectionLost = false;

  // Realtime data
  bool isDAQConnected = false;
  bool isDAQRunning = false;
  bool isDAQScanning = false;
  bool autoDAQScanEnabled = true;

  bool isRIGConnected = false;
  bool isRIGRunning = false;
  bool isRIGScanning = false;
  bool autoRIGScanEnabled = true;

  String? setEthernetIp = '192.168.4.140';
  int? setEthernetPort = 2000;

  String? setNIModule = 'cDAQ9181-2185DAEMod1/ai0';
  int? setNIModuleSPS = 30;

  String? setSerialPort;
  int setSerialBaudRate = 57600;
  // SerialPort? _port;

  List<TractorPressure> tractorData = [];
  List<TractorSpeed> tractorSpeedData = [];
  List<RigData> rigData = [];
  // for Logging table
  final List<LogEntry> _logEntries = [];
  List<LogEntry> get logEntries => List.unmodifiable(_logEntries);
  Map<String, double> latestMetrics = {};
  List<EthDeviceInfo> connectedDevices = [];

  List<String> get availablePorts => SerialPort.availablePorts;

  final List<int> availableBaudRates = [
    9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
  ];

  /// Call this from your main screen initState to auto-connect
  void init() {
    connectWebSocket();
  }

  /// Connect with the currently set address & port
  void connectWebSocket() {
    if (wsConnected || wsConnecting) return;

    wsConnecting = true;
    wsConnectionLost = false;
    notifyListeners();

    try {
      final uri = Uri.parse('ws://$wsAddress:$wsPort');
      _channel = WebSocketChannel.connect(uri);

      _channelSubscription = _channel!.stream.listen(
        (message) {
          wsConnected = true;
          wsConnecting = false;
          _handleMessage(jsonDecode(message));
          notifyListeners();
        },
        onError: (error) {
          _handleDisconnect(lost: true);
        },
        onDone: () {
          _handleDisconnect(lost: true);
        },
        cancelOnError: true,
      );
    } catch (e) {
      _handleDisconnect(lost: true);
    }
  }


  /// Disconnect manually
  void disconnectWebSocket() {
    if (wsConnected) {
      sendCommand({'command': 'WSdisconnect'});
    }
    _channelSubscription?.cancel();
    _channel?.sink.close(status.normalClosure);
    _handleDisconnect(lost: false);
  }


  /// Reconnect
  void reconnectWebSocket() {
    disconnectWebSocket();
    Future.delayed(Duration(milliseconds: 300), connectWebSocket);
    if (wsConnected) {
      sendCommand({'command': 'WSconnect'});
    }
  }

  void _handleDisconnect({required bool lost}) {
    wsConnected = false;
    wsConnecting = false;
    wsConnectionLost = lost;
    notifyListeners();
  }


  // Old message handler
  // void _handleMessage(dynamic data) {
  //   if (data['source'] == 'DAQ') {
  //     if (data['type'] == 'sensor') {
  //       final point = TractorPressure(
  //         timestamp: DateTime.parse(data['timestamp']),
  //         rawPressure: data['raw'],
  //         filteredPressure: data['filtered'],
  //       );
  //       tractorData.add(point);
  //       if (tractorData.length > 100) tractorData.removeAt(0);
  //     }
      
  //     if (data['type'] == 'tractor') {
  //       final speed = TractorSpeed(
  //         timestamp: DateTime.parse(data['timestamp']),
  //         speed: data['speed'],
  //       );
  //       tractorSpeedData.add(speed);
  //       if (tractorSpeedData.length > 100) tractorSpeedData.removeAt(0);
  //     }
      
  //     if (data['type'] == 'metric_update') {
  //       latestMetrics[data['name']] = data['value'];
  //     }
  //   }
  //   else if (data['source'] == 'RIG') {
  //     if (data['type'] == 'device') {
  //       // connectedDevices = data['devices'];
  //     }
  //   }

  //   notifyListeners();
  // }


  void _handleMessage(dynamic data) {
    if (data['source'] == 'DAQ' && data['type'] == 'data') {
      final params = data['params'];
      if (params != null) {

        // Handle timestamp
        final double? ts = params['timestamp']?.toDouble();
        if (ts == null) return;
        final timestamp = DateTime.fromMillisecondsSinceEpoch((ts * 1000).toInt(),);


        // Handle pressures together only if rawPressure is available
        if (params['raw_pressure'] != null) {
          final rawPressure = (params['raw_pressure'] as num).toDouble();
          final filteredPressure = (params['filtered_pressure'] as num?)?.toDouble() ?? -1;

          final pressurePoint = TractorPressure(
            timestamp: timestamp,
            rawPressure: rawPressure,
            filteredPressure: filteredPressure,
          );
          _addTractorPressure(pressurePoint);
        }

        // Handle tractor speed independently if present
        if (params['tractor_speed'] != null) {
          final speed = (params['tractor_speed'] as num?)?.toDouble() ?? -1;
          final speedPoint = TractorSpeed(timestamp: timestamp, tractorSpeed: speed);
          _addTractorSpeed(speedPoint);
        }
      }
    }
    else if (data['source'] == 'RIG' && data['type'] == 'data') {
      final params = data['params'];
      if (params != null) {
        final timestamp = DateTime.fromMillisecondsSinceEpoch((params['timestamp'] as num).toInt(),);
        final ctPressure = (params['ct_pressure'] as num?)?.toDouble() ?? -1;
        final whPressure = (params['wh_pressure'] as num?)?.toDouble() ?? -1;
        final ctDepth = (params['ct_depth'] as num?)?.toDouble() ?? -1;
        final ctWeight = (params['ct_weight'] as num?)?.toDouble() ?? -1;
        final ctSpeed = (params['ct_speed'] as num?)?.toDouble() ?? -1;
        final ctFluidRate = (params['ct_fluid_rate'] as num?)?.toDouble() ?? -1;
        final n2FluidRate = (params['n2_fluid_rate'] as num?)?.toDouble() ?? -1;

        final rigdatapoint = RigData(
          timestamp: timestamp, 
          ctPressure: ctPressure,
          whPressure: whPressure,
          ctDepth: ctDepth,
          ctWeight: ctWeight,
          ctSpeed: ctSpeed,
          ctFluidRate: ctFluidRate,
          n2FluidRate: n2FluidRate,
        );
        _addRigData(rigdatapoint);
      }
    }
    notifyListeners();
  }


  static const int maxDataPoints = 2000;

  // Add other data lists here for Rig source, e.g.:
  // final List<RigData> rigData = [];

  void _addTractorPressure(TractorPressure point) {
    tractorData.add(point);
    if (tractorData.length > maxDataPoints) {
      tractorData.removeRange(0, tractorData.length - maxDataPoints);
    }
    _scheduleUpdate();
  }

  void _addTractorSpeed(TractorSpeed speed) {
    tractorSpeedData.add(speed);
    if (tractorSpeedData.length > maxDataPoints) {
      tractorSpeedData.removeRange(0, tractorSpeedData.length - maxDataPoints);
    }
    _scheduleUpdate();
  }

  void _addRigData(RigData rigdatapoint) {
    rigData.add(rigdatapoint);
    if (rigData.length > (maxDataPoints - 300)) {
      rigData.removeRange(0, rigData.length - (maxDataPoints - 300));
    }
    _scheduleUpdate();
  }

  
  //Combine the updates of the two lists
  Timer? _updateTimer;
  void _scheduleUpdate() {
    if (_updateTimer == null || !_updateTimer!.isActive) {
      _updateTimer = Timer(Duration(milliseconds: 100), () {
        notifyListeners();
      });
    }
  }

  // Send commands over WS
  void sendCommand(Map<String, dynamic> message) {
    if (wsConnected) {
      _channel!.sink.add(jsonEncode(message));
    }
  }

  void addLogEntry(LogEntry entry){
    _logEntries.insert(0, entry); // insert at the beginning
    notifyListeners();
  }

  void _seedMockLogs(){
    // adding a few mock logs
    _logEntries.addAll([
      LogEntry(
        logtime: DateTime.now().subtract(const Duration(minutes: 5)), 
        logctPressure: 6402, 
        logwhPressure: 1743, 
        logctDepth: 18164, 
        logctWeight: 9162, 
        logctSpeed: 14.2, 
        logctFluidRate: 5.25, 
        logcomments: "Nominal"
      ),
      LogEntry(
        logtime: DateTime.now().subtract(const Duration(minutes: 7)), 
        logctPressure: 6474, 
        logwhPressure: 1714, 
        logctDepth: 18023, 
        logctWeight: 8460, 
        logctSpeed: 13.8, 
        logctFluidRate: 5.25, 
        logcomments: "Lost some weight" 
      ),
      LogEntry(
        logtime: DateTime.now().subtract(const Duration(minutes: 12)), 
        logctPressure: 6281, 
        logwhPressure: 1684, 
        logctDepth: 17804, 
        logctWeight: 11462, 
        logctSpeed: 14.7, 
        logctFluidRate: 5.2, 
        logcomments: "RIH"
      ),
    ]);
  }

  // UI-bound setters
  void setWsAddress(String value) {
    wsAddress = value;
    notifyListeners();
  }

  void setWsPort(int value) {
    wsPort = value;
    notifyListeners();
  }

  // Your existing DAQ control methods remain unchanged
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
    sendCommand({"type": "command", "params": {"action": "DAQstart"}});
    isDAQRunning = true;
    notifyListeners();
  }

  void stopDAQ() {
    sendCommand({"type": "command", "params": {"action": "DAQstop"}});
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

  void setSelectedNIModuleChannel(String channel) {
    setNIModule = channel;
    sendCommand({'command': 'setNIModule', 'channel': channel});
    notifyListeners();
  }

  void setSelectedSerialPort(String? port) {
    setSerialPort = port;
    notifyListeners();
  }

  void setSelectedEthernetPort(int? port) {
    setEthernetPort = port;
    notifyListeners();
  }

  void setSelectedBaudRate(int baudRate) {
    setSerialBaudRate = baudRate;
    notifyListeners();
  }

  String daqMode = "Ethernet"; // or "Serial"
  void setDaqMode(String mode) {
    daqMode = mode;
    notifyListeners();
  }

  int? setSerialFPS; // for serial frame rate
}
